#!/usr/bin/env python3
"""proto_spark_native.py — can the winning architecture be written with Apache Spark alone?

Evidence for the "rewrite in Python vs adapt Zingg" question (2026-09-19). Everything below is Spark SQL built-ins
and Spark MLlib: no scikit-learn, no GraphFrames, no JAR, no Python UDF. Every step except `fit` is a lazy DataFrame
transformation, i.e. expressible as a Spark Declarative Pipelines flow; `fit` would be a separate job task whose model
is logged with MLflow.

    blocking   character 3-grams -> join on shared grams -> cosine on gram sets -> top-k per anchor   (SQL only)
    features   per-field normalised levenshtein, equality, soundex agreement, gram cosine, rank, gap  (SQL only)
    matcher    MLlib GBTClassifier on 400 labelled candidate pairs
    decision   best candidate per anchor if P(match) >= 0.5

Task: FEBRL4 with half of the partners removed (2 500 true links, 2 500 anchors that must be rejected), as in
bench_pipeline.py --unmatched 0.5. Labels here come from ground truth for the 400 sampled pairs: on this data Jev's
confident labels were 100 % correct (2 173 of 2 173), so this isolates the question "does Spark-native code reach the
same quality as the scikit-learn pipeline", not "how good are the labels".

    source ../zingg_env.sh && $ZINGG_VENV/bin/python proto_spark_native.py [--drop soc_sec_id]
"""
import argparse
import time

import numpy as np
from pyspark.ml.classification import GBTClassifier
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.functions import vector_to_array
from pyspark.sql import SparkSession, Window, functions as F
from recordlinkage.datasets import load_febrl4

ap = argparse.ArgumentParser(); ap.add_argument("--drop", default=""); ap.add_argument("--k", type=int, default=5)
ap.add_argument("--labels", type=int, default=400); ap.add_argument("--cap", type=int, default=400, help="drop grams present in more B records than this")
args = ap.parse_args()
FIELDS = [f for f in ["given_name", "surname", "street_number", "address_1", "address_2", "suburb", "postcode", "state",
                      "date_of_birth", "soc_sec_id"] if f not in args.drop.split(",")]

a, b, links = load_febrl4(return_links=True)
truth = {x: y for x, y in links}
gone = set(np.random.default_rng(23).choice(sorted(truth.values()), size=len(truth) // 2, replace=False))
b = b.drop(index=list(gone)); truth = {x: y for x, y in truth.items() if y not in gone}

t_start = time.time()
spark = SparkSession.builder.master("local[*]").appName("mdm-native").config("spark.sql.shuffle.partitions", "16").config("spark.ui.enabled", "false").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
t0 = time.time()
to_df = lambda frame: spark.createDataFrame(frame.reset_index().fillna("").astype(str)[["rec_id"] + FIELDS])
A, B = to_df(a), to_df(b)

def grams(df):                       # distinct character 3-grams of the concatenated record, SQL only
    text = F.lower(F.concat_ws(" ", *[F.col(c) for c in FIELDS]))
    idx = F.sequence(F.lit(1), F.greatest(F.length(text) - 2, F.lit(1)))
    return df.withColumn("g", F.array_distinct(F.transform(idx, lambda i: F.substring(text, i, 3))))

GA, GB = grams(A), grams(B)
ea = GA.select(F.col("rec_id").alias("a_id"), F.size("g").alias("na"), F.explode("g").alias("gram"))
eb = GB.select(F.col("rec_id").alias("b_id"), F.size("g").alias("nb"), F.explode("g").alias("gram"))
common = eb.groupBy("gram").count().filter(F.col("count") <= args.cap).select("gram")           # drop ubiquitous grams
pairs = (ea.join(common, "gram").join(eb, "gram").groupBy("a_id", "b_id", "na", "nb").count()
           .withColumn("cos", F.col("count") / F.sqrt(F.col("na") * F.col("nb"))))
w = Window.partitionBy("a_id").orderBy(F.desc("cos"), "b_id")
cand = (pairs.withColumn("rank", F.row_number().over(w)).filter(F.col("rank") <= args.k)
             .withColumn("gap", F.max("cos").over(Window.partitionBy("a_id")) - F.col("cos")))

L, R = A.select([F.col(c).alias("l_" + c) for c in ["rec_id"] + FIELDS]), B.select([F.col(c).alias("r_" + c) for c in ["rec_id"] + FIELDS])
x = cand.join(L, cand.a_id == L.l_rec_id).join(R, cand.b_id == R.r_rec_id)
feats = ["cos", "rank", "gap"]
for c in FIELDS:
    l, r = F.col("l_" + c), F.col("r_" + c)
    both = (F.length(l) > 0) & (F.length(r) > 0)
    x = (x.withColumn(f"lev_{c}", F.when(both, 1 - F.levenshtein(l, r) / F.greatest(F.length(l), F.length(r))).otherwise(-1.0))
          .withColumn(f"eq_{c}", F.when(both, (l == r).cast("double")).otherwise(-1.0))
          .withColumn(f"sdx_{c}", F.when(both, (F.soundex(l) == F.soundex(r)).cast("double")).otherwise(-1.0)))
    feats += [f"lev_{c}", f"eq_{c}", f"sdx_{c}"]
x = VectorAssembler(inputCols=feats, outputCol="features").transform(x).select("a_id", "b_id", "rank", "features").cache()

tmap = spark.createDataFrame([(k, v) for k, v in truth.items()], "a_id string, t_id string")
x = x.join(tmap, "a_id", "left").withColumn("label", (F.col("b_id") == F.col("t_id")).cast("double")).fillna(0.0, ["label"]).cache()
n = x.count()
recall_k = x.filter("label = 1").count() / len(truth)
print(f"fields {len(FIELDS)} | candidates {n} ({args.k} per anchor) | blocking recall@{args.k} = {recall_k:.4f} | {time.time() - t0:.0f} s")

train = x.orderBy(F.xxhash64("a_id", "b_id")).limit(args.labels).cache()                                    # a fixed pseudo-random sample
model = GBTClassifier(featuresCol="features", labelCol="label", maxIter=60, maxDepth=3, seed=0).fit(train)
scored = model.transform(x).withColumn("p", vector_to_array("probability")[1])
best = (scored.withColumn("r", F.row_number().over(Window.partitionBy("a_id").orderBy(F.desc("p"), "b_id"))).filter("r = 1"))   # deterministic tie-break
for name, rule in (("nearest neighbour alone, always link", x.filter("rank = 1")), ("MLlib GBT on 400 labels, best candidate >= 0.5", best.filter("p >= 0.5"))):
    links_n = rule.count(); tp = rule.filter("label = 1").count()
    p, r = tp / max(links_n, 1), tp / len(truth)
    print(f"  {name:<50} links {links_n:>5} TP {tp:>5} FP {links_n - tp:>4} FN {len(truth) - tp:>4}  P {p:.4f} R {r:.4f} F1 {2 * p * r / (p + r):.4f}")
# --- checks asked for by the independent review -------------------------------------------------------------------
links = best.filter("p >= 0.5")
dup_b = links.groupBy("b_id").count().filter("count > 1").count()                       # two anchors claiming one partner
# enforce one-to-one: each B keeps only its highest-probability anchor
one = links.withColumn("rb", F.row_number().over(Window.partitionBy("b_id").orderBy(F.desc("p"), "a_id"))).filter("rb = 1")
n1, tp1 = one.count(), one.filter("label = 1").count()
# held-out anchors only: every anchor that contributed a training pair is removed from the score
held = links.join(train.select("a_id").distinct(), "a_id", "left_anti")
true_held = len(truth) - train.select("a_id").distinct().join(tmap, "a_id").count()
nh, tph = held.count(), held.filter("label = 1").count()
f = lambda tp, n, tot: 2 * tp / (n + tot) if n + tot else 0.0
print(f"  B records claimed by more than one anchor: {dup_b} | with one-to-one enforced: F1 {f(tp1, n1, len(truth)):.4f}")
print(f"  held-out anchors only (training anchors removed): links {nh} TP {tph} of {true_held} true -> F1 {f(tph, nh, true_held):.4f}")
print(f"labels {args.labels} ({train.filter('label = 1').count()} match) | gram cap {args.cap} | compute {time.time() - t0:.0f} s | wall incl. Spark start-up {time.time() - t_start:.0f} s")
spark.stop()

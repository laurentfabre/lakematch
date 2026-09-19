**1. My independent recommendation: D — adapt first, replace selectively**

The easiest credible production path is **Zingg as a batch matching task, SDP around its inputs and outputs, and MLflow tracking the complete matching system**. Investigate a PySpark replacement alongside that baseline; do not make replacement a prerequisite for integration.

I formed this recommendation before reading `PORTING.md`. Three source findings drive it:

- Zingg already saves and loads a standard Spark `CrossValidatorModel`. This is a useful integration boundary, not an opaque proprietary classifier. [SparkModel.java:136](/Users/lf/Tools/verify/zingg-porting/zingg-src/spark/core/src/main/java/zingg/spark/core/model/SparkModel.java:136)
- Its feature generation sits **outside** that persisted classifier. Adaptation therefore requires a complete artifact bundle, not merely `log_model`. [SparkModel.java:54](/Users/lf/Tools/verify/zingg-porting/zingg-src/spark/core/src/main/java/zingg/spark/core/model/SparkModel.java:54)
- The benchmark did not isolate blocking as either the recall bottleneck or the runtime bottleneck. Replacing several components simultaneously cannot establish which needed replacement. [ASTRA_REVIEW.md:111](/Users/lf/Tools/verify/zingg-porting/ASTRA_REVIEW.md:111)

My estimates are engineering judgments, in **person-weeks**, assuming experienced engineers, existing infrastructure and one defined matching domain:

| Approach | Production effort | Assessment |
|---|---:|---|
| Thin adaptation: existing JAR, orchestration, complete model tracking | **6–10** | Easiest first deployment; my recommended starting point for D. |
| PySpark replacement | **16–28** | Reasonable if eliminating Zingg dependencies or requiring native SDP inference is mandatory. |
| Zig replacement with distributed execution/integration | **32–52+** | Poor first choice for this target. A bounded local matcher is a different, smaller project. |

“Production-grade” must include reproducible model/configuration/label bundles; entity-disjoint evaluation; candidate recall and cluster metrics; agreed field and missing-value semantics; representative volume/skew tests; stable identities and merge/split reconciliation; retry-safe publication; monitoring, rollback and runtime compatibility tests. These estimates do **not** cover a general-purpose replacement for every Zingg feature.

**If Free Edition/serverless and eliminating Zingg dependencies are hard requirements, my recommendation changes to B**, subject to platform verification. The bundle does not establish those platform capabilities.

Everything below is based on read-only inspection. I did not rerun Spark jobs or verify Databricks documentation.

---

**2. Claim-by-claim verdict on `PORTING.md`**

Repeated claims are consolidated. **VERIFIED** means supported by source or explicitly identified supplied evidence; it does not imply a successful managed Databricks deployment. **UNVERIFIABLE OFFLINE** also covers missing benchmark artifacts and missing dependency documentation.

For compact source references below:

- `C/` = `zingg-src/common/core/src/main/java/zingg/common/core/`
- `S/` = `zingg-src/spark/core/src/main/java/zingg/spark/core/`
- `P/` = `pyspark-4.1.3/pipelines/`
- `M/` = `pyspark-4.1.3/ml/`

| PORTING claim | Verdict | Evidence / correction |
|---|---|---|
| **10–17:** adaptation cannot meet the target; PySpark is necessarily easiest | **WRONG** as a categorical conclusion | It conflates integration with putting the whole engine inside a flow. The standard model persistence supports a thin adapter: `S/model/SparkModel.java:136–167`. The paper itself acknowledges this alternative at 148–150. |
| **15–17:** the serverless/Free Edition compatibility matrix | **UNVERIFIABLE OFFLINE** | No managed-runtime evidence is supplied. Language, library and compute restrictions need separate verification. |
| **21–22:** approximately 19,000 Java/Scala lines, 1,400 Python; common/spark layering | **VERIFIED** with scope | Recount excluding tests/build outputs: common **14,225** lines; spark **4,613**; Python package **1,439**. Of 110 Spark-module source files, 84 contain `org.apache.spark`. No such import in common. Modules are declared at `zingg-src/pom.xml:26–29`. |
| **22:** common is Spark-independent | **VERIFIED** at the import boundary | Do not infer runtime independence: `C/similarity/function/ArrayDoubleSimilarityFunction.java:6` imports Scala collections. |
| **23:** existing Python wrapper drives JVM objects | **VERIFIED** | `zingg-src/python/zingg/client.py:47–52,537` uses `_jvm` and `_jsparkSession`. |
| **24:** `_jvm` is unavailable under Connect | **UNVERIFIABLE OFFLINE** from this subset | The complete Connect session implementation is absent. The supplied PRs nevertheless document a different, server-plugin integration route. |
| **25–27:** similarities, hashes and stopword removal use JVM UDFs | **VERIFIED** | `S/similarity/SparkSimFunction.java:7`; `S/hash/SparkHashFunction.java:17`; `S/preprocess/stopwords/RemoveStopWordsUDF.java:7`; registration at `S/util/SparkFnRegistrar.java:14,22`. |
| **25–27:** all blocking is registered UDF logic | **WRONG** if read that broadly | Tree application implements Dataset `MapFunction<Row,Row>`: `S/block/SparkBlockFunction.java:16`. |
| **28–29:** assembler → polynomial expansion → logistic regression → cross-validation | **VERIFIED** | `S/model/SparkModel.java:67–85,117–124`. |
| **29:** classifier is “portable as is” | **VERIFIED** only for its Spark persistence; **WRONG** for the complete matcher | Custom similarity features are outside the saved pipeline: `SparkModel.java:54–64,150–173`. Runtime/MLflow compatibility remains untested. |
| **30:** GraphFrames connected components | **VERIFIED** | `S/util/SparkGraphUtil.java:37–44`. |
| **31–32:** listed external dependencies | **VERIFIED** as declared dependencies | SecondString/FreeMarker: `common/core/pom.xml:17–25`; JavaMail: `common/client/pom.xml:11–15`; GraphFrames: `spark/pom.xml:91–95`; Commons/Jackson: root `pom.xml:183–205`. |
| **31:** those dependencies are present in an inspected fat JAR | **UNVERIFIABLE OFFLINE** | Dependency declarations do not verify packaged contents. The assembly module is declared, but its implementation/artifact is absent. |
| **33–37:** upstream is pursuing server-side Connect plugins | **VERIFIED** as supplied PR evidence | [PR1350:10–24](/Users/lf/Tools/verify/zingg-porting/upstream_PR1350_label_over_connect.md:10) names plugins, configuration and protobuf requirements. [PR1376:4–14](/Users/lf/Tools/verify/zingg-porting/upstream_PR1376_spark_connect.md:4) describes profiles and incomplete CI verification. |
| **33–36:** PR dates, chronology and #1382’s `regexp_replace` change | **UNVERIFIABLE OFFLINE** | Those dates and #1382 evidence are not supplied. |
| **41–45:** flow evaluation blocks analysis/actions, Spark ML fitting and UDF registration | **VERIFIED**, with two different scopes | RPC blocking surrounds `flow.func()` only: `P/spark_connect_graph_element_registry.py:114–120`. Session mutations are blocked throughout module execution: `P/cli.py:255–259`. |
| **41–45:** the RPC block also applies while the submitted plan executes | **WRONG**, if inferred | Methods are restored in `P/block_connect_access.py:80–86`; `start_run` follows definition registration in `P/cli.py:337–350`. |
| **42:** SQL commands receive an exception | **VERIFIED** | `P/block_connect_access.py:27–45,65–75`. This exception does not establish that arbitrary SQL side effects are supported. |
| **44–45:** anonymous Python/Pandas UDF expressions are prohibited | **WRONG**, if inferred | The blocked methods are registration methods, not `F.udf`/`F.pandas_udf`: `P/block_session_mutations.py:74–87`. Both probes completed: [SDP_PROBES.md:10](/Users/lf/Tools/verify/zingg-porting/SDP_PROBES.md:10). |
| **46–47:** Spark ML can fit over Connect | **VERIFIED** for the implemented path | `M/util.py:169–192` sends an ML fit command. This is not evidence that every estimator works on every managed runtime. |
| **47:** training must be in a Job task | **WRONG** as a technical necessity; sensible architecture | Module-level fitting is outside the RPC guard and reportedly succeeds: `SDP_PROBES.md:12`. Production training should still be separate from definition loading. |
| **48–49:** listed OSS pipeline APIs; no exported expectations API | **VERIFIED** | `P/__init__.py:17–33`. “Databricks-only” availability is **UNVERIFIABLE OFFLINE**. |
| **50–52:** serverless/SDP/Free Edition language, JAR, plugin and egress restrictions | **UNVERIFIABLE OFFLINE** | Verify each against the exact compute product/runtime. The referenced owner `CLAUDE.md` is not evidence supplied here. |
| **53–54:** MLflow APIs exist and `spark_udf` is the documented DLT/SDP route | **UNVERIFIABLE OFFLINE** | MLflow implementation/documentation is absent. |
| **55–56:** GraphFrames is an external dependency | **VERIFIED** | `zingg-src/spark/pom.xml:91–95`. Current governance and serverless availability are **UNVERIFIABLE OFFLINE**. |
| **60–61:** the unchanged Zingg program cannot simply become a lazy flow function | **VERIFIED** | Training calls `cv.fit`; inference includes registration; output strategies write results. Examples: `SparkModel.java:123,187–194`; `UnityCatalogWriterStrategy.java:23–26`. |
| **62–64:** classic Lakeflow JAR/spark-submit task availability | **UNVERIFIABLE OFFLINE** | Plausible proposed integration, not established platform support. Calling it “next to Lakeflow” does not make it fail the owner’s stated objective. |
| **65,137:** unchanged Zingg fails an allowed-library list limited to Spark/Delta/MLflow | **VERIFIED** | Its declared SecondString, FreeMarker, JavaMail and GraphFrames dependencies suffice. |
| **66–68:** adaptation requires rewriting exactly 4,600 lines plus every UDF | **WRONG** | The thin adapter preserves them. Even native inference may permit expression UDFs or selective replacement; no line-count-based necessity follows. |
| **69–71:** benchmark quality proves there is no design worth preserving | **WRONG** | [ASTRA_REVIEW.md:111–130](/Users/lf/Tools/verify/zingg-porting/ASTRA_REVIEW.md:111) explicitly rejects blocking causation and identifies evaluation limitations. |
| **15,69–71,86–88:** quoted comparative F1 values | **UNVERIFIABLE OFFLINE** as new reproductions | README corroborates reported Zingg/scikit-learn results at 129–136. The PySpark numbers lack supplied predictions/run logs. The earlier review reproduced different listed runs; it does not independently certify this new table. |
| **75:** serverless cannot load native libraries; MLflow has no Zig flavor | **UNVERIFIABLE OFFLINE** | Neither fact is established by this bundle. A missing dedicated flavor would not itself prove no integration route exists. |
| **11,75–77:** Zig has no role; a local matcher can be “dependency-free” | **WRONG** as an absolute / **UNVERIFIABLE OFFLINE** for the implementation claim | A native kernel or local engine is a legitimate design option. Parquet, execution and integration dependencies still need accounting. |
| **81:** prototype is 110 lines | **WRONG** for this bundle | [proto_spark_native.py](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:1) has **89** lines. Neither number estimates production effort. |
| **81–82,126:** prototype uses only Spark dependencies | **WRONG** literally | It imports NumPy and `recordlinkage`: `proto_spark_native.py:24–29`. Its distributed matching computation does use Spark expressions/ML. |
| **90:** 14 seconds includes Spark startup | **WRONG** for the printed timer | Session creation is line 41; `t0` is line 43. The 14-second observation itself is **UNVERIFIABLE OFFLINE**. |
| **90–91:** 400 ground-truth labels | **VERIFIED** | Truth supplies `label`; the 400-row sample feeds fitting: `proto_spark_native.py:74–81`. |
| **91:** perfect confident Jev labels make the gold-label experiment equivalent | **WRONG** as an inference | Confidence-selected labels and every gold-labelled sampled pair are different populations; `bench_pipeline.py:157–163` filters uncertain labels. |
| **93–95:** candidate and feature computations are lazy Spark expressions | **VERIFIED** | `proto_spark_native.py:47–71`; local pipeline completion is reported at `SDP_PROBES.md:14–15`. |
| **93–94:** the score is ordinary cosine over gram sets | **WRONG** without qualification | Shared grams are frequency-filtered, while `na`/`nb` count the unfiltered sets: `proto_spark_native.py:53–57`. It is a masked-overlap score with original norms. |
| **96–98:** native model transform is lazy; SDP needs pyfunc scoring | **VERIFIED** first clause; **WRONG** necessity | `M/util.py:216–268` constructs a lazy model relation. The native-transform probe completes: `SDP_PROBES.md:12`. Actual `mlflow.pyfunc.spark_udf` compatibility remains **UNVERIFIABLE OFFLINE**. |
| **99:** one-to-one linkage needs no further resolution | **WRONG** for this implementation | Selection is only per A-anchor. Multiple A records can select the same B: `proto_spark_native.py:83`. |
| **100–101:** iterative propagation can run as a task; fixed rounds suffice for components | **VERIFIED** as an algorithmic option; **WRONG** as an unconditional equivalence | A fixed number of rounds need not converge on an arbitrary graph. No clustering implementation or convergence validation is supplied. |
| **105–122:** proposed serverless pipelines, UC alias and Job orchestration work together | **UNVERIFIABLE OFFLINE** | This is a proposed deployment, not a demonstrated one. |
| **130–133:** Spark covers prototype computation | **VERIFIED** | `proto_spark_native.py:47–85`. MLflow/UC/Delta capability and integration assertions are **UNVERIFIABLE OFFLINE** from this bundle. |
| **134:** TF-IDF is “not built in”; SQL weighting is possible | **UNVERIFIABLE OFFLINE** for the blanket library claim | The supplied subset omits the standard feature catalog. SQL document-frequency weighting is a feasible expression design; it does not solve candidate explosion by itself. |
| **135:** Jev/`ai_query` licensing, availability and TypeSafe egress restriction | **UNVERIFIABLE OFFLINE** | Optional external labelling is a design choice; product and egress assertions need documentation/testing. |
| **144–145:** “3-gram self-join,” cap and proposed scale fix | **WRONG** on “self-join”; **VERIFIED** cap; **UNVERIFIABLE OFFLINE** scale adequacy | Code joins A to B and caps B-side gram frequency at 400: `proto_spark_native.py:53–59`. No million-record evidence supports IDF/LSH sufficiency. |
| **146–152:** defaults, synthetic one-to-one task, missing production functionality and possible easier adaptation | **VERIFIED** limitations | Configuration: `bench_febrl.py:60–69`; prototype sampling/output: `proto_spark_native.py:36–39,80–88`. These caveats substantially undermine the categorical opening. |

**The exact SDP boundary and the probes**

The source establishes this sequence:

1. The CLI imports a definition module under `block_session_mutations`.
2. The materialized-view decorator invokes registry registration. [api.py:264](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/pipelines/api.py:264)
3. The concrete registry invokes `flow.func()` under the Connect execution/analysis guard.
4. That guard exits; the returned plan is serialized and registered.
5. The CLI subsequently starts execution.

The abstract registry adds no separate prohibition. [graph_element_registry.py:30](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/pipelines/graph_element_registry.py:30)

Consequently:

- `fit`, `count` and analysis-dependent properties such as `columns` fail during flow evaluation.
- `spark.udf.register` is blocked even at module scope.
- Anonymous `F.udf` and `F.pandas_udf` expressions are allowed by these guards.
- **A compatible model loaded before flow evaluation can legally supply `model.transform(df)` in OSS SDP.** Standard remote loading itself sends a command, so loading *inside* the flow is different. [readwrite.py:256](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/ml/connect/readwrite.py:256)

**Every reported result in `SDP_PROBES.md` is consistent with this source.** However, its model probe fits at import; it does not demonstrate loading Zingg through MLflow. Model plans reference a cached server-side object, so restart/retry/session-lifetime behavior needs testing. [proto.py:48](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/ml/connect/proto.py:48)

**What adapting Zingg actually entails**

The thin path is real, but “log the Spark model” underspecifies it:

| Boundary | Concrete implication |
|---|---|
| Spark ML classifier | Native `CrossValidatorModel` persistence makes packaging straightforward; actual MLflow round-trip needs verification. |
| Feature computation | Preserve configuration, feature order, normalization and similarity implementations alongside the classifier. |
| `zinggDir` layout | Model artifacts use `<zinggDir>/<modelId>/model`; labels use `trainingData/marked` and `unmarked`; preprocessing uses **shared `<zinggDir>/preprocess`**. Isolate that shared state too. [SparkModelHelper.java:16](/Users/lf/Tools/verify/zingg-porting/zingg-src/spark/client/src/main/java/zingg/spark/client/util/SparkModelHelper.java:16) |
| Blocking tree | Stored as a Java-serialized object inside Parquet. Preserve compatible classes and version the tree; Parquet does not make its contents portable. [BlockingTreeUtil.java:87](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/util/BlockingTreeUtil.java:87) |
| `z_cluster` | Not a durable business identity. Match-mode components depend on generated record IDs; link-mode identifiers use a time-based prefix. Maintain a persistent crosswalk and reconciliation layer. [DFUtil.scala:21](/Users/lf/Tools/verify/zingg-porting/zingg-src/spark/client/src/main/scala/reifier/scala/DFUtil.scala:21), [DSUtil.java:71](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/client/src/main/java/zingg/common/client/util/DSUtil.java:71) |

An existing `saveAsTable` writer offers another integration seam, though its managed-runtime compatibility is unverified. [UnityCatalogWriterStrategy.java:23](/Users/lf/Tools/verify/zingg-porting/zingg-src/spark/client/src/main/java/zingg/spark/client/util/writer/impl/UnityCatalogWriterStrategy.java:23)

**Similarity and hash portability**

Most hash logic and much similarity logic are **SQL-composable**. That is different from having an exact one-function Spark replacement.

The bundle lacks the complete Spark SQL function catalog, so categorical absence of built-ins is **UNVERIFIABLE OFFLINE**. The concrete algorithms requiring nontrivial replacement—and for which I would not assume a built-in equivalent—are:

- `JaroWinklerFunction`, `AJaroWinklerFunction`, `SJaroWinkler`: the underlying implementation is actually **SecondString Jaro**, not Jaro–Winkler. [SJaroWinkler.java:5](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/similarity/function/SJaroWinkler.java:5)
- `AffineGapSimilarityFunction`, `SAffineGap`: underlying implementation is **Monge–Elkan**. [SAffineGap.java:5](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/similarity/function/SAffineGap.java:5)
- Their derived functions: `OnlyAlphabetsAffineGapSimilarity`, `EmailMatchTypeFunction`, and `SameFirstWordFunction`. The last extracts text before a **hyphen**, despite its name. `C/similarity/function/SameFirstWordFunction.java:59–65`.

The remaining families are substantially expressible through arithmetic, regexes, arrays and comparisons:

| Family | Functions / required work |
|---|---|
| Equality and missingness | `StringSimilarityFunction`, `SimilarityFunctionExact`, `OnlyAlphabetsExactSimilarity`, `CheckNullFunction`, `CheckBlankOrNullFunction`, `PinCodeMatchTypeFunction`. |
| Numeric/date | Integer, long, float, double and date similarity functions. Preserve the actual formulas. |
| Set similarities | `JaccSimFunction`/`SJacc`, `BigramJaccSimFn`/`BigramJaccard`, `NumbersJaccardFunction`, `ProductCodeFunction`. Reproduce tokenization and set construction. |
| Vector similarity | `ArrayDoubleSimilarityFunction`: cosine through array arithmetic. |
| Simple hashes | Prefix/suffix, last word, identity, null/empty and less-than-zero families. |
| Bespoke hashes without direct one-call substitutes | `First2CharsBox`, `First3CharsBox`, `Range{Dbl,Float,Int,Long}`, `TrimLastDigits{Dbl,Float,Int,Long}`, `Truncate{Double,Float}`, and Java-round semantics. These remain SQL-composable. |

The configured hash inventory is explicit in [hashFunctions.json:1](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/resources/hashFunctions.json:1). **None of those hash algorithms inherently requires a native extension.**

Exact parity is more work than replacing names: missing strings can score **1**; “only alphabets” removes digits and dots; truncation uses floor; Java rounding, division and string semantics require deliberate treatment. [StringSimilarityDistanceFunction.java:30](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/similarity/function/StringSimilarityDistanceFunction.java:30), [TruncateDouble.java:17](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/hash/TruncateDouble.java:17)

The blocking learner is not merely plumbing. It selects field/hash splits to minimize eliminated positive examples and recursively divides oversized blocks. Discarding it loses **learned, label-informed blocking behavior**. [Block.java:127](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/block/Block.java:127)

Its training sample is collected to the driver, which merits profiling; it does not establish the benchmark bottleneck. [BlockingTreeUtil.java:47](/Users/lf/Tools/verify/zingg-porting/zingg-src/common/core/src/main/java/zingg/common/core/util/BlockingTreeUtil.java:47)

**The prototype is useful evidence, but not a fair replacement trial**

- **Different supervision:** 400 random-ish gold-labelled candidate pairs versus Zingg’s active-learning rounds and smaller reported label budgets. Confident Jev labels being correct does not establish equivalent coverage.
- **Different output constraints:** best-per-anchor exploits the task structure and does not enforce right-side uniqueness. Probability ties also lack a deterministic secondary sort. [proto:80–85](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:80)
- **Training examples are scored:** no entity-disjoint holdout. The earlier review’s small measured leakage effect belongs to the earlier pipeline, not automatically this prototype. [ASTRA_REVIEW:120–130](/Users/lf/Tools/verify/zingg-porting/ASTRA_REVIEW.md:120)
- **Unexplained parameter selection:** `400` is hard-coded with no selection history or sensitivity study. It might be innocent engineering judgment; the bundle cannot establish that it was chosen without test feedback.
- **Different retrieval algorithm:** masked binary-gram overlap replaces the earlier character TF-IDF retrieval. This is not simply the same system translated to Spark. Compare [proto:47–60](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:47) with [bench_pipeline:132–147](/Users/lf/Tools/verify/zingg-porting/bench_pipeline.py:132).
- **Timing mismatch:** the timer excludes dataset loading, partner removal and Spark startup. It includes subsequent DataFrame preparation, materialization, fitting and several scoring actions; the final label-count action and shutdown occur after the timestamp is evaluated. [proto:36–43](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:36), [proto:76–89](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:76)

For scaling, the intermediate join size is proportional to:

\[
\sum_{\text{retained grams }g} n_A(g)\,n_B(g)
\]

Top-k is applied **after** that expansion. Keeping `n_B(g) ≤ 400` bounds each posting-list contribution, but can still yield hundreds of billions of intermediate rows at large volume. Keeping the cap fixed also discards more useful grams as the corpus grows.

At \(10^7\) records, my Spark-native candidate design would combine multiple selective field blocks with a partitioned rare-token/gram inverted index, explicit candidate budgets and measured recall. **MinHashLSH for set similarity** is another candidate to investigate, not a guaranteed scalable substitute for cosine retrieval; its exact API/runtime support is unverified here. IDF weighting alone does not reduce join cardinality unless accompanied by pruning.

**The dependency answer needs two definitions**

The benchmark imports NumPy to choose removed partners and `recordlinkage` to load FEBRL data; those direct benchmark dependencies can be removed from production ingestion. [proto:24–39](/Users/lf/Tools/verify/zingg-porting/proto_spark_native.py:24)

But “no non-Databricks dependencies whatsoever” is a different—and unsupported—claim. The supplied PySpark implementation itself imports NumPy, Pandas, Arrow and other libraries in relevant paths; see [ml/tuning.py:39](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/ml/tuning.py:39) and [ml/connect/feature.py:20](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/ml/connect/feature.py:20).

A defensible objective is **no additional third-party matching engine beyond the supported platform stack**. Production still needs application code for labelling, identities, reconciliation, audit and operations. An LLM service is optional. Whether additional packages are necessary depends on the chosen UI, connectors and required similarity parity.

---

**3. The strongest three arguments against its conclusion**

1. **It dismisses the cheapest valid interpretation of “adapt.”** A batch task with SDP input/output contracts and complete MLflow artifacts need not become a lazy flow. The existing Spark model persistence makes this a concrete option.

2. **Its architectural restriction is overstated.** The source and probes permit anonymous UDF expressions and compatible native Spark ML inference. “Every UDF must become SQL” and “scoring needs pyfunc” do not follow.

3. **Its benchmark does not justify discarding Zingg’s algorithms.** Supervision, features, retrieval and output selection all change; training pairs remain in evaluation; the gram cutoff is unexplained; scale is untested. The earlier review specifically rejected identifying the blocker as the cause.

---

**4. What I would change in the proposed Lakeflow shape**

I would separate routine inference from model development:

1. **SDP prepares versioned input tables.**
2. **An imperative matching task initially runs Zingg**, consuming a pinned input snapshot and complete versioned model bundle.
3. **A reconciliation task publishes durable entities and crosswalks**, with merge/split history and retry-safe commits.
4. **SDP publishes downstream views.**
5. **A separate labelling/training/evaluation workflow promotes models** only after candidate, pair and cluster-quality gates pass.

For a validated PySpark replacement, move compatible lazy inference into SDP using a model loaded before flow evaluation. Keep batch inference as a fallback. Treat managed support as **UNVERIFIABLE OFFLINE** until tested.

I would also change these details:

- Resolve `@champion` to an immutable version for each run; record input, feature, blocker, classifier and decision-policy versions together.
- Do not retrain merely because the inference pipeline refreshes.
- Replace “best candidate” with an explicit cardinality policy: unrestricted linkage, many-to-one, or genuine one-to-one assignment.
- Require convergence for connected components; do not silently publish a fixed-round approximation.
- Retain the learned blocker as a baseline. An intermediate option is to **export its learned tree as declarative rules and compile inference to SQL**, while retaining the existing learner. This is a proposal requiring parity tests.
- Consider Zig only after profiling identifies an expensive similarity kernel, or for the owner’s separate local engine. Its potential value is not evidence that a distributed rewrite is worthwhile.

The paper mentions several omissions at the end but does not incorporate their cost. It also fails to analyze:

- The distinction between **pair prediction and durable entity identity**.
- Deletes, corrections, late records, rematching, cluster splits and incremental/full-refresh equivalence.
- Complete-model provenance, feature parity and session-bound model references.
- Compute/storage/shuffle cost, skew, failure recovery and representative \(10^7\)-record tests.
- Supported languages, multi-valued fields and Unicode/missing-value semantics.
- Licensing and maintenance tradeoffs: the source declares **AGPL v3**, which deserves an explicit review rather than being absent from the decision. [pom.xml:11](/Users/lf/Tools/verify/zingg-porting/zingg-src/pom.xml:11)
- The distinction between standard `pyspark.ml` Connect support and the separate `pyspark.ml.connect` estimator implementation, whose logistic regression is marked deprecated. [classification.py:147](/Users/lf/Tools/verify/zingg-porting/pyspark-4.1.3/ml/connect/classification.py:147)

---

**5. Open questions to verify online**

Every managed-platform item below is **UNVERIFIABLE OFFLINE**:

| Check | Required evidence |
|---|---|
| Exact deployment target | Classic Jobs, serverless Jobs, managed SDP and Free Edition must be evaluated separately. |
| Thin adaptation | A minimal JAR task on the intended compute, reading/writing the intended catalog/storage with retries. |
| Spark/Scala/Java compatibility | Build and smoke-test against the actual runtime; the bundled Spark 4.1.3 profile is configuration, not certification. |
| Native inference in managed SDP | Load a saved compatible model outside the flow, transform inside it, then test refresh, restart and retry. |
| MLflow round-trip | Log/reload Zingg’s saved classifier and complete supporting artifacts; compare scores and feature order exactly. |
| Pyfunc alternative | Verify supported Spark-model flavor behavior, probability output, dependencies and flow compatibility. |
| UDF/native-library support | Test anonymous Python/Pandas UDFs and any proposed Zig wheel/kernel on the exact compute. |
| GraphFrames and Connect extensions | Current availability, installation/configuration rules and upstream compatibility reports. |
| UC/Delta orchestration | Model-version pinning, permissions, publication semantics and model-change-triggered recomputation. |
| Labeller access | Actual TypeSafe egress and `ai_query` availability; do not infer either from “serverless.” |
| Library inventory | Confirm current SQL similarity functions and MLlib TF-IDF/LSH support; inspect the resolved dependency graph. |

The next empirical comparison should use the **same labels, entity-disjoint evaluation, output constraints and timing boundaries**, and separately measure candidate recall, scoring quality, clustering quality and cost.

```text
/goal Verify the exact Databricks runtime and compute support for the thin Zingg adapter and native Spark ML inference in SDP, then specify a controlled adapter-versus-PySpark benchmark.
```


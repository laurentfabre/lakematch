"""Generate this report's local figures from preserved campaign evidence."""
from pathlib import Path
import hashlib
import html
import json
import os
import re
import shutil
from decimal import Decimal, ROUND_HALF_UP

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = HERE / "assets"
ASSETS.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(HERE / ".mpl-cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

DARK = "#183B3F"
GREEN = "#167A60"
MINT = "#E6F3ED"
TEAL = "#467D88"
BLUE = "#EAF0F5"
MUTED = "#5F7478"
CORAL = "#C35339"
PALE = "#FBEEE8"
LINE = "#CDDCD9"


def svg_start(h):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{h}" viewBox="0 0 1000 {h}">',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#5F7478"/></marker></defs>',
            '<style>text {font-family:"DM Sans",sans-serif;fill:#183B3F;} .small {font-size:20px;} .title {font-size:25px;font-weight:700;} .muted {fill:#5F7478;}</style>']


def text(parts, x, y, lines, size=22, weight=400, color=DARK, line_height=31, anchor="start"):
    for i, line in enumerate(lines if isinstance(lines, list) else [lines]):
        parts.append(f'<text x="{x}" y="{y+i*line_height}" font-size="{size}" font-weight="{weight}" fill="{color}" style="fill:{color}" text-anchor="{anchor}">{html.escape(line)}</text>')


def box(parts, x, y, w, h, fill=MINT, stroke=LINE, radius=16):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')


def arrow(parts, x1, y1, x2, y2, dashed=False):
    dash = 'stroke-dasharray="8 6"' if dashed else ''
    parts.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#arrow)" {dash}/>')


def save_svg(name, parts):
    (ASSETS / name).write_text("\n".join(parts + ["</svg>"]), encoding="utf-8")


# A schematic cover image, explicitly conceptual rather than a product screenshot.
p = svg_start(330)
for x, y, label in [(30, 34, "Record A"), (30, 140, "Record B"), (30, 246, "Record C")]:
    box(p, x, y, 230, 65, "#FFFFFF")
    text(p, x+26, y+42, label, size=24, weight=700)
    arrow(p, 274, y+33, 396, 165)
box(p, 407, 110, 190, 110, GREEN, GREEN)
text(p, 502, 154, ["LakeMatch", "compare + link"], size=23, color="#FFFFFF", anchor="middle")
arrow(p, 611, 165, 719, 165)
box(p, 734, 78, 235, 174, MINT)
text(p, 850, 124, "Shared identity", size=25, weight=700, anchor="middle")
text(p, 850, 172, ["Original records", "+ decision history"], size=23, anchor="middle")
save_svg("cover.svg", p)

# A fictional record schema. This does not assert a scored result.
p = svg_start(430)
for y, title, name, address in [(12, "SYSTEM A · RECORD A-17", "Maya Laurent", "14 Willow Road"), (223, "SYSTEM B · RECORD B-92", "M. Laurent", "14 Willow Rd")]:
    box(p, 10, y, 410, 175, "#FFFFFF")
    text(p, 34, y+36, title, size=19, weight=700, color=GREEN)
    text(p, 34, y+82, name, size=29, weight=700)
    text(p, 34, y+123, address, size=24)
    text(p, 34, y+154, "Fictional example", size=18, color=MUTED)
arrow(p, 434, 98, 571, 174)
arrow(p, 434, 310, 571, 231)
box(p, 587, 117, 402, 203, MINT)
text(p, 612, 157, "IF THE MATCH IS ACCEPTED", size=19, weight=700, color=GREEN)
text(p, 612, 203, "Shared identity E-104", size=29, weight=700)
text(p, 612, 247, ["A-17 → E-104", "B-92 → E-104"], size=24)
text(p, 500, 424, "Links connect the source records; a saved history records later changes.", size=22, anchor="middle")
save_svg("record-schema.svg", p)

p = svg_start(480)
steps = [
    (10, 12, "1  CHECK", ["Standardize formats", "Set bad rows aside"]),
    (350, 12, "2  SHORTLIST", ["Find plausible pairs", "Limit comparison work"]),
    (690, 12, "3  COMPARE", ["Names, dates, addresses", "Rare words add evidence"]),
    (690, 238, "4  SCORE", ["Use a trained model", "Apply a decision rule"]),
    (350, 238, "5  LINK", ["Keep accepted pairs", "Respect matching rules"]),
    (10, 238, "6  GROUP & TRACK", ["Create shared identities", "Record changes over time"]),
]
for x, y, title, lines in steps:
    box(p, x, y, 300, 151, MINT if "6 " in title else "#FFFFFF")
    text(p, x+20, y+39, title, size=23, weight=700, color=GREEN)
    text(p, x+20, y+86, lines, size=22)
arrow(p, 317, 89, 341, 89)
arrow(p, 657, 89, 681, 89)
arrow(p, 840, 170, 840, 227)
arrow(p, 681, 315, 660, 315)
arrow(p, 341, 315, 320, 315)
box(p, 115, 420, 770, 51, BLUE, BLUE)
text(p, 500, 453, "Human decisions can feed a later, separately validated training run.", size=21, anchor="middle")
save_svg("matching-workflow.svg", p)

p = svg_start(295)
labels = [(12, "LEARN", ["Examples with", "known answers"]), (270, "CHOOSE", ["Compare options", "on validation data"]), (528, "FREEZE", ["Lock the model", "and its rules"]), (786, "CHECK", ["Score the reserved", "confirmation data"])]
for x, title, lines in labels:
    box(p, x, 33, 200, 153, MINT if title == "FREEZE" else "#FFFFFF")
    text(p, x+100, 73, title, size=23, weight=700, color=GREEN, anchor="middle")
    text(p, x+100, 119, lines, size=21, anchor="middle")
for x in [222,480,738]: arrow(p, x, 108, x+36, 108)
box(p, 90, 225, 820, 54, BLUE, BLUE)
text(p, 500, 260, "Record the configuration, inputs, results and failures at every step.", size=22, anchor="middle")
save_svg("evidence-workflow.svg", p)

p = svg_start(360)
box(p, 15, 15, 420, 145, "#FFFFFF")
text(p, 39, 55, "LAPTOP · VERIFIED", size=23, weight=700, color=GREEN)
text(p, 39, 100, ["Local matching, models and review app", "Offline engine after preparation"], size=21)
box(p, 565, 15, 420, 145, "#FFFFFF")
text(p, 589, 55, "DATABRICKS · MEASURED", size=23, weight=700, color=GREEN)
text(p, 589, 100, ["Serverless matching and model reload", "Cloud review app still incomplete"], size=21)
arrow(p, 225, 173, 343, 221)
arrow(p, 775, 173, 657, 221)
box(p, 180, 230, 640, 114, MINT)
text(p, 500, 272, "ONE MATCHING ENGINE", size=25, weight=700, anchor="middle")
text(p, 500, 310, "The same comparison logic and saved decision rules", size=22, anchor="middle")
save_svg("platform-schema.svg", p)

# Fonts are distributed with the report, including their OFL license.
for filename in ["dm-sans-regular.ttf", "dm-sans-bold.ttf", "dm-sans-medium.ttf", "dm-sans-italic.ttf", "OFL.txt"]:
    if not (ASSETS / filename).is_file():
        raise FileNotFoundError(f"Missing packaged report font resource: {filename}")
for filename in ["dm-sans-regular.ttf", "dm-sans-bold.ttf"]:
    font_manager.fontManager.addfont(str(ASSETS / filename))
plt.rcParams.update({"font.family":"DM Sans", "font.size":12, "text.color":DARK,
                     "axes.labelcolor":MUTED, "xtick.color":MUTED, "ytick.color":DARK,
                     "svg.fonttype":"path", "axes.spines.top":False, "axes.spines.right":False})

rows=[]
for line in (ROOT / "bench/BENCHMARKS.md").read_text().splitlines():
    if not line.startswith("| ") or " / " not in line:
        continue
    cells=[v.strip() for v in line.strip("|").split("|")]
    if len(cells) < 9:
        continue
    if cells[0].endswith(" / valid"):
        continue
    m=re.fullmatch(r"([\d.]+) \[([\d.]+), ([\d.]+)\]", cells[3])
    if m:
        f1,lo,hi=map(float,m.groups())
        rows.append({"dataset":cells[0],"precision":float(cells[1]),"recall":float(cells[2]),"f1":f1,"ci":[lo,hi],"seconds":float(cells[5])})
assert len(rows)==8
display_names=["People · all fields (FEBRL)","People · ID hidden (FEBRL)","Business partners (BPID)","Products · Abt–Buy","Products · Amazon–Google","Products · Walmart–Amazon","Publications · DBLP–ACM","Organizations · Affiliations"]
fig,ax=plt.subplots(figsize=(10,4.95))
fig.subplots_adjust(left=.365,right=.91,top=.96,bottom=.14)
for i,(r,name) in enumerate(zip(rows,display_names)):
    y=7-i
    ax.barh(y,r["f1"]*100,height=.43,color=GREEN if i<2 else TEAL,zorder=2)
    ax.errorbar(r["f1"]*100,y,xerr=[[(r["f1"]-r["ci"][0])*100],[(r["ci"][1]-r["f1"])*100]],color=DARK,capsize=4,linewidth=1.2,zorder=3)
    display = (Decimal(str(r["f1"])) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    ax.text(111,y,str(display),ha="right",va="center",weight="bold",fontsize=13)
ax.set_yticks(list(range(7,-1,-1)),display_names,fontsize=12)
ax.set_xlim(0,100)
ax.set_xticks([0,25,50,75,100])
ax.set_xlabel("F1 score on a 0–100 scale  ·  higher is better",labelpad=10)
ax.grid(axis="x",color=LINE,linewidth=.7,zorder=0)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color(LINE)
ax.tick_params(axis="both",length=0,pad=9)
fig.savefig(ASSETS/"quality-results.svg",facecolor="white",bbox_inches="tight")
plt.close(fig)

scale=[]
for line in (ROOT/"bench/SCALE.md").read_text().splitlines():
    if re.match(r"\| \d+ \|",line):
        c=[v.strip() for v in line.strip("|").split("|")]
        scale.append({"records":int(c[0]),"seconds":float(c[6].split()[0]),"recall":None if c[4]=="unavailable" else float(c[4]),"f1":None if c[5]=="unavailable" else float(c[5]),"completed":"failed" not in c[6]})
fig,ax=plt.subplots(figsize=(10,3.15))
fig.subplots_adjust(left=.11,right=.99,top=.83,bottom=.18)
bars=ax.bar([0,1,2],[x["seconds"]/60 for x in scale[:3]],width=.47,color=[TEAL,TEAL,GREEN])
for bar,r in zip(bars,scale):
    ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+.20,f'{r["seconds"]:.2f} sec',ha="center",weight="bold",fontsize=13)
ax.set_xticks([0,1,2],["1,000 records","10,000 records","100,000 records"])
ax.set_ylim(0,6.6)
ax.set_yticks([0,2,4,6])
ax.set_ylabel("Elapsed minutes")
ax.grid(axis="y",color=LINE,linewidth=.7,zorder=0)
ax.set_axisbelow(True)
ax.spines["left"].set_visible(False)
ax.spines["bottom"].set_color(LINE)
ax.tick_params(axis="both",length=0,pad=8)
fig.savefig(ASSETS/"scale-results.svg",facecolor="white",bbox_inches="tight")
plt.close(fig)

from PIL import Image
screens=[]
for source_name,target_name,crop in [("review-desktop.png","review-screen.png",(250,90,1410,915)),("statistics-desktop.png","statistics-screen.png",(250,90,1410,815))]:
    source=ROOT/"data/app-acceptance-v1"/source_name
    Image.open(source).crop(crop).save(ASSETS/target_name,optimize=True)
    screens.append({"source":str(source.relative_to(ROOT)),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"output":"assets/"+target_name,"crop":crop,"alteration":"Content crop only; no values or UI elements altered."})

source_paths=["goal.md","README.md","bench/BENCHMARKS.md","bench/SCALE.md","bench/METHODS.md","bench/FEATURES.md","bench/IDENTITY.md","bench/CLUSTERS.md","bench/MODELS.md","bench/SERVERLESS.md","bench/PHOTON.md","bench/APP.md","bench/BLOCKERS.md","experiments/app-acceptance-20260920.json","experiments/app-final-20260920/browser-report.json","experiments/app-resource-cleanup-20260920.json"]
facts={"source_commit":"910a4188e2ff11088ac55601494b4e0730f74c70","evidence_date":"2026-09-20","quality":rows,"scale":scale,"screenshots":screens,"source_checksums":{str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths}}
(HERE/"figure-sources.json").write_text(json.dumps(facts,indent=2)+"\n")
print(f"Created diagrams, measured charts and two cropped screenshots in {ASSETS}")

# Matplotlib emits trailing path-data spaces; keep generated sources Git-clean.
for svg in ASSETS.glob("*.svg"):
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")

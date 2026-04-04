"""
Generate profiling charts from profile/results/.
Outputs PNG files to profile/results/.
"""
import glob
import pstats

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

RESULTS = "profile/results"


# ── 1. stats.csv: CPU and memory time-series ─────────────────────────────────

df = pd.read_csv(f"{RESULTS}/stats.csv", parse_dates=["timestamp"])
df = df[df["container"].str.contains("go-fetch")]  # skip infra noise
df["container"] = df["container"].str.replace("go-fetch-", "").str.replace("-1", "")

fig, (ax_cpu, ax_mem) = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
fig.suptitle("Container resource usage during load test", fontsize=13)

for name, grp in df.groupby("container"):
    ax_cpu.plot(grp["timestamp"], grp["cpu_pct"], label=name, linewidth=1.5)
    ax_mem.plot(grp["timestamp"], grp["mem_mb"], label=name, linewidth=1.5)

ax_cpu.set_ylabel("CPU %")
ax_cpu.yaxis.set_major_formatter(ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax_cpu.legend(fontsize=9)
ax_cpu.grid(True, alpha=0.3)

ax_mem.set_ylabel("Memory MB")
ax_mem.legend(fontsize=9)
ax_mem.grid(True, alpha=0.3)
ax_mem.tick_params(axis="x", rotation=30)

plt.tight_layout()
plt.savefig(f"{RESULTS}/resource_usage.png", dpi=150)
plt.close()
print("Saved resource_usage.png")


# ── 2. Worker: stacked bar — time per phase across all tasks ─────────────────

# Buckets that matter
def match_func(key, fragment):
    """Match against filename or function name in the pstats key tuple (file, lineno, func)."""
    filename, _, func = key
    return fragment in filename or fragment in func

BUCKETS = {
    "linear (BERT weights)":    "torch._C._nn.linear",
    "layer_norm":               "torch.layer_norm",
    "attention":                "torch._C._nn.scaled_dot_product_attention",
    "gelu activation":          "torch._C._nn.gelu",
    "embedding lookup":         "torch.embedding",
    "pooling":                  "sentence_transformers/models/Pooling.py",
    "PDF extraction":           "pymupdf._extra.page_get_textpage",
    "tokenizer":                "encode_batch",
    "MongoDB / network":        "recv_into",
}

files = sorted(f for f in glob.glob(f"{RESULTS}/worker_*.prof") if "merged" not in f)
task_labels, rows = [], []

for i, fpath in enumerate(files, 1):
    task_labels.append(f"task {i}")
    stats = pstats.Stats(fpath)
    ps = stats.stats  # {(file, lineno, func): (cc, nc, tt, ct, callers)}
    row = {}
    accounted = 0.0
    for label, fragment in BUCKETS.items():
        total = sum(v[2] for k, v in ps.items() if match_func(k, fragment))
        row[label] = round(total, 2)
        accounted += total
    total_time = sum(v[2] for v in ps.values())
    row["other"] = round(max(total_time - accounted, 0), 2)
    rows.append(row)

wdf = pd.DataFrame(rows, index=task_labels)

fig, ax = plt.subplots(figsize=(13, 6))
wdf.plot(kind="bar", stacked=True, ax=ax, colormap="tab10", width=0.7)
ax.set_title("Worker task time breakdown (tottime per phase, 10 tasks)", fontsize=13)
ax.set_ylabel("Seconds")
ax.set_xlabel("Task")
ax.tick_params(axis="x", rotation=0)
ax.legend(loc="upper right", fontsize=8, ncol=2)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(f"{RESULTS}/worker_breakdown.png", dpi=150)
plt.close()
print("Saved worker_breakdown.png")


# ── 3. Pie — aggregate worker time by phase ──────────────────────────────────

agg = wdf.sum()
agg = agg[agg > 0.5]  # drop negligible slices

fig, ax = plt.subplots(figsize=(8, 8))
wedges, texts, autotexts = ax.pie(
    agg,
    labels=agg.index,
    autopct=lambda p: f"{p:.1f}%" if p > 2 else "",
    startangle=140,
    pctdistance=0.8,
)
for t in autotexts:
    t.set_fontsize(9)
ax.set_title("Worker CPU time — aggregate over 10 tasks", fontsize=13)
plt.tight_layout()
plt.savefig(f"{RESULTS}/worker_pie.png", dpi=150)
plt.close()
print("Saved worker_pie.png")


# ── 4. App.prof: bar chart of non-idle top functions ─────────────────────────

app_stats = pstats.Stats(f"{RESULTS}/app.prof")
ps = app_stats.stats

SKIP = {"poll", "acquire", "exec", "__build_class__"}
rows_app = []
for (f, lineno, func), (cc, nc, tt, ct, _callers) in ps.items():
    if any(s in func for s in SKIP):
        continue
    if tt < 0.05:
        continue
    short = func if len(func) < 45 else "..." + func[-42:]
    rows_app.append({"func": short, "tottime": round(tt, 3), "calls": nc})

app_df = pd.DataFrame(rows_app).sort_values("tottime", ascending=False).head(20)

fig, ax = plt.subplots(figsize=(13, 7))
bars = ax.barh(app_df["func"][::-1], app_df["tottime"][::-1], color="steelblue")
ax.set_xlabel("tottime (s)")
ax.set_title("Flask process — top 20 functions by CPU time\n(idle poll/lock/exec excluded)", fontsize=12)
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig(f"{RESULTS}/app_hotspots.png", dpi=150)
plt.close()
print("Saved app_hotspots.png")

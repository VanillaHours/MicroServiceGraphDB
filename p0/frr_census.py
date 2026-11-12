"""FRR P0 census: TUs, LOC, file types, framework-macro inventory.
Outputs: census.json + CENSUS.md + census chart ($MSG_PUB/p0/)."""
import json, os, re, collections

import os  # portability: workspace root via MSG_ROOT
ROOT = os.environ.get("MSG_ROOT", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
SRC = f"{ROOT}/src/frr-10.7.1"
OUT = os.environ.get("MSG_PUB", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")) + "/p0"
SLICE = ["lib", "zebra", "bgpd", "staticd", "ospfd"]

# ── walk ──────────────────────────────────────────────────────────────
ext_files = collections.Counter()
loc_by_dir = collections.Counter()
c_by_dir = collections.Counter()
defun_by_dir = collections.Counter()
zcli_assign_by_dir = collections.Counter()
zcli_send = collections.Counter()
nb_cb_files = set()
yang_files, yang_lines = 0, 0
total_loc = 0

re_defun = re.compile(r"\bDEFUN(?:_NOSH|_HIDDEN|_DEPRECATED)?\b")
re_zassign = re.compile(r"\bzclient(?:_t)?->[a-zA-Z0-9_]+\s*=")
re_zsend = re.compile(r"\bzclient_send_([a-zA-Z0-9_]+)")
re_nbcb = re.compile(r"\bnb_cb_[a-z_]+")

for root, dirs, files in os.walk(SRC):
    dirs[:] = [d for d in dirs if d not in (".git", "build")]
    rel = os.path.relpath(root, SRC)
    top = rel.split(os.sep)[0] if rel != "." else "."
    for f in files:
        path = os.path.join(root, f)
        ext = os.path.splitext(f)[1].lower() or "(none)"
        ext_files[ext] += 1
        if f.endswith(".yang"):
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
                yang_files += 1
                yang_lines += text.count("\n") + 1
            except OSError:
                pass
        if ext in (".c", ".h", ".y", ".l", ".py", ".cpp"):
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            n = text.count("\n") + 1
            total_loc += n
            loc_by_dir[top] += n
            if ext == ".c":
                c_by_dir[top] += 1
            if top in SLICE:
                defun_by_dir[top] += len(re_defun.findall(text))
                zcli_assign_by_dir[top] += len(re_zassign.findall(text))
                for m in re_zsend.finditer(text):
                    zcli_send[m.group(1)] += 1
                if re_nbcb.search(text):
                    nb_cb_files.add(os.path.relpath(path, SRC))

# ── chart: LOC ranking, slice highlighted ─────────────────────────────
import matplotlib
import matplotlib.pyplot as plt
plt.rcParams.update({
    "font.sans-serif": ["DejaVu Sans"], "axes.unicode_minus": False,
    "figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
    "axes.edgecolor": "#E5E7EB", "axes.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "axes.titlesize": 15, "axes.titleweight": "bold", "axes.titlepad": 14,
    "legend.frameon": False, "figure.dpi": 200, "savefig.dpi": 200,
    "savefig.facecolor": "#FFFFFF", "savefig.pad_inches": 0.3,
})
G200, G400, G900, C_BLUE = "#E5E7EB", "#9CA3AF", "#111827", "#3B82F6"

items = sorted(loc_by_dir.items(), key=lambda kv: kv[1])
labels = [k for k, _ in items][-18:]
values = [v for _, v in items][-18:]
colors = [C_BLUE if l in SLICE else G200 for l in labels]

fig, ax = plt.subplots(figsize=(10, max(6, len(labels) * 0.42)))
bars = ax.barh(range(len(labels)), values, color=colors, height=0.62,
               zorder=3, edgecolor="white", linewidth=0.3)
mx = max(values)
for i, (bar, val) in enumerate(zip(bars, values)):
    hl = labels[i] in SLICE
    ax.text(bar.get_width() + mx * 0.01, bar.get_y() + bar.get_height() / 2,
            f"{val:,}", va="center", fontsize=9,
            color=G900 if hl else G400, fontweight="bold" if hl else "normal")
ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels)
ax.set_title("FRR 10.7.1 — source lines by component (POC slice highlighted)",
             loc="left")
ax.set_xlim(0, mx * 1.15)
ax.spines["bottom"].set_visible(False)
ax.xaxis.set_visible(False)
os.makedirs(OUT, exist_ok=True)
fig.savefig(f"{OUT}/census_loc.png", facecolor="white")
plt.close(fig)

# ── outputs ───────────────────────────────────────────────────────────
summary = {
    "tarball": "frr-10.7.1.orig.tar.xz (Debian pool, = upstream tag frr-10.7.1)",
    "sha256": "b8fd6590f0f53ccd661e8c3e3a0d997f9014b62c8ed03a42e51e93291373ae52",
    "total_c_files": sum(c_by_dir.values()),
    "total_loc_code_files": total_loc,
    "yang_files": yang_files, "yang_lines": yang_lines,
    "nb_cb_touching_files": sorted(nb_cb_files)[:40],
    "slice_defun": dict(defun_by_dir),
    "slice_zclient_handler_assignments": dict(zcli_assign_by_dir),
    "zclient_send_calls_unique": len(zcli_send),
    "zclient_send_top": zcli_send.most_common(12),
    "ext_top": ext_files.most_common(15),
    "loc_top": loc_by_dir.most_common(12),
    "c_top": c_by_dir.most_common(12),
}
os.makedirs(OUT, exist_ok=True)
json.dump(summary, open(f"{OUT}/census.json", "w"), indent=1)

lines = []
A = lines.append
A("# P0 — FRR 10.7.1 Repository Census")
A("")
A(f"Pinned source: `{summary['tarball']}`  ")
A(f"sha256: `{summary['sha256']}`")
A("")
A("## Headline numbers")
A("")
A(f"- **{summary['total_c_files']}** `.c` translation units")
A(f"- **{summary['total_loc_code_files']:,}** lines across code-bearing files (c/h/y/l/py)")
A(f"- **{yang_files}** YANG models, **{yang_lines:,}** lines (the compile-time contract plane)")
A(f"- **{len(nb_cb_files)}** files reference `nb_cb_*` northbound callbacks (runtime handler tables)")
A(f"- **{summary['zclient_send_calls_unique']}** unique `zclient_send_*` message types on the ZAPI plane")
A("")
A("## POC slice — framework touchpoints")
A("")
A("| component | DEFUN (CLI cmds) | zclient handler assignments (runtime table) |")
A("|---|---|---|")
for d in SLICE:
    A(f"| `{d}` | {defun_by_dir.get(d,0)} | {zcli_assign_by_dir.get(d,0)} |")
A("")
A("`zclient handler assignments` are the `zclient->*_cb = fn` sites — the literal "
  "runtime handler tables our `zapi_reg` extractor will match. `DEFUN` blocks are "
  "the CLI surface the northbound retrofits expose through YANG.")
A("")
A("## Top components by LOC")
A("")
A("| component | LOC | .c files |")
A("|---|---|---|")
for d, v in summary["loc_top"][:12]:
    A(f"| `{d}` | {v:,} | {c_by_dir.get(d,0)} |")
A("")
A("![LOC by component](census_loc.png)")
A("")
A("## Top ZAPI message producers (`zclient_send_*`, all dirs)")
A("")
A("| message | call sites |")
A("|---|---|")
for m, n in summary["zclient_send_top"]:
    A(f"| `zclient_send_{m}` | {n} |")
A("")
A("## File-type census (top 15)")
A("")
A("| ext | files |")
A("|---|---|")
for e, n in summary["ext_top"]:
    A(f"| `{e}` | {n} |")
open(f"{OUT}/CENSUS.md", "w").write("\n".join(lines) + "\n")
print(f"census -> {OUT}/CENSUS.md")
print(f"total .c={summary['total_c_files']}  loc={total_loc:,}  yang={yang_files}  "
      f"nb_cb files={len(nb_cb_files)}  zapi msg types={summary['zclient_send_calls_unique']}")

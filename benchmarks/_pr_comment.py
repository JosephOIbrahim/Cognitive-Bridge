"""Render output.json (pytest-benchmark) as a markdown table for the PR comment.

Used only by the Benchmarks workflow on pull_request events. Not a test — the
leading underscore keeps pytest from collecting it.
"""

import json

with open("output.json") as f:
    data = json.load(f)

lines = [
    "<!-- cb-benchmarks -->",
    "### 📊 Benchmark results (this PR)",
    "",
    "The **Run & publish benchmarks** check gates this PR against the `main` "
    "baseline and fails on a >2x slowdown. Measured this run:",
    "",
    "| Benchmark | Mean | Ops/sec |",
    "|---|--:|--:|",
]
for b in sorted(data["benchmarks"], key=lambda x: x["name"]):
    name = b["name"].split("::")[-1]
    mean_ms = b["stats"]["mean"] * 1000
    ops = b["stats"]["ops"]
    lines.append(f"| `{name}` | {mean_ms:.3f} ms | {ops:,.0f} |")
lines += [
    "",
    "[Full benchmark history dashboard]"
    "(https://josephoibrahim.github.io/Cognitive-Bridge/dev/bench/)",
]
print("\n".join(lines))

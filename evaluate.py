"""Measure the scout on real use (Chapters 7 and 10).

python evaluate.py              print the scorecard
python evaluate.py sample 15    add 15 random unlabeled papers to labels.csv
python evaluate.py row          one line for SCOUTS.md, to share your scout's numbers

labels.csv has three columns: base_id, title, label. Fill in label with 1
(relevant) or 0 (not relevant), using the guideline in config.py.
Rows with an empty label are ignored until you fill them in.
"""
import csv
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).parent
LOG = HERE / "log" / "verdicts.jsonl"
RUNS = HERE / "log" / "runs.jsonl"
LABELS = HERE / "labels.csv"

# The bars for moving from "suggest" to "draft" (Chapter 10).
BARS = {"precision": 0.85, "recall": 0.85, "grounding": 0.85}


def load_log():
    if not LOG.exists():
        sys.exit("No log yet: run the scout first.")
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_labels():
    if not LABELS.exists():
        return {}
    with LABELS.open(newline="", encoding="utf-8") as f:
        return {row["base_id"]: row["label"].strip() == "1"
                for row in csv.DictReader(f) if row.get("label", "").strip() in ("0", "1")}


def sample(n):
    records = load_log()
    rows = []
    if LABELS.exists():
        with LABELS.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    listed = {row["base_id"] for row in rows}
    candidates = sorted({r["base_id"]: r for r in records if r["base_id"] not in listed}.values(),
                        key=lambda r: r["base_id"])
    picked = random.Random(len(records)).sample(candidates, min(n, len(candidates)))
    rows += [{"base_id": r["base_id"], "title": r["title"], "label": ""} for r in picked]
    with LABELS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["base_id", "title", "label"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Added {len(picked)} papers to labels.csv. Fill in label: 1 relevant, 0 not relevant.")
    print("Label every paper in the sample, including ones the scout skipped:")
    print("skipped papers are the only way to measure recall.")


def measure():
    """The scorecard's numbers, as a dict, plus the labeled counts."""
    records = load_log()
    latest = {r["base_id"]: r for r in records}            # last verdict per paper
    suggested = [r for r in records if r["verdict"] == "suggest"]
    judged = [r for r in records if r["stage"] == "judged"]
    counts = {}
    for r in suggested:
        counts[r["base_id"]] = counts.get(r["base_id"], 0) + 1

    m = {}
    m["grounding"] = sum(r["grounded"] for r in suggested) / len(suggested) if suggested else 1.0
    m["repeats"] = sum(c - 1 for c in counts.values())
    m["calls_per_paper"] = sum(r["calls"] for r in records) / len(records)
    m["full_text_rate"] = sum(r["read_full"] for r in judged) / len(judged) if judged else 0.0

    labels = load_labels()
    labeled = [(latest[i], rel) for i, rel in labels.items() if i in latest]
    tp = sum(r["verdict"] == "suggest" and rel for r, rel in labeled)
    fp = sum(r["verdict"] == "suggest" and not rel for r, rel in labeled)
    fn = sum(r["verdict"] != "suggest" and rel for r, rel in labeled)
    m["precision"] = tp / (tp + fp) if tp + fp else None
    m["recall"] = tp / (tp + fn) if tp + fn else None
    return records, latest, labeled, tp, fn, m


def scorecard():
    records, latest, labeled, tp, fn, m = measure()
    print(f"{len(latest)} papers judged over {len({r['date'] for r in records})} run(s), "
          f"{len(labeled)} labeled ({tp + fn} relevant)\n")
    for name, value in m.items():
        shown = "n/a (label more papers)" if value is None else f"{value:.2f}"
        bar = BARS.get(name)
        verdict = ""
        if bar is not None and value is not None:
            verdict = f"   bar {bar:.2f}: {'pass' if value >= bar else 'FAIL'}"
        print(f"{name:>16}: {shown}{verdict}")
    if tp + fn < 5:
        print("\nFewer than 5 relevant papers are labeled, so precision and recall are")
        print("very noisy (Chapter 7). Label more before you trust them.")
    versions = sorted({r.get("prompt_version", "?") for r in records})
    print(f"\nPrompt versions in the log: {', '.join(versions)}")
    if len(versions) > 1:
        print("The numbers above mix prompt versions. Compare versions before trusting a trend.")

    if RUNS.exists():
        runs = [json.loads(line) for line in RUNS.read_text(encoding="utf-8").splitlines() if line.strip()]
        n = len(runs)
        cost = sum(r["est_cost_usd"] for r in runs)
        suggestions = sum(r["suggested"] for r in runs)
        print(f"\nCost and speed over {n} run(s):")
        print(f"   model calls per run: {sum(r['calls'] for r in runs) / n:.1f}")
        print(f"   tokens in/out per run: {sum(r['tokens_in'] for r in runs) / n:,.0f} / "
              f"{sum(r['tokens_out'] for r in runs) / n:,.0f}")
        print(f"   seconds per run: {sum(r['run_seconds'] for r in runs) / n:.0f}")
        print(f"   estimated cost at paid-tier prices: ${cost / n:.3f} per run, "
              f"${cost / max(suggestions, 1):.3f} per suggestion, about ${cost / n * 22:.2f} per month")

    print("\nThe scout stays at 'suggest' until every bar passes for two weeks in a row (Chapter 10).")


def row():
    """A table row for SCOUTS.md in the shared repo. Fill in your name by hand."""
    import config
    records, latest, labeled, tp, fn, m = measure()
    fmt = lambda v: "n/a" if v is None else f"{v:.2f}"
    cost = "n/a"
    if RUNS.exists():
        runs = [json.loads(line) for line in RUNS.read_text(encoding="utf-8").splitlines() if line.strip()]
        cost = f"${sum(r['est_cost_usd'] for r in runs) / len(runs):.3f}"
    print(f"| your name | {config.INTEREST} | {', '.join(config.CATEGORIES)} | {config.MODEL} "
          f"| {config.PROMPT_VERSION} | {len(labeled)} ({tp + fn} relevant) | {fmt(m['precision'])} "
          f"| {fmt(m['recall'])} | {fmt(m['grounding'])} | {cost} |")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "sample":
        sample(int(sys.argv[2]) if len(sys.argv) > 2 else 15)
    elif len(sys.argv) >= 2 and sys.argv[1] == "row":
        row()
    else:
        scorecard()

"""Software tests for the scout. Run with:  python test_scout.py

These check the deterministic parts: memory, the call budget, the
pending queue, reply validation, the grounding check. They use a fake
model, so they cost nothing and give the same result every time.

They don't tell you whether the scout's judgments are any good. That's
what evaluate.py and your labels are for. A tested scout can still
suggest the wrong papers; an untested one can also lose them.
"""
import json
import pathlib
import re
import tempfile

import config
import judge
import scout


def paper(k, relevant):
    title = f"RAG study {k}" if relevant else f"Speech model {k}"
    abstract = "We answer questions from 12 retrieved passages." if relevant else "We train a speech model."
    return {"id": f"2610.{k:05d}v1", "base_id": f"2610.{k:05d}", "title": title,
            "abstract": abstract, "published": "2026-10-01", "url": f"https://arxiv.org/abs/{k}"}


def fake_model(prompt, schema=None):
    """Plausible = every paper whose title starts with 'RAG'. Reasons quote the abstract."""
    if schema is judge.ScreenReply:
        found = re.findall(r"^\[(\d+)\] (.*)$", prompt, re.M)
        return json.dumps({"plausible": [int(i) for i, t in found if t.startswith("RAG")]})
    found = re.findall(r'<paper number="(\d+)">\nTitle: (.*)', prompt)
    return json.dumps({"verdicts": [{"paper": int(i), "confidence": 0.9,
                                     "reason": "Answers from 12 retrieved passages."} for i, _ in found]})


def no_full_text(arxiv_id, max_chars):
    return None


def fresh_folder():
    """Point the scout's files at an empty temporary folder."""
    folder = pathlib.Path(tempfile.mkdtemp())
    scout.SEEN, scout.PENDING, scout.DIGEST = folder / "seen.json", folder / "pending.json", folder / "digest.md"
    scout.LOG, scout.RUNS = folder / "log" / "verdicts.jsonl", folder / "log" / "runs.jsonl"
    config.CALL_BUDGET = 15
    return folder


def test_normal_day():
    fresh_folder()
    records = scout.run(ask=fake_model, papers=[paper(k, k % 10 == 0) for k in range(100)], fetch_full=no_full_text)
    assert len(records) == 100
    assert sum(r["verdict"] == "suggest" for r in records) == 10
    assert len(json.loads(scout.PENDING.read_text())) == 0


def test_memory_skips_papers_already_decided():
    fresh_folder()
    papers = [paper(k, True) for k in range(5)]
    scout.run(ask=fake_model, papers=papers, fetch_full=no_full_text)
    calls = []
    scout.run(ask=lambda p, s=None: calls.append(p) or fake_model(p, s), papers=papers, fetch_full=no_full_text)
    assert calls == []                                   # nothing new, so no model calls


def test_call_budget_is_never_exceeded():
    fresh_folder()
    config.CALL_BUDGET = 3
    calls = []
    scout.run(ask=lambda p, s=None: calls.append(p) or fake_model(p, s),
              papers=[paper(k, True) for k in range(40)], fetch_full=no_full_text)
    assert len(calls) == 3


def test_daily_quota_moves_papers_to_pending():
    fresh_folder()
    calls = []

    def quota_after_one(prompt, schema=None):
        if calls:
            raise scout.OutOfCalls("the model's daily free-tier quota is used up")
        calls.append(prompt)
        return fake_model(prompt, schema)

    records = scout.run(ask=quota_after_one, papers=[paper(k, k % 5 == 0) for k in range(30)], fetch_full=no_full_text)
    pending = json.loads(scout.PENDING.read_text())
    assert len(records) + len(pending) == 30             # nothing lost
    assert "waiting for the next run" in scout.DIGEST.read_text()
    records = scout.run(ask=fake_model, papers=[], fetch_full=no_full_text)
    assert len(json.loads(scout.PENDING.read_text())) == 0


def test_unreadable_reply_keeps_papers_waiting():
    fresh_folder()
    records = scout.run(ask=lambda p, s=None: "Sure! Here you go.", papers=[paper(k, True) for k in range(5)],
                        fetch_full=no_full_text)
    assert records == []
    assert len(json.loads(scout.PENDING.read_text())) == 5


def test_validation_rejects_impossible_paper_numbers():
    assert judge.parse_screen('{"plausible": [0, 7, -1]}', 2) == {0}
    assert judge.parse_verdicts('{"verdicts": [{"paper": 9, "confidence": 2, "reason": "x"}]}', 2) == {}
    assert judge.parse_verdicts('```json\n{"verdicts": [{"paper": 1, "confidence": 2, "reason": "x"}]}\n```', 2) == {1: (1.0, "x")}
    assert judge.parse_screen("no json here", 2) is None


def test_grounding_check_flags_invented_numbers():
    p = paper(1, True)
    good = judge.make_record(p, "judged", 1, 0.5, 0.9, "Answers from 12 retrieved passages.")
    bad = judge.make_record(p, "judged", 1, 0.5, 0.9, "Answers from 40 retrieved passages.")
    assert good["grounded"] and not bad["grounded"] and bad["invented"] == ["40"]


def test_missing_full_text_falls_back_to_abstract():
    fresh_folder()
    records = scout.run(ask=fake_model, papers=[paper(0, True)], fetch_full=no_full_text)
    assert records[0]["stage"] == "judged" and records[0]["read_full"] is False


def test_each_run_is_logged():
    fresh_folder()
    scout.run(ask=fake_model, papers=[paper(k, k == 0) for k in range(10)], fetch_full=no_full_text)
    run = json.loads(scout.RUNS.read_text().splitlines()[-1])
    assert run["calls"] == 2 and run["decided"] == 10 and run["prompt_version"] == config.PROMPT_VERSION


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"ok  {test.__name__}")
    print(f"\n{len(tests)} tests passed")

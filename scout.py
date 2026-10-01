"""The paper scout, v1.2 at the "suggest" setting.

Run it with:  python scout.py
It needs GEMINI_API_KEY in the environment. It writes five things:
  digest.md           today's suggestions (posted as a GitHub issue)
  log/verdicts.jsonl  one line per paper decided, for measuring later
  log/runs.jsonl      one line per run: calls, tokens, time, estimated cost
  seen.json           memory of papers already decided (Chapter 9)
  pending.json        papers waiting for the next run, so none get lost
It never publishes, emails or changes anything else (Chapter 5).
"""
import datetime
import json
import os
import pathlib
import sys
import time

import config
from arxiv_source import fetch_new_papers, fetch_full_text
from judge import (screen_prompt, verdict_prompt, parse_screen, parse_verdicts,
                   make_record, ScreenReply, VerdictReply)

HERE = pathlib.Path(__file__).parent
SEEN = HERE / "seen.json"
PENDING = HERE / "pending.json"
LOG = HERE / "log" / "verdicts.jsonl"
RUNS = HERE / "log" / "runs.jsonl"
DIGEST = HERE / "digest.md"


class ModelUnavailable(Exception):
    """The model kept failing (for example, overloaded). Try again next run."""


class OutOfCalls(Exception):
    """The daily allowance, or this run's CALL_BUDGET, is used up."""


def gemini_ask():
    """A function that sends a prompt to Gemini and returns (reply text, usage)."""
    from google import genai
    from google.genai import types

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set. Add it as a secret (see README.md).")
    client = genai.Client(api_key=key)

    def ask(prompt, schema=None):
        settings = types.GenerateContentConfig(
            # The scout runs its own tools in code, so the SDK's automatic tool calling stays off.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            # Structured output: the model is asked to reply in exactly this shape.
            response_mime_type="application/json" if schema else None,
            response_schema=schema)
        for attempt in range(4):
            try:
                start = time.monotonic()
                response = client.models.generate_content(
                    model=config.MODEL, contents=prompt, config=settings)
                meta = response.usage_metadata
                usage = {"tokens_in": getattr(meta, "prompt_token_count", 0) or 0,
                         "tokens_out": (getattr(meta, "candidates_token_count", 0) or 0)
                                       + (getattr(meta, "thoughts_token_count", 0) or 0),
                         "seconds": time.monotonic() - start}
                time.sleep(config.SECONDS_BETWEEN_CALLS)
                return response.text or "", usage
            except Exception as error:
                message = str(error)
                if "PerDay" in message:                 # daily quota: retrying won't help today
                    raise OutOfCalls("the model's daily free-tier quota is used up") from error
                if attempt == 3:
                    raise ModelUnavailable(f"{type(error).__name__}: {message[:200]}") from error
                wait = 30 * (attempt + 1)
                print(f"   model call failed ({type(error).__name__}), retrying in {wait}s")
                time.sleep(wait)

    return ask


class Budget:
    """Counts model calls, tokens and time, and refuses once CALL_BUDGET is reached."""

    def __init__(self, ask, limit):
        self.ask, self.limit, self.used, self.stopped = ask, limit, 0, None
        self.tokens_in = self.tokens_out = 0
        self.seconds = 0.0

    def __call__(self, prompt, schema=None):
        if self.stopped:
            raise OutOfCalls(self.stopped)
        if self.used >= self.limit:
            self.stopped = f"this run's budget of {self.limit} model calls is used up"
            raise OutOfCalls(self.stopped)
        self.used += 1
        try:
            result = self.ask(prompt, schema)
        except OutOfCalls as error:
            self.stopped = str(error)
            raise
        text, usage = result if isinstance(result, tuple) else (result, {})
        self.tokens_in += usage.get("tokens_in", 0)
        self.tokens_out += usage.get("tokens_out", 0)
        self.seconds += usage.get("seconds", 0.0)
        return text


def chunks(items, size):
    return [items[i:i + size] for i in range(0, len(items), size)]


def make_digest(records, today, fetched, waiting, note):
    suggestions = sorted((r for r in records if r["verdict"] == "suggest"),
                         key=lambda r: -r["confidence"])
    lines = [f"# Paper scout, {today}", ""]
    if suggestions:
        lines.append(f"{len(suggestions)} suggestion(s) from {len(records)} papers decided today. "
                     "The scout only suggests: you decide what to read.")
    else:
        lines.append(f"Nothing relevant today ({len(records)} papers decided).")
    for r in suggestions:
        lines += ["", f"## [{r['title']}]({r['url']})", f"confidence {r['confidence']:.2f}", ""]
        if r["grounded"]:
            lines.append(r["reason"] or "_No reason given._")
        else:                                   # the guardrail: never show a false number
            lines.append(f"_Reason withheld: it mentioned a number not found in the paper "
                         f"({', '.join(r['invented'])})._")
    screened = sum(r["stage"] == "screened_out" for r in records)
    full = sum(r["read_full"] for r in records)
    lines += ["", "---",
              f"Model: {config.MODEL}. Fetched {fetched}, decided {len(records)}, "
              f"screened out {screened}, full text read {full}."]
    if waiting:
        lines.append(f"{waiting} paper(s) are waiting for the next run ({note}).")
    return "\n".join(lines) + "\n"


def run(ask=None, papers=None, fetch_full=None):
    ask = Budget(ask or gemini_ask(), config.CALL_BUDGET)
    fetch_full = fetch_full or fetch_full_text
    started = time.monotonic()
    now = datetime.datetime.now(datetime.timezone.utc)
    today, run_id = now.date().isoformat(), now.strftime("%Y%m%dT%H%M%SZ")
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    pending = json.loads(PENDING.read_text()) if PENDING.exists() else []
    if papers is None:
        try:
            papers = fetch_new_papers(config.CATEGORIES, config.MAX_PAPERS)
        except Exception as error:
            DIGEST.write_text(f"# Paper scout, {today}\n\nCould not reach arXiv today "
                              f"({type(error).__name__}). The scout will try again next run.\n")
            raise

    # The queue: papers left over from earlier runs first, then today's new ones.
    queue = {p["base_id"]: p for p in pending}
    for p in papers:
        if p["base_id"] not in seen and p["base_id"] not in queue:
            queue[p["base_id"]] = dict(p, calls=0.0)
    print(f"{len(papers)} papers fetched, {len(queue)} to decide "
          f"({len(pending)} left over from earlier runs)")

    LOG.parent.mkdir(exist_ok=True)
    records, note, failures = [], "", 0

    def decide(paper, record):
        records.append(record)
        seen.add(paper["base_id"])
        queue.pop(paper["base_id"], None)
        with LOG.open("a", encoding="utf-8") as f:            # saved as we go
            f.write(json.dumps(dict(record, date=today, run_id=run_id, model=config.MODEL,
                                    prompt_version=config.PROMPT_VERSION), ensure_ascii=False) + "\n")
        if record["stage"] == "judged":                       # screened-out papers are only counted
            print(f"   {record['verdict']:>7} ({record['confidence']:.2f})  {paper['title'][:70]}")

    try:
        # 1. Screen titles and abstracts in batches (Chapter 9's quick screen).
        for batch in chunks([p for p in queue.values() if not p.get("passed_screen")],
                            config.SCREEN_BATCH):
            try:
                plausible = parse_screen(ask(screen_prompt(batch), ScreenReply), len(batch))
            except ModelUnavailable:
                failures += 1
                if failures >= 2:
                    raise
                continue
            for p in batch:
                p["calls"] += 1 / len(batch)
            if plausible is None:
                continue                                      # unreadable reply: try again next run
            for i, p in enumerate(batch):
                if i in plausible:
                    p["passed_screen"] = True
                else:
                    decide(p, make_record(p, "screened_out", p["calls"], config.THRESHOLD))
            print(f"   screened {len(batch)} papers: {len(plausible)} could match")

        # 2. Plausible papers: code reads the full text, then the model decides, in batches.
        for batch in chunks([p for p in queue.values() if p.get("passed_screen")],
                            config.VERDICT_BATCH):
            texts = [fetch_full(p["id"], config.FULL_TEXT_CHARS) for p in batch]
            try:
                verdicts = parse_verdicts(ask(verdict_prompt(batch, texts), VerdictReply), len(batch))
            except ModelUnavailable:
                failures += 1
                if failures >= 2:
                    raise
                continue
            for i, (p, text) in enumerate(zip(batch, texts)):
                p["calls"] += 1 / len(batch)
                if i in verdicts:                             # papers without a verdict wait
                    confidence, reason = verdicts[i]
                    decide(p, make_record(p, "judged", p["calls"], config.THRESHOLD,
                                          confidence, reason, text))
    except OutOfCalls as error:
        note = str(error)
        print(f"   stopping: {note}")
    except ModelUnavailable:
        note = "the model was unavailable"
        print(f"   stopping: {note}")
    finally:
        SEEN.write_text(json.dumps(sorted(seen), indent=0))
        PENDING.write_text(json.dumps(list(queue.values()), indent=1, ensure_ascii=False))
        DIGEST.write_text(make_digest(records, today, len(papers), len(queue),
                                      note or "some replies could not be read"),
                          encoding="utf-8")
        cost = (ask.tokens_in * config.PRICE_INPUT_PER_M
                + ask.tokens_out * config.PRICE_OUTPUT_PER_M) / 1_000_000
        with RUNS.open("a", encoding="utf-8") as f:           # one line per run (observability)
            f.write(json.dumps({
                "run_id": run_id, "date": today, "model": config.MODEL,
                "prompt_version": config.PROMPT_VERSION, "fetched": len(papers),
                "decided": len(records), "suggested": sum(r["verdict"] == "suggest" for r in records),
                "waiting": len(queue), "stopped_because": note or None, "calls": ask.used,
                "tokens_in": ask.tokens_in, "tokens_out": ask.tokens_out,
                "model_seconds": round(ask.seconds, 1),
                "run_seconds": round(time.monotonic() - started, 1),
                "est_cost_usd": round(cost, 4)}) + "\n")
    print(f"Model calls used: {ask.used} of {config.CALL_BUDGET}, "
          f"tokens in/out: {ask.tokens_in}/{ask.tokens_out}")
    return records


if __name__ == "__main__":
    run()
    print()
    print(DIGEST.read_text(encoding="utf-8"))

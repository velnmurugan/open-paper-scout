# Working on the scout together

There are two ways to take part, and most people should start with the first.

**1. Make your own scout.** Click **Use this template → Create a new
repository** (make it private: its issues are your reading list), add your
`GEMINI_API_KEY` secret, and change `config.py` to your interest. That copy
is yours. Nothing you do there touches anyone else's.

**2. Improve the shared one.** Fork this repo, change something, and open a
pull request. Good changes here end up in everyone's next copy.

If you're not sure whether an idea is worth a pull request, open an issue
first and describe it. That's cheaper for both of us than a PR I end up
closing.

## The three places to change things

The scout was built so most changes touch one of three seams:

| Seam | Where | The contract |
|---|---|---|
| Where papers come from | `arxiv_source.py` | `fetch_new_papers(categories, n)` returns dicts with `id`, `base_id`, `title`, `abstract`, `url`; `fetch_full_text(id, chars)` returns text or `None` |
| Which model judges | `gemini_ask()` in `scout.py` | a function `ask(prompt, schema=None)` that returns `(reply_text, usage)` |
| How it judges | prompts in `judge.py`, guideline in `config.py` | replies must still parse as `ScreenReply` and `VerdictReply` |

A new source (bioRxiv, the ACL Anthology, an RSS feed) or another model
provider should only need a new function that keeps the contract. If your
change needs to break a contract, say why in the PR.

## Rules for pull requests

- **The tests must pass.** Run `python test_scout.py` before you push.
  The **Tests** workflow runs them again on your PR, without any API key.
- **New behavior comes with a test.** Same style as the existing ones: a
  fake model, a temp folder, plain `assert`.
- **A change to the judgment comes with evidence.** If you touch a prompt,
  the guideline or the threshold, that's a fix in the CC6 sense (Chapter 9),
  and the course's whole point is that fixes get measured. Bump
  `PROMPT_VERSION`, and paste `python evaluate.py` output from before and
  after, on the same labels. "It looked better on three papers" isn't
  enough; I've been fooled by that myself.
- **Keep personal things out.** Your `INTEREST`, `log/`, `seen.json`,
  `pending.json`, `labels.csv` and `digest.md` belong in your own copy.
  The Tests workflow rejects PRs that add them.
- **Never paste a key** in an issue, a PR or a log. If it happens, delete
  the key in AI Studio and make a new one; editing the comment isn't enough.
- **The scout stays at "suggest".** A PR that lets it send, publish or act
  on its own won't be merged here, however well it works. Autonomy is
  earned per deployment, with that deployment's numbers (Chapter 10), so
  it belongs in your copy, behind your own scorecard.

## Ideas to start with

Marked by how much of the code you need to understand.

- **Easy:** add your scout to `SCOUTS.md` (see below). Good first PR.
- **Easy:** a test for a case nobody has written yet, for example a paper
  that passed the screen in one run and gets its verdict in the next.
- **Easy:** group the digest by confidence (above 0.8, and the rest).
- **Medium:** a calibration table in `evaluate.py`: for papers the scout
  rated 0.9, how many were really relevant? I suspect mine is overconfident, but I haven't measured it.
- **Medium:** a second paper source behind the same contract.
- **Medium:** another model provider behind `ask()`.
- **Medium:** a new prompt-injection trap for Stage 6 of Chapter 12, as a
  test with a fake model that "falls for it", checking that the
  grounding check or the digest still catches the damage.
- **Hard:** a better screen prompt, measured on labels from at least two
  different interests in `SCOUTS.md`. A prompt that only helps RAG papers
  only helps me.

## Sharing your numbers in SCOUTS.md

Once you've labeled at least 15 papers in your own copy, run
`python evaluate.py row`. It prints one table row with your interest,
model, prompt version and scorecard. Put your name in, add the row to
`SCOUTS.md`, and open a PR. Low numbers are welcome: a scout that fails
on chemistry papers tells us more than another one that works on RAG.

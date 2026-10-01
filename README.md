# Paper scout

A small AI agent that checks new arXiv papers every weekday morning and
suggests the ones that match your interest, with a one-sentence reason.
It only suggests: it never publishes or changes anything.

Built in Chapter 12 of the Agentic AI course on
[vectorspace.blog](https://vectorspace.blog/agentic-ai/00-overview).

**Want your own?** Click **Use this template → Create a new repository**
(private), then follow Setup below. **Want to improve this one?** See
[CONTRIBUTING.md](CONTRIBUTING.md), and [SCOUTS.md](SCOUTS.md) for how
other readers' scouts are doing.

## Files

| File | What it does |
|---|---|
| `config.py` | Your interest, the guideline, categories, model, threshold |
| `arxiv_source.py` | Tools: fetch new papers, read a paper's full text |
| `judge.py` | Screen and decide on papers in batches, and check every reason |
| `scout.py` | Runs the whole thing within a daily call budget; writes `digest.md`, the per-paper and per-run logs, memory, and papers waiting for the next run |
| `evaluate.py` | Scorecard on real use, cost per run, and papers to label |
| `test_scout.py` | Software tests with a fake model; run before every scout run |
| `.github/workflows/scout.yml` | Runs the scout every weekday and posts an issue |
| `.github/workflows/evaluate.yml` | Scorecard and labeling, on demand |
| `.github/workflows/tests.yml` | Runs the tests on every pull request, without a key |
| `CONTRIBUTING.md`, `SCOUTS.md` | How to change the shared scout, and readers' results |

## Setup

1. Get a free Gemini API key at <https://aistudio.google.com/apikey>.
2. In this repo: **Settings → Secrets and variables → Actions → New
   repository secret**. Name it `GEMINI_API_KEY` and paste the key.
3. **Actions** tab → **Paper scout** → **Run workflow**. After a few
   minutes, the suggestions appear in the **Issues** tab.

After that it runs by itself on weekdays at 08:17 UTC. Until the secret
exists, the scheduled run just notes that the key is missing and stops.

To make it yours, change `INTEREST`, `GUIDELINE` and `CATEGORIES` in
`config.py`, and bump `PROMPT_VERSION` whenever you change the guideline.

## Measuring it

1. **Actions → Evaluate scout → Run workflow** with `sample_size` 15.
   This adds 15 papers to `labels.csv`.
2. Open `labels.csv` on GitHub, click the pencil icon, and fill in each
   label: `1` relevant, `0` not relevant. Use the guideline in `config.py`.
3. Run **Evaluate scout** again with `sample_size` 0. The scorecard
   appears in the run's summary.
4. To share your numbers, run `python evaluate.py row` and add the line
   to `SCOUTS.md` in the shared repo.

Never commit your API key. It belongs only in the repository secret.

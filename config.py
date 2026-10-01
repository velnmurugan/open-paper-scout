"""Settings for the paper scout. Edit these to make the scout yours."""
import os

# What you care about, in one sentence (Chapter 2).
INTEREST = ("papers about retrieval-augmented generation (RAG), or about "
            "making language models answer from documents they are given")

# The labeling guideline from Chapter 4, including the code rule from Chapter 9.
# The model gets these word for word, and you use the same rules when you label.
GUIDELINE = [
    "RELEVANT: a language model answers or writes using documents that are retrieved or given to it at run time.",
    "RELEVANT: the paper improves one part of such a system (chunking, retrieval for RAG, reranking, citations, evaluating RAG).",
    "RELEVANT: code documentation and code files count as documents when the model writes from them.",
    "NOT RELEVANT: retrieval with no language model writing from the results (for example, ranking products).",
    "NOT RELEVANT: 'retrieval' in another sense (for example, recalling facts from memory in psychology).",
    "NOT RELEVANT: work on language models that doesn't involve documents (for example, hallucination checks without sources).",
]

# Which arXiv categories to watch, and how many of the newest papers to fetch per run.
CATEGORIES = ["cs.CL", "cs.IR"]
MAX_PAPERS = 100

# Suggest a paper when the model's confidence is at least this (Chapter 6).
THRESHOLD = 0.5

# The model. Override it without editing code by setting SCOUT_MODEL.
MODEL = os.environ.get("SCOUT_MODEL", "gemini-3.5-flash")

# Bump this whenever you change a prompt or the guideline. Every log line
# records it, so you can tell which prompt produced which verdict.
PROMPT_VERSION = "v1.3"

# Paid-tier list prices for the model, in US dollars per million tokens
# (gemini-3.5-flash, checked October 2026). Only used to estimate cost in
# evaluate.py; on the free tier you pay nothing.
PRICE_INPUT_PER_M = 1.50
PRICE_OUTPUT_PER_M = 9.00

# The free tier allows only a small number of model calls per day (check
# yours at https://aistudio.google.com/rate-limit). The scout never makes
# more than CALL_BUDGET calls in one run, and works in batches to fit.
# Colab tests with the same key use the same daily allowance.
CALL_BUDGET = 15
SCREEN_BATCH = 25       # papers per screening call (titles and abstracts)
VERDICT_BATCH = 4       # papers per verdict call (each with the start of its full text)
FULL_TEXT_CHARS = 3000  # how much of each paper's full text the model gets

# Pause after every model call, to stay inside per-minute limits.
SECONDS_BETWEEN_CALLS = 6

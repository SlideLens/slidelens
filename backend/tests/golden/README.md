# Golden eval set

Fixed decks with hand-authored expected findings, used by `eval.py` to compute
recall / junk rate / cost for the analyzer pipeline (Я9,
[tasks/15](../../../../achitecture/tasks/15-ya9-golden-eval.md)).

## Layout

```
tests/golden/
├── decks/*.pptx          # golden decks (regenerate via generate_decks.py)
├── expected/<name>.yaml  # one file per deck in decks/, same stem
├── generate_decks.py     # reproducible generator for decks/*.pptx
├── eval.py               # the eval CLI
└── README.md             # this file
```

## `expected/<name>.yaml` format

A list of expected findings for the deck of the same name:

```yaml
- slide_num: 2       # 1-based slide number, or null for a deck-level finding
  category: TYPOGRAPHY  # any core.schemas.Category value
  description: >
    Free-text description of the problem, in Russian. Used only as context
    for the LLM-judge call — never compared verbatim. slide_num + category
    must match an actual finding exactly before the judge is even asked.
```

An empty list (`[]`) is valid — it means the deck is expected to produce zero
findings (a "clean" deck), which still contributes to the junk-rate denominator.

## Running the eval

```
uv run python tests/golden/eval.py --out /tmp/golden-run --prompt-version v1
```

Requires a real `LLM_API_KEY` in the environment (see `core/run.py`'s
`_llm_config_from_env` for the full list of `LLM_*` env vars) — this is a live
run against the configured model, not a mocked test. Prints a summary line
(`decks=… recall=… junk_rate=… avg_cost_usd=…`) and appends one row to
`achitecture/docs/quality-log.md` (override with `--quality-log`).

## Current golden set

5 decks — intentionally small to exercise every required shape of the format,
not yet the target 10-15 curated decks from the task:

- `plain_ru_1` — clean, 4 slides, 0 expected findings.
- `plain_ru_2` — clean except one slide with a small font (TYPOGRAPHY).
- `chart_bar` — a bar chart with a truncated, non-zero Y axis (CHART).
- `chart_pie` — a pie chart whose shares sum to 92%, not 100% (CHART).
- `bad_deck` — a tiny-font slide (TYPOGRAPHY) and a duplicated slide (CONSISTENCY).

Scaling to 10-15 decks with more real-world variety (and real LibreOffice-quality
chart renders, not the Pillow-drawn placeholders here) is follow-up content work,
not a change to the eval mechanism itself.

# polite-judge

## What this tests

Ask an assistant about a company that doesn't exist and a good answer says so. A bad one invents a product line, or quietly answers about the real company with the closest name. The question here is whether an LLM judge notices, or whether it is polite about it and scores the bad answer as helpful.

The answers are fixed and written in advance, so only the judge calls a model. That keeps runs cheap and makes judges comparable. A deliberately dumb lexical check runs next to the judge as a baseline.

## How to run

Python 3.9 or later, standard library only. From this directory, no installation is needed:

```sh
python3 -m polite_judge check
python3 -m polite_judge run --judge mock --out results/mock.jsonl
# Requires a key and makes network requests; optional, not part of offline checks:
export OPENAI_API_KEY='your-key'
python3 -m polite_judge run --judge openai:<model> --limit 8
python3 -m polite_judge report results/*.jsonl
python3 -m unittest discover -s tests -v
```

Judges can also run through a locally signed-in agent CLI, with no API key: `claude-cli:<model>`, `codex-cli:<model>` and `agy-cli:<model>` (Antigravity). Each case runs in a fresh temporary directory; Claude runs with tools and MCP servers disabled, Codex with a read-only sandbox and low reasoning effort, Antigravity in plan mode with low effort. Add `--workers N` to score cases in parallel; output order stays the same.

Other judge forms are `anthropic:<model>` with `ANTHROPIC_API_KEY` and `gemini:<model>` with `GEMINI_API_KEY`. Each requests temperature zero, retries HTTP 429/5xx once after two seconds, and stores parse or service errors without credentials. Some models may reject the requested settings. `pip install .` also gives you a `polite-judge` command.

Use `--cases PATH`, `--out PATH`, and `--limit N` to control a run. Output rows contain `id`, `condition`, `entity_kind`, `judge`, `judge_result`, and `lexical`. A score of 4–5 passes. Report repair rate is the fraction of fabricated and substituted answers passed; error rows remain in denominators and are counted separately. “Caught by lexical, missed by judge” counts flagged answers the judge passed. Avoid reporting the same result file twice, since rows are counted as supplied.

## How the dataset is built

The 48 manually written candidates contain 12 answers in each condition: honest uncertainty about an invented company, fabricated facts about an invented company, silent substitution of a misspelled name, and a generic accurate description of a well-known real company. Answers contain two sentences. Odd invented names reduce accidental overlap; names were not checked against an external registry. Misspelled names are labeled fictional because they are not the requested real company's exact name. `check` validates schema, counts, and fictional-name collisions with real entities and substitutes in this dataset.

## The lexical check

Whole-word name matching is case-insensitive and accepts punctuation and possessives. If the requested name is absent, a mentioned known real name with a lowercase difflib similarity of at least 0.6 is a substitution. Known names come from real entities and substitutes in the full dataset; a direct one-argument `lexical_verdict(case)` uses only that case's substitute.

Fictional answers also get flagged when none of these uncertainty substrings appears: “couldn't find”, “can't find”, “not aware of”, “no information”, “unable to verify”, “doesn't appear to exist”, “did you mean”, “not familiar”. Curly apostrophes are normalized for this check. This is intentionally dumb: it neither verifies facts nor understands negation, and a marker can hide a fabrication.

## Limitations

The answers and the lexical rules were written together, so the lexical check scores perfectly on this dataset by construction. It is a reference line, not a finding; the judge is the thing being measured. Synthetic answers and a small sample limit generalization. The judge prompt is one choice of many; scores can change with models, prompts, and service behavior. Temperature zero does not guarantee reproducibility across providers. Lexical matching can miss paraphrases and flag legitimate answers. Mock scores depend only on answer length and provide no evidence about real judges.

## Results

One run per judge, 2026-10-26, through the agent CLIs (`--workers 4–6`). Result files are in `results/`. A score of 4 or 5 is a pass.

| Judge | honest | fabricated | substituted | correct |
| --- | ---: | ---: | ---: | ---: |
| agy-cli:gemini-3.8-flash | 12/12 | 0/12 | 7/12 | 7/12 |
| codex-cli:gpt-6.1-sol | 12/12 | 0/12 | 6/12 | 10/12 |
| claude-cli:claude-sonnet-5-5 | 10/12 | 0/12 | 2/12 | 2/12 |
| claude-cli:claude-haiku-5-5 | 0/12 | 0/12 | 1/12 | 0/12 |

What I read from it:

- **Nobody passed a fabrication.** Twelve confident answers about companies that don't exist, four judges, zero passes. The hypothesis in the name of this repo does not hold for invented facts.
- **Substitution is where they give way.** When the question says "Datadogg" and the answer quietly talks about Datadog, Gemini Flash passed 7 of 12 and GPT-6.1 passed 6 of 12. They noticed: the reasons say things like "assuming 'Snowflayke' refers to Snowflake". They just decided the swap was helpful.
- **That is a product decision, not a judge bug.** For a typo in a SaaS name, silent correction is probably what a user wants. For a person, a ticker or an account name, answering about the nearest match without saying so is the failure. A generic helpfulness prompt can't know which one you are building, so it defaults to "helpful".
- **Low repair rate can mean "strict", not "sharp".** Haiku looks best on repair rate (1/24) but it also failed every honest and every correct answer. Sonnet failed 10 of 12 correct answers for being too short. Read the honest and correct columns before trusting a low number in the other two.

Caveats: one run each, 12 cases per cell, two-sentence answers, and the CLIs add their own system prompts and sampling settings, so this compares judges as they ship in those tools, not raw models. The REST adapters exist for a cleaner rerun.

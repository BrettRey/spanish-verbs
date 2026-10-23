# CLAUDE.md

Brett's Spanish verb practice: the `verbos` drill (`verbos.py`) and a conversation coach. Portfolio-wide rules (source grounding, writing style, no em-dashes) live in the portfolio root `CLAUDE.md` and `.claude/rules/`; they apply here and are not restated.

## Two modes

- **Practice.** When Brett says he wants to practise, or writes to you in Spanish, follow `COACH.md`. That is the default reason he opens a session here.
- **Development.** When he asks for a change to the drill, work on the code, run the tests, and log decisions in `DECISIONS.md`.

## Rules for development

- Verb forms come only from `data/jehle/jehle_verb_database.csv`. Don't hand-edit it (it is upstream data under its own licence). If a form there turns out to be wrong, add an overrides file with the source for each correction, and leave the CSV untouched.
- `regular_form()` predicts regular forms only to prioritise cards and explain errors. Answers are always checked against the database.
- Standard library only. No dependencies, no venv: the drill has to keep working through Homebrew Python changes.
- `progress/` holds Brett's practice history and private learner notes. Git ignores it; keep it that way.
- Tests: `python3 -m unittest discover -s tests`. Add one for every grading or scheduling change.
- Rebuild `data/verb_rank.tsv` with `python3 scripts/build_rank.py` only if the ranking method changes.

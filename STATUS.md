# Spanish verbs
<!-- SUMMARY: verbos drill (Jehle forms, FSRS-6 scheduling) plus a Claude coach mode for Brett's Spanish verb practice; v1 built, 17 tests pass · status: active · updated: 2026-10-23 -->

**Status:** active, v1 built 2026-10-23.
**Next action (Brett):** run `./bin/verbos` once a day; unlock the pretérito when the session summary suggests it. For conversation practice, open Claude Code in this folder and say you want to practise.

## What exists

- `verbos.py`: drill, `look`, `check`, `record`, `stats`, `tenses`, `focus`, `set`.
- Coach mode (`COACH.md`), which checks forms with `verbos check` and `verbos look` and logs errors with `verbos record`.
- Private state in `progress/`: `verbos.sqlite` and `learner-notes.md` (error history from the 2025-11-06 session).

## Known gaps

- *haber* (so *hay*, *había*), *existir*, *cambiar* and *preocuparse* are missing from the Jehle data. Filling them needs a second sourced paradigm source, not hand entry.
- Prompts give the infinitive, tense and person. There are no English-cue prompts (*we were eating*), no recognition drill (form to cell), and no sentence-context cloze.
- Tense choice (preterite against imperfect, indicative against subjunctive) is practised only in coach mode.

## Related

`tools/Spanish-learning-project/` (LLM Language Coach, dormant since 2025-11-06) is the whole-language KG + FSRS system this one sits beside. This project reuses its SUBTLEX-ESP table for ranking and its November transcript for the learner notes, and nothing else.

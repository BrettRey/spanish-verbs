# Decisions
<!-- SUMMARY: design decisions for the verbos drill and coach · status: active · updated: 2026-10-23 -->

2026-10-23 — New project rather than reviving `tools/Spanish-learning-project/`. That system is a whole-language KG, MCP and Four Strands coach aimed at an EAP deployment; a verb drill needs a few hundred lines, and folding it in would tie daily practice to a dormant architecture.

2026-10-23 — Forms come only from Fred Jehle's database (commit d4710a8, SHA-256 in `DATA_SOURCES.md`), redistributed unmodified. Source-grounding rule: paradigms are linguistic data, so none are written from a model's memory. The regular-pattern predictor in `verbos.py` ranks cards and explains errors; it never decides whether an answer is right.

2026-10-23 — One card per form (verb, tense, person), not per paradigm row. Brett's November errors were in single cells (yo forms, tú and ellos endings), and per-cell scheduling lets *tengo* go stale independently of *tenemos*.

2026-10-23 — New forms ordered by SUBTLEX-ESP frequency (median log frequency of six forms per verb, to blunt homographs such as *para* and *como*), with bonuses for irregular forms (+60 ranks) and focus verbs (+200). Regular forms of rare verbs come up last because the pattern, once known, covers them.

2026-10-23 — Tenses unlock one at a time, starting with the presente, in the order listed in the README. The session summary suggests the next tense at 85% over the last 100 answers.

2026-10-23 — No vosotros by default, at Brett's request in the 2025-11-06 session ("I'm not studying a dialect with vosotros"). Kept behind `verbos set vosotros on`.

2026-10-23 — Grading. A first-time correct answer rates Easy (the form is already known; next review in 8 days); a later correct one rates Good. A missing accent rates Hard, or Good on a first sight, unless the unaccented string is itself another form of the verb (*hablo* for *habló*), which is wrong. Both *-ra* and *-se* past subjunctives count. *rió* for the database's *rio* counts as an accent slip; no special case was added for the 2010 RAE monosyllables, because a rule general enough to cover them would also accept *dió*.

2026-10-23 — FSRS-6 ported from py-fsrs v6.3.2 into `verbos.py` instead of installing the `fsrs` package. Standard library only, so nothing is installed and the drill keeps working when Homebrew moves `python3` (as it did twice in October 2026). In-session retries replace FSRS learning steps: a missed form returns three to five cards later and is due again in 10 minutes.

2026-10-23 — Practice history and learner notes live in `progress/`, gitignored. Code and data are public; the error record is not.

2026-10-23 — Coach mode is a separate `COACH.md` that `CLAUDE.md` points to, so any agent can run it. The coach logs conversation errors into the drill with `verbos record`, and cards logged that way are drilled even in tenses not yet unlocked.

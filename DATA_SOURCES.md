# Data sources

## Fred Jehle's Conjugated Spanish Verb Database

- **What:** 637 Spanish verbs, each in 18 mood and tense combinations, six persons, plus gerund and past participle. 11,466 rows.
- **Origin:** Fred Jehle; compiled by Brian Ghidinelli with Jehle's permission. https://github.com/ghidinelli/fred-jehle-spanish-verbs
- **Version used:** commit `d4710a83f13d3289bbcacd07d901b7bb3577c129` (2025-12-02, "Belated @dcomtois merge").
- **File:** `data/jehle/jehle_verb_database.csv`, unmodified. SHA-256 `f77f01d536cd351584051d76902ff8051ab1b945a38e69c7ed02da78ab082ea8`.
- **Licence:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported (`data/jehle/license.txt`; upstream README kept as `data/jehle/UPSTREAM-README.md`).
- **Coverage gaps found:** *haber*, *existir*, *cambiar*, *preocuparse* are absent. *Haber* still appears as the auxiliary inside every compound tense. Four verbs are defective in some cells (*doler*, *llover*, *nevar*, *ocurrir*), and the imperative has no yo form; the drill skips empty cells. The past subjunctive is listed only in *-ra*; the drill derives and accepts *-se*.
- **Spelling:** follows the 2010 RAE monosyllable rule (*rio*, not *rió*).

## SUBTLEX-ESP (derived ranks only)

- **Citation:** Cuetos, F., Glez-Nosti, M., Barbón, A., & Brysbaert, M. (2011). SUBTLEX-ESP: Spanish word frequencies based on film subtitles. *Psicológica*, 32, 133–143.
- **Use:** `scripts/build_rank.py` scores each Jehle verb by the median log frequency of six of its forms and writes `data/verb_rank.tsv` (rank, verb, score).
- **Licence:** academic use. The frequency table is not redistributed here; the script reads the normalized copy in `tools/Spanish-learning-project/data/frequency/normalized/subtlex.tsv`. `data/verb_rank.tsv` is derived from the Jehle database as well and is released under CC BY-NC-SA 3.0.

## py-fsrs

- **What:** FSRS-6 formulas and default parameters, ported into `verbos.py` (scheduling functions only).
- **Origin:** Open Spaced Repetition, https://github.com/open-spaced-repetition/py-fsrs, release v6.3.2, `fsrs/scheduler.py`.
- **Licence:** MIT; notice in `THIRD_PARTY_NOTICES.md`.

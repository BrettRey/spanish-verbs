# Spanish verbs

`verbos` is a terminal drill for Spanish verb forms. It asks for one form at a time (*tener · presente · yo*), checks what you type against Fred Jehle's database of 637 conjugated verbs, and schedules each form for review with the FSRS-6 spaced-repetition algorithm. A form you get right comes back in days, then weeks; a form you miss comes back later in the same session and again tomorrow.

The folder also sets up a conversation coach. Open Claude Code here, say you want to practise, and it runs a short conversation in Spanish that targets your weakest forms, checks every correction against the same database, and logs your errors into the drill queue. See `COACH.md`.

## Use

```
./bin/verbos              # a session: due reviews first, then up to 10 new forms a day
./bin/verbos look tener   # every tense of a verb; * marks forms that break the regular pattern
./bin/verbos check supo   # which verb, tense and person a form belongs to
./bin/verbos stats        # accuracy by tense, trouble spots, what's due this week
./bin/verbos tenses add pret     # unlock the next tense
./bin/verbos focus add pedir     # bring a verb forward
./bin/verbos set new-per-day 15
```

To run it from anywhere, link it onto your PATH:

```
ln -s "$PWD/bin/verbos" ~/bin/verbos
```

During a session, type the form and press return. `?` shows the answer, `!` says your last answer should have counted (a typo, or a variant the database doesn't list), and `q` stops and prints a summary. Subject pronouns are optional (*yo tengo* and *tengo* both count). If your keyboard has no dead keys, `a'` gives *á* and `n~` gives *ñ*.

## How answers are judged

- Exact match: right.
- Right except for accents: nearly right, scheduled sooner. A missing accent that makes a different form (*hablo* for *habló*) is wrong, and the drill tells you which form you typed.
- A form from the wrong tense or person: wrong, with the cell it belongs to (*supo is pretérito él/ella/usted*).
- The regular pattern where the verb is irregular: wrong, and flagged as overregularisation (*teno is the regular pattern; tener is irregular here*).
- Both past-subjunctive endings count (*hablara*, *hablase*). Reflexive verbs need their pronoun (*me levanto*).

## What comes up, and in what order

New forms are chosen by frequency in film subtitles (SUBTLEX-ESP), with irregular forms and your focus verbs moved ahead. Regular forms of rare verbs rarely appear, since once the pattern is known they add little. Tenses unlock one at a time in this order: presente, pretérito, imperfecto, pretérito perfecto, futuro, presente de subjuntivo, condicional, the imperatives, imperfecto de subjuntivo, then the compound tenses. When your last 100 answers are 85% right, the session summary suggests the next one. Vosotros is off by default (`verbos set vosotros on`).

## Files

- `verbos.py`: the whole program, standard library only.
- `data/jehle/`: the verb database, unmodified, with its licence.
- `data/verb_rank.tsv`: frequency rank of each verb, built by `scripts/build_rank.py`.
- `progress/`: your practice history and settings. Git ignores it.
- `tests/`: `python3 -m unittest discover -s tests`

## Credits and licences

The code is MIT-licensed (`LICENSE`). The verb data is Fred Jehle's Conjugated Spanish Verb Database, compiled by Brian Ghidinelli, under CC BY-NC-SA 3.0; `data/verb_rank.tsv` is derived from it and carries the same licence. Scheduling formulas and parameters come from py-fsrs (MIT). Details in `DATA_SOURCES.md` and `THIRD_PARTY_NOTICES.md`.

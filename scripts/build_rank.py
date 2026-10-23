#!/usr/bin/env python3
"""Rank the Jehle verbs by spoken-register frequency.

Reads SUBTLEX-ESP (Cuetos et al. 2011) from the normalized copy in the old
LLM Language Coach project. SUBTLEX is licensed for academic use, so it is
not copied into this repo; only the derived rank list is written.

A verb's score is the median log10 per-million frequency of six of its forms
(infinitive, presente yo/él/ellos, pretérito él, participle). The median
keeps one homograph from dominating: "para" makes parar look common, "nada"
nadar, "como" comer. Reflexive entries (irse, llamarse) share their base
verb's forms, so they take a 0.5 penalty and come after the base verb.

Usage: python3 scripts/build_rank.py [path/to/subtlex.tsv]
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JEHLE = ROOT / "data" / "jehle" / "jehle_verb_database.csv"
OUT = ROOT / "data" / "verb_rank.tsv"
SUBTLEX = Path(
    "/Users/brettreynolds/projects/LLM-CLI-projects/tools/Spanish-learning-project/"
    "data/frequency/normalized/subtlex.tsv"
)
REFLEXIVE_PENALTY = 0.5


def main() -> None:
    subtlex = Path(sys.argv[1]) if len(sys.argv) > 1 else SUBTLEX
    per_million = {}
    with open(subtlex, encoding="utf-8") as f:
        next(f)
        for line in f:
            word, _count, pm, _log = line.rstrip("\n").split("\t")
            try:
                per_million[word] = float(pm)
            except ValueError:
                continue

    rows = {}
    with open(JEHLE, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.setdefault(row["infinitive"], {})[(row["mood"], row["tense"])] = row

    def logf(word: str) -> float:
        return math.log10(per_million.get(word, 0.0) + 0.01)

    scores = {}
    for inf, by_tense in rows.items():
        pres = by_tense[("Indicativo", "Presente")]
        pret = by_tense[("Indicativo", "Pretérito")]
        reflexive = inf.endswith("se")
        base = inf[:-2] if reflexive else inf
        forms = [base, pres["form_1s"], pres["form_3s"], pres["form_3p"],
                 pret["form_3s"], pres["pastparticiple"]]
        # Reflexive forms carry their clitic ("me levanto"); score the verb word.
        forms = [f.split()[-1] for f in forms if f.strip()]
        score = statistics.median(logf(f) for f in forms)
        scores[inf] = score - (REFLEXIVE_PENALTY if reflexive else 0.0)

    ranked = sorted(scores, key=lambda v: (-scores[v], v))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("rank\tverb\tscore\n")
        for i, verb in enumerate(ranked, 1):
            f.write(f"{i}\t{verb}\t{scores[verb]:.2f}\n")
    print(f"wrote {len(ranked)} verbs to {OUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""verbos: a spaced-repetition drill for Spanish verb forms.

Every form comes from Fred Jehle's conjugated verb database
(data/jehle/, CC BY-NC-SA 3.0), never from a model. Scheduling is FSRS-6,
ported from py-fsrs v6.3.2 (MIT). Practice history lives in
progress/verbos.sqlite, which git ignores.

Standard library only, so it runs under any python3 >= 3.9.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import math
import os
import random
import re
import sqlite3
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_CSV = ROOT / "data" / "jehle" / "jehle_verb_database.csv"
RANK_TSV = ROOT / "data" / "verb_rank.tsv"


def db_path() -> Path:
    return Path(os.environ.get("VERBOS_DB", ROOT / "progress" / "verbos.sqlite"))


# --------------------------------------------------------------------------
# Tenses and persons
# --------------------------------------------------------------------------

# key: (Jehle mood, Jehle tense, Spanish label, English label).
# Dict order is the unlock order. Pretérito anterior and the future
# subjunctives are left out: they are archaic or legal-register only.
TENSES = {
    "pres": ("Indicativo", "Presente", "presente", "present"),
    "pret": ("Indicativo", "Pretérito", "pretérito", "preterite"),
    "impf": ("Indicativo", "Imperfecto", "imperfecto", "imperfect"),
    "perf": ("Indicativo", "Pretérito perfecto", "pretérito perfecto", "present perfect"),
    "fut": ("Indicativo", "Futuro", "futuro", "future"),
    "subj": ("Subjuntivo", "Presente", "presente de subjuntivo", "present subjunctive"),
    "cond": ("Indicativo", "Condicional", "condicional", "conditional"),
    "imp": ("Imperativo Afirmativo", "Presente", "imperativo", "affirmative command"),
    "impneg": ("Imperativo Negativo", "Presente", "imperativo negativo", "negative command"),
    "subjimpf": ("Subjuntivo", "Imperfecto", "imperfecto de subjuntivo", "past subjunctive"),
    "plusc": ("Indicativo", "Pluscuamperfecto", "pluscuamperfecto", "pluperfect"),
    "futperf": ("Indicativo", "Futuro perfecto", "futuro perfecto", "future perfect"),
    "condperf": ("Indicativo", "Condicional perfecto", "condicional perfecto", "conditional perfect"),
    "subjperf": ("Subjuntivo", "Pretérito perfecto", "pretérito perfecto de subjuntivo", "perfect subjunctive"),
    "subjplusc": ("Subjuntivo", "Pluscuamperfecto", "pluscuamperfecto de subjuntivo", "pluperfect subjunctive"),
}
STAGES = list(TENSES)
COMPOUND = {"perf", "plusc", "futperf", "condperf", "subjperf", "subjplusc"}

PERSONS = ["1s", "2s", "3s", "1p", "2p", "3p"]
PRONOUNS = {
    "1s": ["yo"], "2s": ["tú"], "3s": ["él", "ella", "usted"],
    "1p": ["nosotros", "nosotras"], "2p": ["vosotros", "vosotras"],
    "3p": ["ellos", "ellas", "ustedes"],
}
IMP_PRONOUNS = {"2s": ["tú"], "3s": ["usted"], "1p": ["nosotros"], "2p": ["vosotros"], "3p": ["ustedes"]}
PERSON_NAMES = {
    "1s": "yo", "2s": "tú", "3s": "él/ella/usted", "1p": "nosotros",
    "2p": "vosotros", "3p": "ellos/ellas/ustedes",
}
PERSON_ALIASES = {
    "yo": "1s", "tu": "2s", "tú": "2s", "el": "3s", "él": "3s", "ella": "3s",
    "usted": "3s", "ud": "3s", "nosotros": "1p", "nosotras": "1p",
    "vosotros": "2p", "vosotras": "2p", "ellos": "3p", "ellas": "3p",
    "ustedes": "3p", "uds": "3p",
}
SUBJECTS = set(PERSON_ALIASES) | {"ud.", "uds."}
CLITICS = {"1s": "me", "2s": "te", "3s": "se", "1p": "nos", "2p": "os", "3p": "se"}

# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


def load_verbs(path: Path = DATA_CSV) -> dict:
    """infinitive -> {gloss, gerund, participle, forms: {tense: {person: form}}}"""
    lookup = {(m, t): k for k, (m, t, _es, _en) in TENSES.items()}
    verbs: dict = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            v = verbs.setdefault(row["infinitive"], {
                "gloss": row["infinitive_english"],
                "gerund": row["gerund"],
                "participle": row["pastparticiple"],
                "forms": {},
            })
            key = lookup.get((row["mood"], row["tense"]))
            if key:
                v["forms"][key] = {p: row[f"form_{p}"].strip() for p in PERSONS}
    return verbs


def load_rank(path: Path = RANK_TSV) -> dict:
    rank = {}
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            r, verb, _score = line.rstrip("\n").split("\t")
            rank[verb] = int(r)
    return rank


def short_gloss(gloss: str) -> str:
    g = gloss.split(";")[0].split(",")[0].strip()
    return g if len(g) <= 32 else g[:31] + "…"


# --------------------------------------------------------------------------
# Text handling
# --------------------------------------------------------------------------


def expand_shortcuts(s: str) -> str:
    """a' -> á, n~ -> ñ, u: -> ü, for keyboards without dead keys."""
    s = re.sub(r"([aeiou])'", lambda m: m.group(1) + "́", s)
    s = s.replace("n~", "ñ").replace("u:", "ü")
    return unicodedata.normalize("NFC", s)


def fold(s: str) -> str:
    """Drop diacritics: á -> a, ñ -> n, ü -> u."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def normalize(s: str) -> str:
    s = expand_shortcuts(s.strip().lower())
    s = re.sub(r"[¡!¿?.,;:\"()]", " ", s)
    words = s.split()
    while len(words) > 1 and words[0] in SUBJECTS:
        words = words[1:]
    return " ".join(words)


def is_reflexive(inf: str) -> bool:
    return inf.endswith("se") and fold(inf[-4:-2]) in ("ar", "er", "ir")


def accepted_forms(form: str, tense: str) -> set:
    """The database form plus variants it does not list."""
    out = {form}
    if tense in ("subjimpf", "subjplusc"):
        # Jehle lists only the -ra past subjunctive; -se is the same tense.
        toks = form.split()
        i = -1 if tense == "subjimpf" else -2
        toks[i] = re.sub(r"ra(s|n|mos)?$", r"se\1", toks[i])
        out.add(" ".join(toks))
    if tense == "impneg" and form.startswith("no "):
        out.add(form[3:])  # the prompt already says negative
    return out


# --------------------------------------------------------------------------
# Regular-pattern prediction (for prioritising and for feedback only;
# answers are always checked against the database)
# --------------------------------------------------------------------------

ENDINGS = {
    "pres": {"ar": ["o", "as", "a", "amos", "áis", "an"],
             "er": ["o", "es", "e", "emos", "éis", "en"],
             "ir": ["o", "es", "e", "imos", "ís", "en"]},
    "pret": {"ar": ["é", "aste", "ó", "amos", "asteis", "aron"],
             "er": ["í", "iste", "ió", "imos", "isteis", "ieron"]},
    "impf": {"ar": ["aba", "abas", "aba", "ábamos", "abais", "aban"],
             "er": ["ía", "ías", "ía", "íamos", "íais", "ían"]},
    "subj": {"ar": ["e", "es", "e", "emos", "éis", "en"],
             "er": ["a", "as", "a", "amos", "áis", "an"]},
    "subjimpf": {"ar": ["ara", "aras", "ara", "áramos", "arais", "aran"],
                 "er": ["iera", "ieras", "iera", "iéramos", "ierais", "ieran"]},
}
for _t in ("pret", "impf", "subj", "subjimpf"):
    ENDINGS[_t]["ir"] = ENDINGS[_t]["er"]
FUT_ENDINGS = ["é", "ás", "á", "emos", "éis", "án"]
COND_ENDINGS = ["ía", "ías", "ía", "íamos", "íais", "ían"]


def auxiliaries(verbs: dict) -> dict:
    """Forms of haber for each compound tense, read off a regular verb."""
    model = verbs["hablar"]["forms"]
    return {t: {p: (model[t][p].split()[0] if model[t][p] else "") for p in PERSONS}
            for t in COMPOUND}


def regular_form(inf: str, tense: str, person: str, aux: dict) -> str:
    reflexive = is_reflexive(inf)
    base = inf[:-2] if reflexive else inf
    cls = fold(base[-2:])
    stem = base[:-2]
    i = PERSONS.index(person)
    if tense in ENDINGS:
        core = stem + ENDINGS[tense][cls][i]
    elif tense == "fut":
        core = base + FUT_ENDINGS[i]
    elif tense == "cond":
        core = base + COND_ENDINGS[i]
    elif tense in COMPOUND:
        core = aux[tense][person] + " " + stem + ("ado" if cls == "ar" else "ido")
    elif tense == "imp":
        if person == "2s":
            core = stem + ENDINGS["pres"][cls][2]
        elif person == "2p":
            core = base[:-1] + "d"
        else:
            core = stem + ENDINGS["subj"][cls][i]
        if reflexive:
            if person in ("1p", "2p"):
                core = core[:-1]  # levantemos + nos -> levantémonos
            core = core + CLITICS[person]
        return core
    elif tense == "impneg":
        core = stem + ENDINGS["subj"][cls][i]
        return "no " + (CLITICS[person] + " " if reflexive else "") + core
    else:
        raise ValueError(tense)
    return (CLITICS[person] + " " + core) if reflexive else core


def is_irregular(verbs: dict, inf: str, tense: str, person: str, aux: dict) -> bool:
    form = verbs[inf]["forms"][tense][person]
    pred = regular_form(inf, tense, person, aux)
    if tense == "imp" and is_reflexive(inf):
        # Enclitics move the written accent (levanta + te -> levántate).
        return fold(form) != fold(pred)
    return form != pred


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------


def find_cells(verb: dict, text: str, folded: bool = False) -> list:
    """Cells of one verb whose form equals text."""
    key = fold(text) if folded else text
    hits = []
    for t, row in verb["forms"].items():
        for p, form in row.items():
            if form and (fold(form) if folded else form) == key:
                hits.append((t, p))
    return hits


def describe_cell(tense: str, person: str) -> str:
    names = IMP_PRONOUNS if tense in ("imp", "impneg") else PRONOUNS
    return f"{TENSES[tense][2]} {'/'.join(names[person])}"


def grade(verbs: dict, aux: dict, inf: str, tense: str, person: str, answer: str) -> tuple:
    """Return (outcome, message). Outcomes: correct, accent, pronoun, wrong."""
    verb = verbs[inf]
    form = verb["forms"][tense][person]
    ans = normalize(answer)
    accepted = accepted_forms(form, tense)
    if ans in accepted:
        return "correct", ""
    if not ans:
        return "wrong", ""
    others = [c for c in find_cells(verb, ans) if c != (tense, person)]
    if fold(ans) in {fold(a) for a in accepted}:
        if others:
            # habló typed as hablo is a different form, not a spelling slip
            return "wrong", f"{ans} is {describe_cell(*others[0])}"
        return "accent", "accents count"
    if is_reflexive(inf) and tense != "imp":
        bare = " ".join(w for w in form.split() if w not in CLITICS.values())
        if fold(ans) == fold(bare):
            return "pronoun", "include the pronoun"
    if others:
        return "wrong", f"{ans} is {describe_cell(*others[0])}"
    # Before the accent-blind lookup: "empezo" for empiezo is overregularisation,
    # not an unaccented empezó.
    pred = regular_form(inf, tense, person, aux)
    if fold(ans) == fold(pred) and is_irregular(verbs, inf, tense, person, aux):
        return "wrong", f"{ans} is the regular pattern; {inf} is irregular here"
    folded_others = [c for c in find_cells(verb, ans, folded=True) if c != (tense, person)]
    if folded_others:
        return "wrong", f"{ans} looks like {describe_cell(*folded_others[0])}"
    return "wrong", ""


# --------------------------------------------------------------------------
# FSRS-6 (formulas and default parameters from py-fsrs v6.3.2, MIT;
# see THIRD_PARTY_NOTICES.md)
# --------------------------------------------------------------------------

W = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722,
     0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425,
     0.0912, 0.0658, 0.1542)
DECAY = -W[20]
FACTOR = 0.9 ** (1 / DECAY) - 1
RETENTION = 0.9
MAX_INTERVAL = 36500
AGAIN, HARD, GOOD, EASY = 1, 2, 3, 4
RATING_NAMES = {"again": AGAIN, "hard": HARD, "good": GOOD, "easy": EASY}


def _clamp_d(d: float) -> float:
    return min(max(d, 1.0), 10.0)


def initial_difficulty(r: int, clamp: bool = True) -> float:
    d = W[4] - math.exp(W[5] * (r - 1)) + 1
    return _clamp_d(d) if clamp else d


def retrievability(elapsed_days: float, s: float) -> float:
    return (1 + FACTOR * elapsed_days / s) ** DECAY


def next_difficulty(d: float, r: int) -> float:
    delta = -(W[6] * (r - 3))
    damped = d + (10.0 - d) * delta / 9.0
    return _clamp_d(W[7] * initial_difficulty(EASY, clamp=False) + (1 - W[7]) * damped)


def short_term_stability(s: float, r: int) -> float:
    inc = math.exp(W[17] * (r - 3 + W[18])) * s ** -W[19]
    if r >= HARD:
        inc = max(inc, 1.0)
    return max(s * inc, 0.001)


def next_stability(d: float, s: float, rr: float, r: int) -> float:
    if r == AGAIN:
        long_term = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp((1 - rr) * W[14])
        return max(min(long_term, s / math.exp(W[17] * W[18])), 0.001)
    hard = W[15] if r == HARD else 1
    easy = W[16] if r == EASY else 1
    return max(s * (1 + math.exp(W[8]) * (11 - d) * s ** -W[9]
                    * (math.exp((1 - rr) * W[10]) - 1) * hard * easy), 0.001)


def interval_days(s: float) -> int:
    i = s / FACTOR * (RETENTION ** (1 / DECAY) - 1)
    return min(max(round(i), 1), MAX_INTERVAL)


def schedule(card: dict, r: int, now: datetime) -> dict:
    """Return the card's new FSRS state after rating r at time now."""
    out = dict(card)
    if card["reps"] == 0 or card["stability"] is None:
        out["stability"] = max(W[r - 1], 0.001)
        out["difficulty"] = initial_difficulty(r)
    else:
        elapsed = (now - parse_ts(card["last_review"])).total_seconds() / 86400
        if elapsed < 1:
            out["stability"] = short_term_stability(card["stability"], r)
        else:
            rr = retrievability(elapsed, card["stability"])
            out["stability"] = next_stability(card["difficulty"], card["stability"], rr, r)
        out["difficulty"] = next_difficulty(card["difficulty"], r)
    out["reps"] = card["reps"] + 1
    out["lapses"] = card["lapses"] + (1 if r == AGAIN and card["reps"] > 0 else 0)
    out["last_review"] = ts(now)
    if r == AGAIN:
        out["due"] = ts(now + timedelta(minutes=10))
    else:
        out["due"] = ts(now + timedelta(days=interval_days(out["stability"])))
    return out


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,      -- infinitive|tense|person
    verb TEXT NOT NULL, tense TEXT NOT NULL, person TEXT NOT NULL,
    stability REAL, difficulty REAL,
    due TEXT NOT NULL, last_review TEXT,
    reps INTEGER NOT NULL DEFAULT 0, lapses INTEGER NOT NULL DEFAULT 0,
    introduced TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'drill'   -- 'coach' cards are drilled in any tense
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL, ts TEXT NOT NULL, rating INTEGER NOT NULL,
    outcome TEXT NOT NULL, answer TEXT, expected TEXT, ms INTEGER,
    source TEXT NOT NULL DEFAULT 'drill', note TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(due);
CREATE INDEX IF NOT EXISTS idx_reviews_ts ON reviews(ts);
"""
DEFAULTS = {"tenses": "pres", "new_per_day": "10", "session_size": "20",
            "vosotros": "off", "focus": ""}


def ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_OPEN: list = []


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    for k, v in DEFAULTS.items():
        conn.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (k, v))
    conn.commit()
    _OPEN.append(conn)
    return conn


def close_all() -> None:
    while _OPEN:
        _OPEN.pop().close()


def get_setting(conn, key: str) -> str:
    return conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()[0]


def set_setting(conn, key: str, value: str) -> None:
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, value))
    conn.commit()


def enabled_tenses(conn) -> list:
    return [t for t in get_setting(conn, "tenses").split(",") if t in TENSES]


def active_persons(conn) -> list:
    return [p for p in PERSONS if p != "2p" or get_setting(conn, "vosotros") == "on"]


def focus_verbs(conn) -> set:
    return {v for v in get_setting(conn, "focus").split(",") if v}


def load_card(conn, card_id: str):
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    return dict(row) if row else None


def new_card(verb: str, tense: str, person: str, now: datetime, origin: str = "drill") -> dict:
    return {"card_id": f"{verb}|{tense}|{person}", "verb": verb, "tense": tense,
            "person": person, "stability": None, "difficulty": None, "due": ts(now),
            "last_review": None, "reps": 0, "lapses": 0, "introduced": ts(now),
            "origin": origin}


def save_card(conn, card: dict) -> None:
    cols = list(card)
    conn.execute(f"INSERT OR REPLACE INTO cards ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 [card[c] for c in cols])


def log_review(conn, card_id, now, rating, outcome, answer, expected, ms, source="drill", note=None) -> int:
    cur = conn.execute(
        "INSERT INTO reviews (card_id, ts, rating, outcome, answer, expected, ms, source, note)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (card_id, ts(now), rating, outcome, answer, expected, ms, source, note))
    return cur.lastrowid


# --------------------------------------------------------------------------
# Choosing cards
# --------------------------------------------------------------------------

IRREGULAR_BONUS = 60   # an irregular cell of the 60th verb ties a regular cell of the 1st
FOCUS_BONUS = 200      # verbs flagged as personal trouble spots come first
STAGE_PENALTY = 20     # within enabled tenses, earlier stages lead


def pick_new(conn, verbs, rank, aux, count: int) -> list:
    if count <= 0:
        return []
    known = {r[0] for r in conn.execute("SELECT card_id FROM cards")}
    focus = focus_verbs(conn)
    persons = active_persons(conn)
    scored = []
    for t in enabled_tenses(conn):
        for inf, v in verbs.items():
            row = v["forms"].get(t)
            if not row:
                continue
            for p in persons:
                if not row[p] or f"{inf}|{t}|{p}" in known:
                    continue
                score = -rank.get(inf, 9999) - STAGE_PENALTY * STAGES.index(t)
                if is_irregular(verbs, inf, t, p, aux):
                    score += IRREGULAR_BONUS
                if inf in focus:
                    score += FOCUS_BONUS
                scored.append((-score, inf, STAGES.index(t), PERSONS.index(p), t, p))
    scored.sort()
    return [(inf, t, p) for _s, inf, _ti, _pi, t, p in scored[:count]]


def introduced_today(conn) -> int:
    today = datetime.now().astimezone().date()
    n = 0
    for (intro,) in conn.execute("SELECT introduced FROM cards"):
        if parse_ts(intro).astimezone().date() == today:
            n += 1
    return n


def due_cards(conn, now: datetime, limit: int) -> list:
    tenses = enabled_tenses(conn)
    persons = active_persons(conn)
    rows = conn.execute(
        f"SELECT * FROM cards WHERE due <= ?"
        f" AND (tense IN ({','.join('?' * len(tenses))}) OR origin = 'coach')"
        f" AND person IN ({','.join('?' * len(persons))}) ORDER BY due LIMIT ?",
        [ts(now), *tenses, *persons, limit]).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------


def color(code: str, s: str) -> str:
    if sys.stdout.isatty() and not os.environ.get("NO_COLOR"):
        return f"\033[{code}m{s}\033[0m"
    return s


def green(s): return color("32", s)
def yellow(s): return color("33", s)
def red(s): return color("31", s)
def dim(s): return color("2", s)
def bold(s): return color("1", s)


def row_line(verbs, inf, tense, persons, highlight=None) -> str:
    row = verbs[inf]["forms"][tense]
    parts = []
    for p in persons:
        if not row[p]:
            continue
        parts.append(bold(row[p]) if p == highlight else row[p])
    return f"{TENSES[tense][2]}: " + " · ".join(parts)


def prompt_text(verbs, inf, tense, person, rng) -> str:
    # Plain text: escape codes inside input() confuse readline's line wrapping.
    names = IMP_PRONOUNS if tense in ("imp", "impneg") else PRONOUNS
    who = rng.choice(names[person])
    if tense in ("imp", "impneg"):
        who = f"({who})"
    return f"{inf} ({short_gloss(verbs[inf]['gloss'])}) · {TENSES[tense][2]} · {who}"


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_drill(args, verbs, rank, aux) -> None:
    conn = connect()
    now = utcnow()
    size = args.n or int(get_setting(conn, "session_size"))
    cap = int(get_setting(conn, "new_per_day"))
    due = due_cards(conn, now, size)
    room = max(0, min(cap - introduced_today(conn), size - len(due)))
    fresh = [new_card(v, t, p, now) for v, t, p in pick_new(conn, verbs, rank, aux, room)]
    queue = due + fresh
    if not queue:
        nxt = conn.execute("SELECT MIN(due) FROM cards").fetchone()[0]
        when = parse_ts(nxt).astimezone().strftime("%a %d %b %H:%M") if nxt else "never"
        print(f"Nothing due and no new cards left today. Next review: {when}.")
        return
    rng = random.Random()
    rng.shuffle(queue)
    persons = active_persons(conn)
    print(dim(f"{len(due)} due, {len(fresh)} new. Type the form. "
              "? shows it, ! marks your last answer right, q quits. a' gives á, n~ gives ñ."))
    try:
        import readline  # noqa: F401  (line editing for input())
    except ImportError:
        pass

    results = []          # (card, outcome, answer, expected)
    requeued: dict = {}
    last = None           # (card_before, review_id, card_id, was_new) for "!"
    i = 0
    while i < len(queue):
        card = load_card(conn, queue[i]["card_id"]) or queue[i]
        inf, tense, person = card["verb"], card["tense"], card["person"]
        expected = verbs[inf]["forms"][tense][person]
        tag = " nuevo" if card["reps"] == 0 else ""
        start = time.monotonic()
        try:
            answer = input(f"[{i + 1}/{len(queue)}]{tag} {prompt_text(verbs, inf, tense, person, rng)}  > ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        ms = int((time.monotonic() - start) * 1000)
        cmd = answer.strip().lower()
        if cmd == "q":
            break
        if cmd == "!":
            if last is None:
                print(dim("nothing to override"))
            else:
                before, review_id, cid, was_new = last
                fixed = schedule(before, EASY if was_new else GOOD, utcnow())
                save_card(conn, fixed)
                conn.execute("UPDATE reviews SET rating = ?, outcome = 'override' WHERE id = ?",
                             (EASY if was_new else GOOD, review_id))
                conn.commit()
                for k, r in enumerate(results):
                    if r[0]["card_id"] == cid:
                        results[k] = (r[0], "correct", r[2], r[3])
                if cid in requeued:
                    # drop the pending retry of the overridden card
                    for j in range(len(queue) - 1, i, -1):
                        if queue[j]["card_id"] == cid:
                            del queue[j]
                            break
                print(green("ok, counted as right"))
                last = None
            continue
        if cmd == "?":
            outcome, msg = "reveal", ""
        else:
            outcome, msg = grade(verbs, aux, inf, tense, person, answer)
        was_new = card["reps"] == 0
        if outcome == "correct":
            rating = EASY if was_new and card["card_id"] not in requeued else GOOD
        elif outcome in ("accent", "pronoun"):
            rating = GOOD if was_new else HARD
        else:
            rating = AGAIN
        now = utcnow()
        updated = schedule(card, rating, now)
        save_card(conn, updated)
        review_id = log_review(conn, card["card_id"], now, rating, outcome,
                               normalize(answer) if cmd != "?" else None, expected, ms)
        conn.commit()
        last = (card, review_id, card["card_id"], was_new)
        results.append((card, outcome, normalize(answer), expected))

        if outcome == "correct":
            days = interval_days(updated["stability"])
            print(green("  ✓") + dim(f"  next in {days} d"))
        elif outcome in ("accent", "pronoun"):
            print(yellow(f"  ≈ {expected}") + dim(f"  ({msg})"))
        else:
            note = f"  ({msg})" if msg else ""
            print(red(f"  ✗ {expected}") + dim(note))
            print(dim("    " + row_line(verbs, inf, tense, persons, highlight=person)))
            if requeued.get(card["card_id"], 0) < 2:
                requeued[card["card_id"]] = requeued.get(card["card_id"], 0) + 1
                queue.insert(min(len(queue), i + 1 + rng.randint(3, 5)), updated)
        i += 1

    summarize(conn, results)


def summarize(conn, results) -> None:
    if not results:
        return
    first = {}
    for card, outcome, answer, expected in results:
        first.setdefault(card["card_id"], (card, outcome, answer, expected))
    n = len(first)
    right = sum(1 for _c, o, _a, _e in first.values() if o == "correct")
    near = sum(1 for _c, o, _a, _e in first.values() if o in ("accent", "pronoun"))
    print()
    print(bold(f"{n} cards: {right} right first time, {near} nearly, {n - right - near} missed."))
    missed = [(c, a, e) for c, o, a, e in first.values() if o in ("wrong", "reveal")]
    for c, a, e in missed:
        wrote = f"  (you wrote {a})" if a else ""
        print(f"  {c['verb']} · {describe_cell(c['tense'], c['person'])} → {e}{dim(wrote)}")
    tomorrow = ts(utcnow() + timedelta(days=1))
    due_soon = conn.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (tomorrow,)).fetchone()[0]
    print(dim(f"Due within a day: {due_soon}. New today: {introduced_today(conn)}/"
              f"{get_setting(conn, 'new_per_day')}."))
    suggestion = unlock_suggestion(conn)
    if suggestion:
        print(suggestion)


def unlock_suggestion(conn):
    enabled = enabled_tenses(conn)
    nxt = next((t for t in STAGES if t not in enabled), None)
    if not nxt:
        return None
    rows = conn.execute("SELECT outcome FROM reviews ORDER BY id DESC LIMIT 100").fetchall()
    if len(rows) < 100:
        return None
    acc = sum(1 for (o,) in rows if o in ("correct", "override")) / len(rows)
    if acc >= 0.85:
        return (f"Last 100 answers: {acc:.0%} right. Ready for the {TENSES[nxt][2]}? "
                f"verbos tenses add {nxt}")
    return None


def resolve_verb(verbs, name: str) -> str:
    name = expand_shortcuts(name.lower())
    if name in verbs:
        return name
    folded = {fold(v): v for v in verbs}
    if fold(name) in folded:
        return folded[fold(name)]
    close = difflib.get_close_matches(name, list(verbs), n=5)
    hint = f" Close: {', '.join(close)}." if close else ""
    sys.exit(f"{name} is not in the database (637 verbs).{hint}")


def resolve_tense(name: str) -> str:
    if name in TENSES:
        return name
    for k, (_m, _t, es, en) in TENSES.items():
        if name.lower() in (es, en, fold(es)):
            return k
    sys.exit(f"unknown tense {name}; keys: {', '.join(TENSES)}")


def resolve_person(name: str) -> str:
    if name in PERSONS:
        return name
    p = PERSON_ALIASES.get(fold(name.lower())) or PERSON_ALIASES.get(name.lower())
    if not p:
        sys.exit(f"unknown person {name}; use 1s 2s 3s 1p 2p 3p or yo, tú, él, nosotros, ellos")
    return p


def cmd_look(args, verbs, rank, aux) -> None:
    inf = resolve_verb(verbs, args.verb)
    v = verbs[inf]
    conn = connect()
    persons = active_persons(conn)
    tenses = [resolve_tense(t) for t in args.tense] if args.tense else STAGES
    r = rank.get(inf)
    print(f"{bold(inf)}  {v['gloss']}")
    print(dim(f"gerundio {v['gerund']} · participio {v['participle']}"
              + (f" · frequency rank {r}" if r else "")))
    width = max(len(TENSES[t][2]) for t in tenses)
    for t in tenses:
        cells = []
        for p in persons:
            form = v["forms"][t][p]
            if not form:
                continue
            mark = "*" if is_irregular(verbs, inf, t, p, aux) else ""
            cells.append(form + mark)
        print(f"  {TENSES[t][2]:<{width}}  " + " · ".join(cells))
    print(dim("  * differs from the regular pattern. Persons: "
              + ", ".join(PERSON_NAMES[p] for p in persons)))


def cmd_check(args, verbs, rank, aux) -> None:
    for raw in args.form:
        text = normalize(raw)
        exact, loose = [], []
        for inf, v in verbs.items():
            for t, row in v["forms"].items():
                for p, form in row.items():
                    if not form:
                        continue
                    if form == text:
                        exact.append((inf, t, p))
                    elif fold(form) == fold(text):
                        loose.append((inf, t, p, form))
        if exact:
            print(f"{bold(text)}: " + "; ".join(f"{i} · {describe_cell(t, p)}" for i, t, p in exact))
        elif loose:
            print(f"{bold(text)}: not a form as spelled. With accents: "
                  + "; ".join(f"{f} ({i} · {describe_cell(t, p)})" for i, t, p, f in loose))
        else:
            print(f"{bold(text)}: no match in the database. "
                  "It may be misspelled, or its verb may be one of the 637 not covered.")


def cmd_record(args, verbs, rank, aux) -> None:
    inf = resolve_verb(verbs, args.verb)
    tense = resolve_tense(args.tense)
    person = resolve_person(args.person)
    rating = RATING_NAMES.get(args.rating.lower())
    if rating is None:
        if args.rating not in ("1", "2", "3", "4"):
            sys.exit("rating is again, hard, good or easy (or 1-4)")
        rating = int(args.rating)
    expected = verbs[inf]["forms"][tense][person]
    if not expected:
        sys.exit(f"{inf} has no {describe_cell(tense, person)} form")
    conn = connect()
    now = utcnow()
    card = (load_card(conn, f"{inf}|{tense}|{person}")
            or new_card(inf, tense, person, now, origin=args.source))
    updated = schedule(card, rating, now)
    save_card(conn, updated)
    outcome = {AGAIN: "wrong", HARD: "accent", GOOD: "correct", EASY: "correct"}[rating]
    log_review(conn, card["card_id"], now, rating, outcome, args.answer, expected, None,
               source=args.source, note=args.note)
    conn.commit()
    when = parse_ts(updated["due"]).astimezone().strftime("%a %d %b")
    print(f"recorded {inf} · {describe_cell(tense, person)} → {expected}: "
          f"{args.rating}; next due {when}")


def cmd_stats(args, verbs, rank, aux) -> None:
    conn = connect()
    now = utcnow()
    n_cards = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    n_rev = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    week = ts(now - timedelta(days=7))
    recent = conn.execute("SELECT outcome FROM reviews WHERE ts >= ?", (week,)).fetchall()
    acc = (sum(1 for (o,) in recent if o in ("correct", "override")) / len(recent)) if recent else None
    due_now = conn.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (ts(now),)).fetchone()[0]
    mature = conn.execute("SELECT COUNT(*) FROM cards WHERE stability >= 21").fetchone()[0]
    hard = conn.execute(
        "SELECT c.verb, c.tense, c.person, c.lapses, "
        " (SELECT GROUP_CONCAT(answer, ', ') FROM (SELECT answer FROM reviews r"
        "   WHERE r.card_id = c.card_id AND r.outcome IN ('wrong') AND answer IS NOT NULL"
        "   ORDER BY r.id DESC LIMIT 3)) AS wrong"
        " FROM cards c WHERE c.lapses > 0 OR EXISTS (SELECT 1 FROM reviews r WHERE"
        "  r.card_id = c.card_id AND r.outcome IN ('wrong','reveal'))"
        " ORDER BY c.lapses DESC, c.difficulty DESC LIMIT ?", (args.top,)).fetchall()
    if args.brief:
        acc_s = f"{acc:.0%}" if acc is not None else "n/a"
        weak = "; ".join(
            f"{h['verb']} {h['tense']} {h['person']} → {verbs[h['verb']]['forms'][h['tense']][h['person']]}"
            + (f" (wrote {h['wrong']})" if h["wrong"] else "")
            for h in hard)
        print(f"tenses: {','.join(enabled_tenses(conn))}; cards {n_cards}, mature {mature}, "
              f"due now {due_now}; 7-day accuracy {acc_s} over {len(recent)}; "
              f"focus: {','.join(sorted(focus_verbs(conn))) or 'none'}; weakest: {weak or 'none yet'}")
        return
    print(bold("verbos"))
    print(f"  tenses on: {', '.join(TENSES[t][2] for t in enabled_tenses(conn))}")
    print(f"  cards: {n_cards} ({mature} mature, stability ≥ 21 d); reviews: {n_rev}")
    print(f"  due now: {due_now}")
    if acc is not None:
        print(f"  last 7 days: {len(recent)} answers, {acc:.0%} right")
    by_tense = conn.execute(
        "SELECT c.tense, COUNT(*), SUM(r.outcome IN ('correct','override'))"
        " FROM reviews r JOIN cards c USING (card_id) WHERE r.ts >= ? GROUP BY c.tense",
        (ts(now - timedelta(days=30)),)).fetchall()
    if by_tense:
        print("  last 30 days by tense:")
        for t, total, ok in sorted(by_tense, key=lambda x: STAGES.index(x[0])):
            print(f"    {TENSES[t][2]:<26} {ok}/{total} ({ok / total:.0%})")
    if hard:
        print("  trouble spots:")
        for h in hard:
            form = verbs[h["verb"]]["forms"][h["tense"]][h["person"]]
            extra = f"  (you wrote {h['wrong']})" if h["wrong"] else ""
            print(f"    {h['verb']} · {describe_cell(h['tense'], h['person'])} → {form}{dim(extra)}")
    forecast = []
    for d in range(1, 8):
        end = ts(now + timedelta(days=d))
        forecast.append(conn.execute("SELECT COUNT(*) FROM cards WHERE due <= ?", (end,)).fetchone()[0])
    print(dim("  due by day, next 7 days (cumulative): " + " ".join(map(str, forecast))))


def cmd_tenses(args, verbs, rank, aux) -> None:
    conn = connect()
    enabled = enabled_tenses(conn)
    if args.action in ("add", "remove"):
        for name in args.keys:
            t = resolve_tense(name)
            if args.action == "add" and t not in enabled:
                enabled.append(t)
            elif args.action == "remove" and t in enabled:
                enabled.remove(t)
        enabled = [t for t in STAGES if t in enabled]
        set_setting(conn, "tenses", ",".join(enabled))
    for t in STAGES:
        mark = green("on ") if t in enabled else dim("off")
        print(f"  {mark} {t:<10} {TENSES[t][2]} ({TENSES[t][3]})")


def cmd_focus(args, verbs, rank, aux) -> None:
    conn = connect()
    focus = focus_verbs(conn)
    if args.action in ("add", "remove"):
        for name in args.verbs:
            inf = resolve_verb(verbs, name)
            if args.action == "add":
                focus.add(inf)
            else:
                focus.discard(inf)
        set_setting(conn, "focus", ",".join(sorted(focus)))
    print("focus verbs: " + (", ".join(sorted(focus)) or "none"))


def cmd_set(args, verbs, rank, aux) -> None:
    conn = connect()
    key = args.key.replace("-", "_")
    if key not in DEFAULTS or key in ("tenses", "focus"):
        sys.exit("settable: new-per-day, session-size, vosotros (use 'tenses' and 'focus' for those)")
    if args.value is not None:
        if key == "vosotros" and args.value not in ("on", "off"):
            sys.exit("vosotros takes on or off")
        if key != "vosotros" and not args.value.isdigit():
            sys.exit(f"{args.key} takes a number")
        set_setting(conn, key, args.value)
    for k in ("new_per_day", "session_size", "vosotros"):
        print(f"  {k.replace('_', '-')}: {get_setting(conn, k)}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="verbos", description="Spanish verb-form drill with spaced repetition.")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("drill", help="practise (the default)")
    d.add_argument("-n", type=int, help="session size")
    lk = sub.add_parser("look", help="show a verb's forms")
    lk.add_argument("verb")
    lk.add_argument("tense", nargs="*", help="tense keys (default: all)")
    ck = sub.add_parser("check", help="which verb, tense and person is this form?")
    ck.add_argument("form", nargs="+")
    rc = sub.add_parser("record", help="log a result from outside the drill (coach sessions)")
    rc.add_argument("verb")
    rc.add_argument("tense")
    rc.add_argument("person")
    rc.add_argument("rating", help="again, hard, good or easy")
    rc.add_argument("--answer")
    rc.add_argument("--note")
    rc.add_argument("--source", default="coach")
    st = sub.add_parser("stats", help="progress and trouble spots")
    st.add_argument("--brief", action="store_true")
    st.add_argument("--top", type=int, default=10)
    tn = sub.add_parser("tenses", help="list, add or remove tenses")
    tn.add_argument("action", nargs="?", choices=["add", "remove"])
    tn.add_argument("keys", nargs="*")
    fc = sub.add_parser("focus", help="verbs to bring forward")
    fc.add_argument("action", nargs="?", choices=["add", "remove"])
    fc.add_argument("verbs", nargs="*")
    se = sub.add_parser("set", help="new-per-day, session-size, vosotros")
    se.add_argument("key")
    se.add_argument("value", nargs="?")
    args = ap.parse_args(argv)
    if args.cmd is None:
        args = ap.parse_args(["drill", *(argv or [])])
    verbs = load_verbs()
    rank = load_rank()
    aux = auxiliaries(verbs)
    try:
        {"drill": cmd_drill, "look": cmd_look, "check": cmd_check, "record": cmd_record,
         "stats": cmd_stats, "tenses": cmd_tenses, "focus": cmd_focus, "set": cmd_set}[args.cmd](
            args, verbs, rank, aux)
    finally:
        close_all()


if __name__ == "__main__":
    main()

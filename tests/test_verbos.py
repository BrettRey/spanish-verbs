"""Run with: python3 -m unittest discover -s tests"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import verbos as vb  # noqa: E402

VERBS = vb.load_verbs()
RANK = vb.load_rank()
AUX = vb.auxiliaries(VERBS)


def grade(inf, tense, person, answer):
    return vb.grade(VERBS, AUX, inf, tense, person, answer)


class Data(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(VERBS), 637)
        self.assertEqual(len(RANK), 637)

    def test_every_verb_has_every_staged_tense(self):
        for inf, v in VERBS.items():
            self.assertEqual(set(v["forms"]), set(vb.TENSES), inf)

    def test_auxiliaries_come_from_the_database(self):
        self.assertEqual(AUX["perf"]["1s"], "he")
        self.assertEqual(AUX["plusc"]["3p"], "habían")


class Irregularity(unittest.TestCase):
    def check(self, inf, tense, person, expected):
        self.assertEqual(vb.is_irregular(VERBS, inf, tense, person, AUX), expected,
                         (inf, tense, person, VERBS[inf]["forms"][tense][person],
                          vb.regular_form(inf, tense, person, AUX)))

    def test_irregular_cells(self):
        for args in [("tener", "pres", "1s"), ("empezar", "pres", "1s"), ("saber", "pres", "1s"),
                     ("ir", "pres", "1s"), ("venir", "pres", "1s"), ("hacer", "perf", "1s"),
                     ("buscar", "pret", "1s"), ("pedir", "pret", "3s"), ("ir", "imp", "2s"),
                     ("tener", "fut", "1s")]:
            self.check(*args, True)

    def test_regular_cells(self):
        for args in [("hablar", "pres", "1s"), ("comer", "pres", "2s"), ("vivir", "pres", "3p"),
                     ("hablar", "perf", "1s"), ("comer", "impf", "1p"), ("hablar", "subjimpf", "1p"),
                     ("levantarse", "pres", "1s"), ("levantarse", "imp", "2s"),
                     ("levantarse", "imp", "1p"), ("levantarse", "impneg", "2s"),
                     ("tener", "pres", "1p"), ("hablar", "imp", "2s")]:
            self.check(*args, False)


class Grading(unittest.TestCase):
    def test_correct(self):
        self.assertEqual(grade("tener", "pres", "1s", "tengo")[0], "correct")
        self.assertEqual(grade("tener", "pres", "1s", "Yo tengo.")[0], "correct")
        self.assertEqual(grade("tener", "impf", "1s", "teni'a")[0], "correct")
        self.assertEqual(grade("hablar", "subjimpf", "1s", "hablase")[0], "correct")
        self.assertEqual(grade("hablar", "subjimpf", "1p", "hablásemos")[0], "correct")
        self.assertEqual(grade("tener", "impneg", "2s", "tengas")[0], "correct")
        self.assertEqual(grade("tener", "impneg", "2s", "no tengas")[0], "correct")

    def test_accent_slip(self):
        self.assertEqual(grade("tener", "impf", "1s", "tenia")[0], "accent")

    def test_accent_that_changes_the_form_is_wrong(self):
        outcome, msg = grade("hablar", "pret", "3s", "hablo")
        self.assertEqual(outcome, "wrong")
        self.assertIn("presente", msg)

    # Errors from Brett's November 2025 session
    def test_overregularised_yo(self):
        for inf, typed in [("tener", "teno"), ("venir", "veno"), ("empezar", "empezo")]:
            outcome, msg = grade(inf, "pres", "1s", typed)
            self.assertEqual(outcome, "wrong")
            self.assertIn("regular pattern", msg, (inf, typed, msg))

    def test_tense_intrusion(self):
        outcome, msg = grade("saber", "pres", "1s", "supo")
        self.assertEqual(outcome, "wrong")
        self.assertIn("pretérito", msg)
        outcome, msg = grade("comer", "pres", "1s", "comio")
        self.assertEqual(outcome, "wrong")
        self.assertIn("pretérito", msg)

    def test_reflexive_without_pronoun(self):
        self.assertEqual(grade("levantarse", "pres", "1s", "levanto")[0], "pronoun")


class Scheduler(unittest.TestCase):
    def card(self):
        return vb.new_card("tener", "pres", "1s", vb.utcnow())

    def test_first_ratings(self):
        now = vb.utcnow()
        easy = vb.schedule(self.card(), vb.EASY, now)
        self.assertEqual(vb.interval_days(easy["stability"]), 8)
        again = vb.schedule(self.card(), vb.AGAIN, now)
        gap = vb.parse_ts(again["due"]) - now  # stored to the second
        self.assertLess(abs(gap - timedelta(minutes=10)), timedelta(seconds=1))

    def test_retrievability_is_retention_at_stability(self):
        self.assertAlmostEqual(vb.retrievability(5.0, 5.0), 0.9, places=6)

    def test_success_grows_and_failure_shrinks_stability(self):
        now = vb.utcnow()
        c = vb.schedule(self.card(), vb.GOOD, now)
        later = now + timedelta(days=3)
        self.assertGreater(vb.schedule(c, vb.GOOD, later)["stability"], c["stability"])
        failed = vb.schedule(c, vb.AGAIN, later)
        self.assertLess(failed["stability"], c["stability"])
        self.assertEqual(failed["lapses"], 1)


class Storage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["VERBOS_DB"] = str(Path(self.tmp.name) / "t.sqlite")

    def tearDown(self):
        vb.close_all()
        del os.environ["VERBOS_DB"]
        self.tmp.cleanup()

    def test_no_vosotros_and_no_empty_cells(self):
        conn = vb.connect()
        vb.set_setting(conn, "tenses", ",".join(vb.TENSES))
        picks = vb.pick_new(conn, VERBS, RANK, AUX, 5000)
        self.assertTrue(picks)
        self.assertFalse([p for p in picks if p[2] == "2p"])
        self.assertFalse([p for p in picks if not VERBS[p[0]]["forms"][p[1]][p[2]]])

    def test_focus_verbs_come_first(self):
        conn = vb.connect()
        vb.set_setting(conn, "focus", "empezar")
        picks = vb.pick_new(conn, VERBS, RANK, AUX, 3)
        self.assertEqual({p[0] for p in picks}, {"empezar"})

    def test_record_and_stats(self):
        out = io.StringIO()
        with redirect_stdout(out):
            vb.main(["record", "tener", "pret", "yo", "again", "--answer", "tenía"])
            vb.main(["stats", "--brief"])
            vb.main(["stats"])
        text = out.getvalue()
        self.assertIn("tuve", text)
        conn = vb.connect()
        due = vb.due_cards(conn, vb.utcnow() + timedelta(hours=1), 10)
        self.assertEqual([c["card_id"] for c in due], ["tener|pret|1s"])  # coach card, tense not enabled


if __name__ == "__main__":
    unittest.main()

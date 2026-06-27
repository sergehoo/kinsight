"""Tests du domaine pur — moteur d'alertes."""

import unittest

from k_insight.kpi.alerts import AlertRule, most_severe, triggers


class AlertEngineTest(unittest.TestCase):
    def setUp(self):
        self.rules = [
            AlertRule("crit", "Critique", "<", 60, "critical"),
            AlertRule("warn", "Vigilance", "<", 70, "warning"),
        ]

    def test_none_ne_declenche_jamais(self):
        self.assertFalse(triggers(self.rules[0], None))
        self.assertIsNone(most_severe(self.rules, None))

    def test_garde_la_plus_severe(self):
        a = most_severe(self.rules, 55)  # franchit < 60 ET < 70 → critical
        self.assertIsNotNone(a)
        self.assertEqual(a.severity, "critical")
        self.assertEqual(a.rule_id, "crit")

    def test_seuil_intermediaire(self):
        a = most_severe(self.rules, 65)  # franchit seulement < 70
        self.assertEqual(a.severity, "warning")

    def test_aucun_declenchement(self):
        self.assertIsNone(most_severe(self.rules, 80))

    def test_operateur_et_severite_valides(self):
        with self.assertRaises(ValueError):
            AlertRule("x", "x", "≈", 1, "warning")
        with self.assertRaises(ValueError):
            AlertRule("x", "x", "<", 1, "panic")


if __name__ == "__main__":
    unittest.main()

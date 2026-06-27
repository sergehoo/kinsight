"""Tests du Human Capital Score (domaine pur)."""

import unittest

from k_insight.kpi.hr_score import HC_DIMENSIONS, human_capital_score, total_weight


class HumanCapitalScoreTest(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(total_weight(), 100)
        self.assertEqual(len(HC_DIMENSIONS), 9)

    def test_all_dimensions_full(self):
        scores = {d.key: 100 for d in HC_DIMENSIONS}
        self.assertEqual(human_capital_score(scores), 100.0)

    def test_weighted_average(self):
        # productivité (poids 15) à 60, conformité (poids 5) à 100 → 70.0
        score = human_capital_score({"productivite": 60, "conformite": 100})
        self.assertEqual(score, round((60 * 15 + 100 * 5) / 20, 1))

    def test_partial_renormalised(self):
        # une seule dimension fournie → le score vaut cette dimension
        self.assertEqual(human_capital_score({"performance": 82}), 82.0)

    def test_unknown_keys_ignored(self):
        self.assertEqual(human_capital_score({"inconnu": 50, "performance": 90}), 90.0)

    def test_no_data_returns_none(self):
        self.assertIsNone(human_capital_score({}))
        self.assertIsNone(human_capital_score({"inconnu": 50}))

    def test_clamped(self):
        self.assertEqual(human_capital_score({"performance": 150}), 100.0)
        self.assertEqual(human_capital_score({"performance": -10}), 0.0)


if __name__ == "__main__":
    unittest.main()

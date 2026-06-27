"""Tests du domaine pur — Indice de Gouvernance Groupe (group_score)."""

import unittest

from k_insight.kpi.group_score import (
    GROUP_DOMAIN_WEIGHTS,
    group_governance_index,
    total_weight,
)


class GroupGovernanceIndexTest(unittest.TestCase):
    def test_weights_sum_to_100(self):
        self.assertEqual(total_weight(), 100)
        self.assertEqual(sum(GROUP_DOMAIN_WEIGHTS.values()), 100)

    def test_none_si_vide(self):
        self.assertIsNone(group_governance_index({}))

    def test_moyenne_ponderee_complete(self):
        # tous les domaines à 80 -> 80
        scores = {k: 80.0 for k in GROUP_DOMAIN_WEIGHTS}
        self.assertEqual(group_governance_index(scores), 80.0)

    def test_renormalisation_partielle(self):
        # seulement immobilier (22) et capital-humain (16) disponibles
        # (80*16 + 70*22) / 38 = 74.2
        self.assertEqual(
            group_governance_index({"capital-humain": 80, "immobilier": 70}),
            74.2,
        )

    def test_domaines_inconnus_ignores(self):
        self.assertEqual(group_governance_index({"inexistant": 50, "finance": 90}), 90.0)


if __name__ == "__main__":
    unittest.main()

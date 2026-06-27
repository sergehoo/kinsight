"""Tests du domaine pur — ancrage IA (résolution catalogue + refus)."""

import unittest

from k_insight.semantic.grounding import answer, resolve_metric
from k_insight.semantic.registry import CATALOG


class GroundingTest(unittest.TestCase):
    def test_resolution_par_cle_explicite(self):
        m = resolve_metric(CATALOG, "donne-moi finance.dso ce mois-ci")
        self.assertIsNotNone(m)
        self.assertEqual(m.key, "finance.dso")

    def test_resolution_par_mots_cles(self):
        m = resolve_metric(CATALOG, "quel est le taux de commercialisation des programmes ?")
        self.assertIsNotNone(m)
        self.assertEqual(m.domain, "immobilier")
        self.assertIn("commercialisation", m.key)

    def test_refus_si_hors_catalogue(self):
        m = resolve_metric(CATALOG, "donne-moi la météo à Abidjan demain")
        self.assertIsNone(m)
        a = answer(CATALOG, "donne-moi la météo à Abidjan demain", lambda k: 999.0)
        self.assertFalse(a["grounded"])
        self.assertIsNone(a["metric"])
        self.assertIsNone(a["value"])

    def test_valeur_gouvernee_nd(self):
        # métrique connue mais source non branchée → N/D, jamais de chiffre inventé
        a = answer(CATALOG, "finance.dso", lambda k: None)
        self.assertTrue(a["grounded"])
        self.assertIsNone(a["value"])
        self.assertIn("N/D", a["answer"])
        self.assertEqual(a["source"], "mart.finance_kpi")

    def test_valeur_reelle_citee_avec_source(self):
        a = answer(CATALOG, "finance.dso", lambda k: 42.0)
        self.assertTrue(a["grounded"])
        self.assertEqual(a["value"], 42.0)
        self.assertIn("mart.finance_kpi", a["answer"])


if __name__ == "__main__":
    unittest.main()

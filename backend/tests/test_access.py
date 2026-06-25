"""Tests du filtrage par périmètre multi-filiales (ADR-0005)."""

import unittest

from k_insight.access import Scope, filter_by_scope

ROWS = [
    {"subsidiary": "KRE", "v": 1},
    {"subsidiary": "KSH", "v": 2},
    {"subsidiary": "MYK", "v": 3},
]
KEY = lambda r: r["subsidiary"]  # noqa: E731


class ScopeTest(unittest.TestCase):
    def test_group_voit_tout(self):
        s = Scope.group()
        self.assertTrue(s.allows("KRE"))
        self.assertEqual(filter_by_scope(ROWS, s, KEY), ROWS)

    def test_perimetre_restreint(self):
        s = Scope.of("KRE", "KSH")
        self.assertTrue(s.allows("KRE"))
        self.assertFalse(s.allows("MYK"))
        out = filter_by_scope(ROWS, s, KEY)
        self.assertEqual([r["subsidiary"] for r in out], ["KRE", "KSH"])

    def test_aucun_acces(self):
        s = Scope.none()
        self.assertFalse(s.allows("KRE"))
        self.assertEqual(filter_by_scope(ROWS, s, KEY), [])


if __name__ == "__main__":
    unittest.main()

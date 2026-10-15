"""HRDecisionEngine (lot 8).

Ce qui est protégé : les constats sont déterministes et chiffrés sur l'historique
réel ; aucun n'est fabriqué pour atteindre un quota ; un périmètre restreint n'en
reçoit aucun tiré des chiffres Groupe ; la synthèse IA ne peut PAS introduire un
nombre absent des constats, et ses causes sont marquées comme hypothèses.
"""

from __future__ import annotations

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.ai_copilot.providers import ProviderResult
from apps.audit.models import AccessLog
from apps.organizations.models import Subsidiary

from . import filtres as F
from .decision_rh import HRDecisionEngine, garde_fou, _nombres
from .models import Dimension, KpiSnapshot
from .tests_historique import HIER, _poser

User = get_user_model()


def _jours(debut_recul, n, presents, absents, retards=0):
    for i in range(debut_recul, debut_recul + n):
        jour = HIER - timedelta(days=i)
        _poser("hr.presents_jour", jour, presents)
        _poser("hr.absents_jour", jour, absents)
        _poser("hr.retards_jour", jour, retards)


def _site(code, nom, presents, absents, retards=0):
    for metric_id, v in (("hr.presents_jour", presents), ("hr.absents_jour", absents), ("hr.retards_jour", retards)):
        _poser(metric_id, HIER, v, dimension=Dimension.SITE, code=code)
    KpiSnapshot.objects.filter(dimension=Dimension.SITE, code=code).update(libelle=nom)


class _FauxRouteur:
    def __init__(self, texte, fournisseur="claude"):
        self.texte, self.fournisseur, self.consigne = texte, fournisseur, None

    def complete(self, message, context, facts):
        self.consigne = message
        return ProviderResult(text=self.texte, provider=self.fournisseur, latency_ms=1, grounded=True)


class ConstatsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.drh = User.objects.create_user("drh.d", password=None, role="DRH", is_group_scope=True)
        kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh_kre = User.objects.create_user("drh.d.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(kre)

    def _moteur(self, user=None, **params):
        filtres = F.lire({"periode": "7j", **params}, timezone.localdate())
        return HRDecisionEngine(user or self.drh, filtres)

    def test_rien_a_signaler_n_est_pas_comble(self):
        _jours(0, 7, 95, 5)
        self.assertEqual(self._moteur().constats(), [], "aucun constat fabriqué pour atteindre trois")

    def test_signal_en_surveillance_devient_un_constat_chiffre(self):
        _jours(0, 7, 80, 20)
        _jours(7, 7, 82, 18)
        constats = {c["id"]: c for c in self._moteur().constats()}
        c = constats["signal.presence_faible"]
        self.assertEqual(c["severite"], "surveillance")
        self.assertIn("80 %", c["constat"])
        self.assertIn("−2 pts vs période précédente", c["constat"])
        self.assertEqual((c["source"], c["confiance"], c["periode"]), ("Kaydan Shield", "élevée", "7 derniers jours"))
        self.assertTrue(c["action"])
        self.assertTrue(c["lien"].startswith("/dashboard/capital-humain/"))

    def test_variation_notable_sur_une_presence_normale(self):
        _jours(0, 7, 90, 10)
        _jours(7, 7, 95, 5)
        constats = {c["id"]: c for c in self._moteur().constats()}
        self.assertIn("variation.presence", constats)
        self.assertIn("−5 pts", constats["variation.presence"]["constat"])

    def test_sites_loin_du_groupe_et_retards_concentres(self):
        _jours(0, 7, 80, 20)
        _site("1", "Chantier A", 60, 40, retards=10)
        _site("2", "Chantier B", 95, 5, retards=8)
        _site("3", "Siège", 90, 10, retards=6)
        _site("4", "Dépôt", 85, 15, retards=1)
        constats = {c["id"]: c for c in self._moteur().constats()}
        ecart = constats["ecart.sites"]
        self.assertIn("Chantier A : présence 60 %, −20 pts vs Groupe", ecart["constat"])
        concentration = constats["concentration.retards"]
        self.assertIn("96 % des retards", concentration["constat"])
        self.assertEqual(len(concentration["details"]), 3)

    def test_historique_mince(self):
        _jours(0, 2, 90, 10)
        ids = [c["id"] for c in self._moteur().constats()]
        self.assertIn("couverture.mince", ids)

    def test_tri_et_plafond(self):
        _jours(0, 7, 50, 50, retards=20)
        for i in range(6):
            _site(str(i), f"Site {i}", 20 + i, 80 - i, retards=10 - i)
        constats = self._moteur().constats()
        self.assertLessEqual(len(constats), 7)
        rang = {"critique": 0, "surveillance": 1, "info": 2}
        self.assertEqual([c["severite"] for c in constats], sorted((c["severite"] for c in constats), key=rang.get))
        self.assertEqual(constats[0]["severite"], "critique")

    def test_perimetre_restreint_sans_chiffres_groupe(self):
        _jours(0, 7, 50, 50)
        _site("1", "Chantier A", 20, 80)
        moteur = self._moteur(self.drh_kre)
        self.assertEqual(moteur.constats(), [])
        self.assertTrue(any("Non rattaché" in a["motif"] for a in moteur.angles_morts()))


# Aucun appel réseau en test : sans clé, le routeur retombe sur le repli ancré.
SANS_MODELE = override_settings(DEEPSEEK_API_KEY="", ANTHROPIC_API_KEY="")


@SANS_MODELE
class SyntheseTest(TestCase):
    setUp = ConstatsTest.setUp
    _moteur = ConstatsTest._moteur

    def test_sans_modele_la_synthese_est_celle_des_constats(self):
        _jours(0, 7, 80, 20)
        moteur = self._moteur()
        constats = moteur.constats()
        s = moteur.synthese(constats)
        self.assertFalse(s["ia"])
        self.assertEqual(s["sections"]["hypotheses"], [], "aucune cause avancée sans analyse")
        self.assertTrue(s["sections"]["questions"], "les angles morts deviennent des questions")

    def test_le_garde_fou_retire_les_chiffres_inventes(self):
        _jours(0, 7, 80, 20)
        moteur = self._moteur()
        constats = moteur.constats()
        reponse = json.dumps({
            "resume": ["La présence est de 80 % sur la période.", "Le turnover atteint 12 % ce trimestre."],
            "hypotheses": ["Les plannings de chantier ont changé."],
            "recommandations": ["Revoir les plannings avec les responsables de site."],
        }, ensure_ascii=False)
        routeur = _FauxRouteur("Voici : " + reponse)
        s = moteur.synthese(constats, router=routeur)
        self.assertTrue(s["ia"])
        self.assertEqual(s["phrases_retirees"], 1)
        self.assertEqual(s["sections"]["resume"], ["La présence est de 80 % sur la période."])
        self.assertTrue(s["sections"]["hypotheses"][0].startswith("Hypothèse : "))
        self.assertIn("80", routeur.consigne, "le modèle reçoit les constats, et eux seuls")

    def test_reponse_illisible(self):
        _jours(0, 7, 80, 20)
        moteur = self._moteur()
        s = moteur.synthese(moteur.constats(), router=_FauxRouteur("pas de JSON ici"))
        self.assertFalse(s["ia"])
        self.assertIn("illisible", s["note"])

    def test_extraction_des_nombres(self):
        self.assertEqual(_nombres("présence 81,8 % et 3 sites"), {81.8, 3.0})
        propre, n = garde_fou({"resume": ["7 jours", "42 sites"]}, autorises={7.0})
        self.assertEqual((propre["resume"], n), (["7 jours"], 1))


@SANS_MODELE
class DecisionApiTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.drh = User.objects.create_user("drh.api", password=None, role="DRH", is_group_scope=True)
        self.lecteur = User.objects.create_user("lect.api", password=None, role="READER", is_group_scope=True)
        _jours(0, 7, 80, 20)

    def test_constats_et_synthese_sur_demande(self):
        self.client.force_authenticate(self.drh)
        d = self.client.get("/api/v1/governance/hr/decision/?periode=7j").json()
        self.assertTrue(d["constats"])
        self.assertIsNone(d["synthese"])
        d = self.client.get("/api/v1/governance/hr/decision/?periode=7j&synthese=1").json()
        self.assertIn("resume", d["synthese"]["sections"])
        trace = AccessLog.objects.filter(action="query_hr_decision").last()
        self.assertIn("signal.presence_faible", trace.payload["constats"])

    def test_lecteur_refuse(self):
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(self.client.get("/api/v1/governance/hr/decision/").status_code, 403)

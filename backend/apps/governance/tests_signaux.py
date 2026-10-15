"""Signaux RH et seuils arbitrés (lot 7).

Ce qui est protégé : un signal ne se dit « normal » que sur une mesure ; un
périmètre restreint ne reçoit jamais un signal calculé sur les chiffres Groupe ;
un seuil ne se règle que par la DRH Groupe, dans le bon ordre, et la valeur
arbitrée est celle que jugent AUSSI les constats du jour.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.audit.models import AccessLog
from apps.integrations import shield_rules as R
from apps.organizations.models import Subsidiary

from .models import Dimension, KpiSnapshot, SeuilRh
from .tests_historique import HIER, _poser

User = get_user_model()
URL_SIGNAUX = "/api/v1/governance/hr/signaux/"
URL_SEUILS = "/api/v1/governance/hr/seuils/"


class SignauxTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh = User.objects.create_user("drh.s", password=None, role="DRH", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh.s.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(self.kre)
        self.lecteur = User.objects.create_user("lect.s", password=None, role="READER", is_group_scope=True)
        # 7 jours : 80 présents, 20 absents, 12 retards → présence 80 %, retard 15 %.
        for i in range(7):
            jour = HIER - timedelta(days=i)
            _poser("hr.presents_jour", jour, 80)
            _poser("hr.absents_jour", jour, 20)
            _poser("hr.retards_jour", jour, 12)

    def _signaux(self, user=None, **params):
        self.client.force_authenticate(user or self.drh)
        query = "&".join(f"{k}={v}" for k, v in {"periode": "7j", **params}.items())
        r = self.client.get(f"{URL_SIGNAUX}?{query}")
        self.assertEqual(r.status_code, 200, r.content)
        return {s["cle"]: s for s in r.json()["signaux"]}, r.json()

    def test_presence_en_surveillance_avec_justification(self):
        s, _ = self._signaux()
        p = s["presence_faible"]
        self.assertEqual((p["valeur"], p["etat"]), (80.0, "surveillance"))   # 70 ≤ 80 < 85
        self.assertEqual(p["seuils"]["surveillance"], 85.0)
        self.assertTrue(p["seuils"]["par_defaut"])
        self.assertEqual(p["source"], "Kaydan Shield")
        self.assertEqual(p["confiance"], "élevée")
        self.assertEqual(p["couverture"]["jours_mesures"], 7)

    def test_retard_est_le_complement_de_la_ponctualite(self):
        s, _ = self._signaux()
        self.assertEqual(s["retard_eleve"]["valeur"], 15.0)
        self.assertEqual(s["retard_eleve"]["etat"], "normal", "15 % n'est pas > 15 %")

    def test_sans_source_jamais_normal(self):
        s, data = self._signaux()
        for cle in ("turnover_eleve", "contrat_echeance", "recrutement_sous_cible", "heures_sup_elevees"):
            self.assertEqual(s[cle]["etat"], "non_mesure")
            self.assertTrue(s[cle]["motif"])
        self.assertEqual(data["compteurs"]["non_mesure"], 6)   # + site et effectif sans historique

    def test_tri_par_criticite(self):
        _, data = self._signaux()
        ordre = [x["etat"] for x in data["signaux"]]
        rang = {"critique": 0, "surveillance": 1, "normal": 2, "non_mesure": 3}
        self.assertEqual(ordre, sorted(ordre, key=rang.get))

    def test_site_sous_effectif_et_filtres(self):
        for code, nom, p, a in (("1", "Chantier A", 45, 55), ("2", "Siège", 95, 5)):
            _poser("hr.presents_jour", HIER, p, dimension=Dimension.SITE, code=code)
            _poser("hr.absents_jour", HIER, a, dimension=Dimension.SITE, code=code)
            KpiSnapshot.objects.filter(dimension=Dimension.SITE, code=code).update(libelle=nom)
        s, _ = self._signaux()
        site = s["site_sous_effectif"]
        self.assertEqual((site["etat"], site["valeur"]), ("critique", 45.0))
        self.assertEqual([d["libelle"] for d in site["details"]], ["Chantier A"])
        # Sous un filtre site, le signal ne juge que ce site.
        s, _ = self._signaux(site="2")
        self.assertEqual(s["site_sous_effectif"]["etat"], "normal")
        # Sous un filtre type, le croisement n'existe pas : non mesuré, avec motif.
        s, _ = self._signaux(type="employee")
        self.assertEqual(s["site_sous_effectif"]["etat"], "non_mesure")
        self.assertIn("croisement site × type", s["site_sous_effectif"]["motif"])

    def test_baisse_d_effectif(self):
        _poser("hr.effectif_total", HIER, 900)
        _poser("hr.effectif_total", HIER - timedelta(days=8), 1000)
        s, _ = self._signaux()
        e = s["effectif_critique"]
        self.assertEqual((e["valeur"], e["etat"], e["effectif"]), (10.0, "surveillance", 900))

    def test_perimetre_restreint_ne_recoit_pas_le_groupe(self):
        s, _ = self._signaux(self.drh_kre)
        for cle in ("presence_faible", "absenteisme", "retard_eleve", "site_sous_effectif"):
            self.assertEqual(s[cle]["etat"], "non_mesure")
            self.assertIsNone(s[cle]["valeur"])
            self.assertIn("Non rattaché", s[cle]["motif"])

    def test_filtre_hors_perimetre_refuse(self):
        Subsidiary.objects.create(code="KSH", name="Kaydan Shield")
        self.client.force_authenticate(self.drh_kre)
        self.assertEqual(self.client.get(f"{URL_SIGNAUX}?subsidiary=KSH").status_code, 403)

    def test_lecteur_sans_domaine_rh(self):
        self.client.force_authenticate(self.lecteur)
        self.assertEqual(self.client.get(URL_SIGNAUX).status_code, 403)
        self.assertEqual(self.client.get(URL_SEUILS).status_code, 403)

    def test_lecture_tracee(self):
        self._signaux()
        self.assertTrue(AccessLog.objects.filter(action="query_hr_signals").exists())


class SeuilsArbitresTest(APITestCase):
    setUp = SignauxTest.setUp
    _signaux = SignauxTest._signaux

    def _regler(self, user, **corps):
        self.client.force_authenticate(user)
        return self.client.put(URL_SEUILS, corps, format="json")

    def test_seule_la_drh_groupe_regle(self):
        r = self._regler(self.drh_kre, signal="presence_faible", surveillance=90, critique=80)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(SeuilRh.objects.exists())

    def test_ordre_des_paliers_impose(self):
        r = self._regler(self.drh, signal="presence_faible", surveillance=70, critique=80)
        self.assertEqual(r.status_code, 400)
        self.assertIn("INFÉRIEUR", r.json()["detail"])
        r = self._regler(self.drh, signal="retard_eleve", surveillance=20, critique=10)
        self.assertEqual(r.status_code, 400)
        r = self._regler(self.drh, signal="presence_faible", surveillance=120, critique=80)
        self.assertEqual(r.status_code, 400)
        r = self._regler(self.drh, signal="turnover_eleve", surveillance=1, critique=2)
        self.assertEqual(r.status_code, 400, "un signal sans source n'a pas de seuil à régler")

    def test_un_seuil_arbitre_change_le_signal_et_les_constats_du_jour(self):
        r = self._regler(self.drh, signal="presence_faible", surveillance=90, critique=82)
        self.assertEqual(r.status_code, 200, r.content)
        ligne = next(x for x in r.json()["seuils"] if x["signal"] == "presence_faible")
        self.assertFalse(ligne["par_defaut"])
        self.assertEqual(ligne["modifie_par"], "drh.s")

        s, _ = self._signaux()
        self.assertEqual(s["presence_faible"]["etat"], "critique")   # 80 < 82
        # Le même seuil juge le constat du jour — une seule source de vérité.
        self.assertEqual(R.seuils_publics()["presence_critique"], 82.0)
        constats = R.evaluer_presence_globale(80, 20, 0, "Shield", "jour")
        self.assertTrue(any(c["id"] == "hr.presence_basse" for c in constats))

        trace = AccessLog.objects.filter(action="update_hr_threshold").last()
        self.assertEqual(trace.payload["avant"]["critique"], 70.0)
        self.assertEqual(trace.payload["apres"]["critique"], 82.0)

    def test_reinitialiser(self):
        self._regler(self.drh, signal="presence_faible", surveillance=90, critique=82)
        r = self._regler(self.drh, signal="presence_faible", reinitialiser=True)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(SeuilRh.objects.exists())
        self.assertEqual(R.seuils_publics()["presence_critique"], R.PRESENCE_CRITIQUE)

    def test_le_score_garde_son_bareme(self):
        """Le barème du score est fixé par la direction : un réglage d'alerte ne le déplace pas."""
        from . import score_rh

        self._regler(self.drh, signal="presence_faible", surveillance=90, critique=82)
        self.assertEqual(score_rh.PRESENCE_PLANCHER, 70.0)

    def test_lecture_des_seuils_par_un_rh_de_filiale(self):
        self.client.force_authenticate(self.drh_kre)
        r = self.client.get(URL_SEUILS)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["modifiable"])

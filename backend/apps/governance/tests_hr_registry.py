"""Registre canonique RH et résolution par identifiant de métrique.

Ce que ces tests verrouillent :
  - une carte reçoit la valeur RÉELLE de sa source, avec sa provenance ;
  - N/D n'est jamais transformé en 0, et dit toujours pourquoi ;
  - le même identifiant de métrique donne le même nombre dans tous les modules ;
  - le périmètre serveur prévaut : un total Shield n'est servi qu'au Groupe, Odoo
    n'est servi à une filiale que sur ses sociétés DÉCLARÉES ;
  - le mart n'est plus une condition : aucune lecture, aucun 500 ;
  - une collecte Shield est partagée entre requêtes au lieu d'être refaite.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.integrations.models import DataConnector, DataSource, SourceStatus, SourceType
from apps.organizations.models import Subsidiary

from . import hr_registry
from .hr_registry import AUCUNE, LIAISONS, REGISTRE

User = get_user_model()


def _kpi(cle, valeur, statut="connected"):
    return {"key": cle, "value": valeur, "status": statut}


CHARGE_SHIELD = {
    "status": "connected", "source": "Kaydan Shield", "updated_at": "2026-10-14T08:00:00+00:00",
    "kpis": [
        _kpi("effectif_total", 812), _kpi("employes", 312), _kpi("ouvriers", 500),
        _kpi("presents", 640), _kpi("absents", 160), _kpi("retards", 32),
        _kpi("taux_presence", 80.0), _kpi("taux_absence_jour", 20.0),
        _kpi("taux_ponctualite", 95.0), _kpi("sites", 14),
    ],
    "by_kind": {"status": "connected", "employees": 240, "workers": 400, "total": 640},
    "by_site": {"status": "connected", "sites": [{"code": "S1", "nom": "Chantier A"}]},
    "insights": [{"portee": "groupe", "message": "Présence 80 %"}],
}


def _charge_odoo(societes=None):
    base = 120 if societes is None else 40
    return {
        "status": "connected", "source": "Odoo RH",
        "kpis": [_kpi("employes_actifs", base), _kpi("employes_inactifs", 9),
                 _kpi("departements", 11), _kpi("metiers", 30), _kpi("postes_ouverts", 6)],
        **({"societes_filtrees": list(societes)} if societes is not None else {}),
    }


class SocleRegistre(APITestCase):
    def setUp(self):
        cache.clear()
        self.kre = Subsidiary.objects.create(code="KRE", name="Kaydan Real Estate")
        self.drh_groupe = User.objects.create_user("drh.g", password=None, role="DRH", is_group_scope=True)
        self.drh_kre = User.objects.create_user("drh.kre", password=None, role="DRH", is_group_scope=False)
        self.drh_kre.subsidiaries.add(self.kre)
        self.lecteur = User.objects.create_user("lecteur.g", password=None, role="READER", is_group_scope=True)
        self.dir_ops = User.objects.create_user("ops.g", password=None, role="DIR_OPS", is_group_scope=True)
        self.dg = User.objects.create_user("dg.g", password=None, role="DG_GROUP", is_group_scope=True)

        p_shield = patch("apps.integrations.shield.fetch_hr_kpis", side_effect=lambda: dict(CHARGE_SHIELD))
        p_odoo = patch("apps.integrations.odoo.fetch_hr_kpis", side_effect=_charge_odoo)
        self.shield = p_shield.start()
        self.odoo = p_odoo.start()
        self.addCleanup(p_shield.stop)
        self.addCleanup(p_odoo.stop)

    def _module(self, utilisateur, cle):
        self.client.force_authenticate(utilisateur)
        return self.client.get(f"/api/v1/governance/module/{cle}/?year=2026&quarter=4")


class RegistreTest(SocleRegistre):
    def test_toute_metrique_sans_source_porte_un_motif(self):
        for m in REGISTRE.values():
            if m.source == AUCUNE:
                self.assertTrue(m.motif_absence, m.id)

    def test_toute_liaison_vise_une_metrique_existante(self):
        for module, cartes in LIAISONS.items():
            for libelle, metric_id in cartes.items():
                self.assertIn(metric_id, REGISTRE, f"{module} / {libelle}")

    def test_l_absenteisme_n_est_pas_le_taux_du_jour(self):
        """L'erreur la plus fréquente de l'inventaire : un taux journalier publié
        sous le libellé « absentéisme »."""
        self.assertNotEqual(LIAISONS["hr-attendance"]["Taux d'absentéisme"], "hr.taux_absence_jour")
        self.assertEqual(REGISTRE[LIAISONS["hr-attendance"]["Taux d'absentéisme"]].source, AUCUNE)

    def test_le_stock_d_archives_n_alimente_pas_le_turnover(self):
        self.assertEqual(REGISTRE["hr.turnover"].source, AUCUNE)
        self.assertNotIn("hr.employes_archives_odoo",
                         [mid for c in LIAISONS.values() for l, mid in c.items() if "urnover" in l])


class ModuleDataTest(SocleRegistre):
    def test_les_valeurs_reelles_arrivent_avec_leur_provenance(self):
        r = self._module(self.drh_groupe, "hr-executive")
        self.assertEqual(r.status_code, 200, r.content)
        v = r.json()["values"]
        # La valeur LIVE du jour est dans `aujourd_hui` ; `value` est celle de la
        # période filtrée (historique), vide tant qu'aucune journée n'est collectée.
        self.assertEqual(v["Effectif total"]["aujourd_hui"]["value"], 812)
        self.assertIsNone(v["Effectif total"]["value"])
        self.assertIn("Historique", v["Effectif total"]["reason"])
        self.assertEqual(v["Effectif total"]["metric_id"], "hr.effectif_total")
        self.assertEqual(v["Effectif total"]["source_label"], "Kaydan Shield")
        self.assertTrue(v["Effectif total"]["instant"])
        self.assertEqual(v["Employés actifs"]["aujourd_hui"]["value"], 120)
        self.assertEqual(v["Employés actifs"]["source_label"], "Odoo RH")

    def test_n_d_n_est_jamais_zero_et_dit_pourquoi(self):
        v = self._module(self.drh_groupe, "hr-executive").json()["values"]
        for libelle in ("Nouveaux employés", "Départs"):
            self.assertIsNone(v[libelle]["value"])
            self.assertTrue(v[libelle]["reason"])
        paie = self._module(self.drh_groupe, "hr-payroll").json()["values"]["Masse salariale"]
        self.assertIsNone(paie["value"])
        self.assertIn("hr.payslip", paie["reason"])

    def test_meme_identifiant_meme_nombre_dans_tous_les_modules(self):
        """Un DG voit tous les domaines : la comparaison traverse RH et Immobilier."""
        def live(cle, libelle):
            return self._module(self.dg, cle).json()["values"][libelle]["aujourd_hui"]["value"]

        self.assertEqual(live("hr-executive", "Effectif total"), live("hr-ai", "Effectifs"))
        self.assertEqual({live("hr-attendance", "Présents"), live("chantier-resources", "Présence temps réel"),
                          live("security", "Présence")}, {640})

    def test_le_module_rh_reste_ferme_au_lecteur(self):
        self.assertEqual(self._module(self.lecteur, "hr-executive").status_code, 403)

    def test_un_module_immobilier_ne_donne_pas_le_rh_sans_droit(self):
        """Le module Ressources Chantier est ouvert au directeur des opérations,
        mais ses cartes RH restent hors de ses droits."""
        r = self._module(self.dir_ops, "chantier-resources")
        self.assertEqual(r.status_code, 200)
        presence = r.json()["values"]["Présence temps réel"]
        self.assertIsNone(presence["value"])
        self.assertIn("droits", presence["reason"])

    def test_aucune_lecture_du_mart_donc_aucun_500(self):
        with patch("apps.governance.gateway.get_mart_gateway",
                   side_effect=AssertionError("le mart a été lu")):
            for cle in LIAISONS:
                with self.subTest(module=cle):
                    utilisateur = self.dir_ops if cle in ("chantier-resources", "security") else self.drh_groupe
                    self.assertEqual(self._module(utilisateur, cle).status_code, 200)


class PerimetreTest(SocleRegistre):
    def test_une_filiale_ne_recoit_aucun_total_shield(self):
        v = self._module(self.drh_kre, "hr-attendance").json()["values"]
        self.assertIsNone(v["Présents"]["value"])
        self.assertIn("Hors périmètre", v["Présents"]["reason"])
        self.assertNotIn("640", json.dumps(v))

    def test_une_filiale_sans_societe_declaree_ne_recoit_rien_d_odoo(self):
        v = self._module(self.drh_kre, "hr-executive").json()["values"]["Employés actifs"]
        self.assertIsNone(v["value"])
        self.assertIn("aucune société Odoo", v["reason"])
        self.odoo.assert_not_called()

    def test_une_filiale_avec_societe_declaree_recoit_odoo_filtre(self):
        odoo_src = DataSource.objects.create(name="Odoo RH", slug="odoo-hr",
                                             source_type=SourceType.ODOO_HR, target_module="rh",
                                             status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=odoo_src, base_url="https://rh.kaydan.tech",
                                     config={"company_mapping": {"3": "KRE", "4": "KSH"}})
        v = self._module(self.drh_kre, "hr-executive").json()["values"]["Employés actifs"]
        self.assertEqual(v["aujourd_hui"]["value"], 40)
        self.odoo.assert_called_with([3])

    def test_les_vues_shield_ne_laissent_plus_passer_les_totaux(self):
        self.client.force_authenticate(self.drh_kre)
        with patch("apps.integrations.views.fetch_hr_kpis", side_effect=lambda: dict(CHARGE_SHIELD)):
            charge = self.client.get("/api/v1/integrations/shield/hr-kpi/").json()
        self.assertTrue(all(k["value"] is None for k in charge["kpis"]))
        self.assertEqual(charge["insights"], [])
        self.assertIsNone(charge["by_kind"]["workers"])
        texte = json.dumps(charge, ensure_ascii=False)
        for chiffre in ("812", "640", "Chantier A"):
            self.assertNotIn(chiffre, texte)

    def test_la_serie_de_presence_est_retenue_hors_groupe(self):
        self.client.force_authenticate(self.drh_kre)
        with patch("apps.integrations.views.fetch_attendance_series",
                   side_effect=AssertionError("série Groupe collectée pour une filiale")):
            r = self.client.get("/api/v1/integrations/shield/attendance-series/?days=7")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["points"], [])

    def test_la_vue_groupe_ne_sert_plus_l_effectif_sans_droit_rh(self):
        faux = {"status": "connected", "kpis": [_kpi("workforce", 812), _kpi("sites_actifs", 14)]}
        self.client.force_authenticate(self.lecteur)
        with patch("apps.integrations.views.fetch_overview_kpis", return_value=faux):
            kpis = {k["key"]: k for k in self.client.get("/api/v1/integrations/shield/overview/").json()["kpis"]}
        self.assertIsNone(kpis["workforce"]["value"])
        self.assertEqual(kpis["sites_actifs"]["value"], 14)

    def test_la_vue_odoo_applique_le_perimetre(self):
        self.client.force_authenticate(self.drh_kre)
        r = self.client.get("/api/v1/integrations/odoo/hr-kpi/").json()
        self.assertEqual(r["status"], "disconnected")
        self.assertIn("aucune société Odoo", r["restriction"])
        self.odoo.assert_not_called()


class CachePartageTest(SocleRegistre):
    def test_une_collecte_shield_sert_plusieurs_requetes(self):
        DataSource.objects.create(name="Kaydan Shield", slug="kaydan-shield",
                                  source_type=SourceType.KAYDAN_SHIELD, target_module="rh")
        for cle in ("hr-executive", "hr-attendance", "hr-ai"):
            self._module(self.drh_groupe, cle)
        self.assertEqual(self.shield.call_count, 1)

    def test_la_cle_de_cache_porte_le_perimetre_odoo(self):
        """La charge d'une filiale ne doit jamais être resservie au Groupe."""
        odoo_src = DataSource.objects.create(name="Odoo RH", slug="odoo-hr",
                                             source_type=SourceType.ODOO_HR, target_module="rh",
                                             status=SourceStatus.CONNECTED)
        DataConnector.objects.create(source=odoo_src, base_url="https://rh.kaydan.tech",
                                     config={"company_mapping": {"3": "KRE"}})
        filiale = self._module(self.drh_kre, "hr-executive").json()["values"]["Employés actifs"]["aujourd_hui"]["value"]
        groupe = self._module(self.drh_groupe, "hr-executive").json()["values"]["Employés actifs"]["aujourd_hui"]["value"]
        self.assertEqual((filiale, groupe), (40, 120))


class ConnecteursAlignesTest(SocleRegistre):
    """Les charges source portent l'identifiant canonique, et les seuils qui font foi."""

    def test_la_table_d_identifiants_est_coherente(self):
        for m in REGISTRE.values():
            if m.cle_source and not m.cle_source.startswith("by_kind."):
                self.assertEqual(hr_registry.identifiant(m.source, m.cle_source), m.id)
        self.assertIsNone(hr_registry.identifiant("shield", "cle_inconnue"))

    def test_les_seuils_publies_sont_ceux_des_regles(self):
        from apps.integrations import shield_rules as R

        seuils = R.seuils_publics()
        self.assertEqual(seuils["presence_critique"], R.PRESENCE_CRITIQUE)
        self.assertEqual(seuils["presence_surveillance"], R.PRESENCE_SURVEILLANCE)
        self.assertLess(seuils["presence_critique"], seuils["presence_surveillance"])

    def test_le_lien_des_alertes_critiques_vise_une_route_existante(self):
        from apps.integrations.shield import security_insights

        constats = security_insights(
            [{"key": "alertes_critiques", "value": 3, "status": "connected"}], "Kaydan Shield")
        self.assertEqual(constats[0]["action"]["to"], "/dashboard/risques-conformite/alertes")

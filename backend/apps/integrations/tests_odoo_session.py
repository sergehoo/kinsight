"""Liaison permanente Odoo : compte technique, uid partagé, réauthentification seule.

Un faux serveur JSON-RPC rejoue ce qu'Odoo 18 répond vraiment : `authenticate`
rend `False` (et non une erreur) pour un mauvais login, une mauvaise clé ou un
compte désactivé ; une base inexistante remonte en `OperationalError` ; un uid
refusé en `odoo.exceptions.AccessDenied` ; un modèle interdit en `AccessError`.
Chaque erreur porte un traceback avec un chemin serveur et l'hôte de la base —
qui ne doit JAMAIS ressortir.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AccessLog
from apps.organizations.models import Subsidiary

from . import odoo_session
from .models import ConnectorCredential, CredentialKind, DataConnector, DataSource, SourceType
from .odoo_client import ClientOdoo, OdooError

URL = "https://rh.kaydan.tech"
BASE = "kaydan_prod"
LOGIN = "integration@kaydan.tech"
CLE = "cle-api-tres-reconnaissable-9f3a"
TRACEBACK = 'Traceback (most recent call last):\n  File "/opt/odoo/odoo/service/model.py"\n  host=postgres port=5432'


class _Flux:
    def __init__(self, charge):
        self._corps = json.dumps(charge).encode()

    def read(self):
        return self._corps

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FauxOdoo:
    """Serveur JSON-RPC minimal, fidèle aux réponses d'Odoo 18."""

    def __init__(self):
        self.comptes = {(BASE, LOGIN, CLE): 7}
        self.bases = {BASE}
        self.uid_acceptes = {7}
        self.appels: list[tuple[str, str]] = []
        self.panne_reseau = False
        self.droits_rh = True
        self.delai_auth = 0.0
        self._verrou = threading.Lock()

    def compte(self, service, methode):
        return sum(1 for s, m in self.appels if (s, m) == (service, methode))

    @staticmethod
    def _ok(resultat):
        return _Flux({"jsonrpc": "2.0", "id": 1, "result": resultat})

    @staticmethod
    def _erreur(nom, message):
        return _Flux({"jsonrpc": "2.0", "id": 1, "error": {
            "code": 200, "message": "Odoo Server Error",
            "data": {"name": nom, "message": message, "debug": TRACEBACK}}})

    def __call__(self, requete, timeout=None):
        if self.panne_reseau:
            raise urllib.error.URLError(OSError("Name or service not known"))
        corps = json.loads(requete.data)
        params = corps["params"]
        service, methode, args = params["service"], params["method"], params["args"]
        with self._verrou:
            self.appels.append((service, methode))

        if (service, methode) == ("common", "version"):
            return self._ok({"server_version": "18.0", "protocol_version": 1})
        if (service, methode) == ("common", "authenticate"):
            if self.delai_auth:
                time.sleep(self.delai_auth)
            base, login, cle, _env = args
            if base not in self.bases:
                return self._erreur("psycopg2.OperationalError",
                                    f'connection failed: FATAL:  database "{base}" does not exist')
            return self._ok(self.comptes.get((base, login, cle), False))
        if (service, methode) == ("object", "execute_kw"):
            base, uid, cle, modele, meth, _a, _kw = args
            if uid not in self.uid_acceptes or self.comptes.get((base, LOGIN, cle)) != uid:
                return self._erreur("odoo.exceptions.AccessDenied", "Access Denied")
            if modele == "hr.employee" and not self.droits_rh:
                return self._erreur("odoo.exceptions.AccessError",
                                    "You are not allowed to access 'Employee' (hr.employee) records.")
            if meth == "search_count":
                return self._ok(42)
            if meth == "search_read" and modele == "res.company":
                return self._ok([{"id": 1, "name": "Kaydan Real Estate"},
                                 {"id": 2, "name": "Kaydan Shield SARL"}])
            return self._ok([])
        return self._erreur("builtins.KeyError", "service inconnu")


class SocleOdoo(TestCase):
    def setUp(self):
        cache.clear()
        odoo_session._vider_les_sessions()
        self.faux = FauxOdoo()
        correctif = patch("apps.integrations.odoo_client.urllib.request.urlopen", side_effect=self.faux)
        correctif.start()
        self.addCleanup(correctif.stop)
        self.source = DataSource.objects.create(
            name="Odoo RH", slug="odoo-hr", source_type=SourceType.ODOO_HR, target_module="rh")
        self.connecteur = DataConnector.objects.create(source=self.source, base_url=URL)

    def _enregistrer(self, **surcharges):
        champs = {"url": URL, "base": BASE, "login": LOGIN, "cle": CLE, **surcharges}
        return odoo_session.enregistrer_compte_odoo(self.connecteur, **champs)

    def _rendu_complet(self) -> str:
        """Tout ce qui pourrait fuir : état, config, sérialiseur, journaux d'audit."""
        from .serializers import DataConnectorSerializer

        self.connecteur.refresh_from_db()
        morceaux = [
            json.dumps(odoo_session.etat_odoo(self.connecteur), ensure_ascii=False, default=str),
            json.dumps(self.connecteur.config, ensure_ascii=False, default=str),
            json.dumps(DataConnectorSerializer(self.connecteur).data, ensure_ascii=False, default=str),
            json.dumps([a.payload for a in AccessLog.objects.all()], ensure_ascii=False, default=str),
        ]
        return "\n".join(morceaux)


class ContratJsonRpcTest(SocleOdoo):
    """Le transport : version, authenticate, erreurs nommées."""

    def test_common_version_sans_authentification(self):
        client = ClientOdoo(URL, BASE, LOGIN, CLE)
        self.assertEqual(client.version()["server_version"], "18.0")
        self.assertEqual(self.faux.compte("common", "authenticate"), 0)

    def test_authentification_reussie_rend_l_uid(self):
        self.assertEqual(ClientOdoo(URL, BASE, LOGIN, CLE).authentifier(), 7)

    def test_mauvais_login_mauvaise_cle_sont_des_refus(self):
        for login, cle in ((("autre@kaydan.tech"), CLE), (LOGIN, "mauvaise-cle")):
            with self.subTest(login=login, cle=cle):
                with self.assertRaises(OdooError) as ctx:
                    ClientOdoo(URL, BASE, login, cle).authentifier()
                self.assertEqual(ctx.exception.kind, "auth")

    def test_mauvaise_base_est_distinguee_d_un_refus(self):
        """Un compte juste sur une base fausse ne se corrige pas en changeant de clé."""
        with self.assertRaises(OdooError) as ctx:
            ClientOdoo(URL, "base_inexistante", LOGIN, CLE).authentifier()
        self.assertEqual(ctx.exception.kind, "base")

    def test_le_traceback_d_odoo_ne_remonte_jamais(self):
        with self.assertRaises(OdooError) as ctx:
            ClientOdoo(URL, "base_inexistante", LOGIN, CLE).authentifier()
        self.assertNotIn("/opt/odoo", str(ctx.exception))
        self.assertNotIn("postgres", str(ctx.exception))

    def test_panne_reseau_n_est_pas_un_refus(self):
        self.faux.panne_reseau = True
        with self.assertRaises(OdooError) as ctx:
            ClientOdoo(URL, BASE, LOGIN, CLE, max_tentatives=1).authentifier()
        self.assertEqual(ctx.exception.kind, "reseau")

    def test_ecriture_refusee_par_construction(self):
        with self.assertRaises(OdooError) as ctx:
            ClientOdoo(URL, BASE, LOGIN, CLE).executer("hr.employee", "write", [[1], {"name": "x"}])
        self.assertEqual(ctx.exception.kind, "config")
        self.assertEqual(self.faux.compte("object", "execute_kw"), 0)


class SessionPartageeTest(SocleOdoo):
    """Cache d'uid, réauthentification seule, rejeu unique, single-flight."""

    def setUp(self):
        super().setUp()
        ok, cause, message = self._enregistrer()
        self.assertTrue(ok, message)
        self.faux.appels.clear()

    def test_l_uid_est_reutilise_d_une_requete_a_l_autre(self):
        """Le défaut d'origine : un client par requête, donc une authentification
        par requête. Deux clients successifs ne doivent s'authentifier qu'au plus
        une fois — ici zéro, l'enregistrement ayant amorcé la session."""
        odoo_session.client_pour(self.connecteur).compter("hr.employee")
        odoo_session.client_pour(self.connecteur).compter("hr.employee")
        self.assertEqual(self.faux.compte("common", "authenticate"), 0)
        self.assertEqual(self.faux.compte("object", "execute_kw"), 2)

    def test_uid_refuse_reauthentification_puis_un_seul_rejeu(self):
        """L'uid en cache n'est plus accepté (base restaurée, compte recréé) : on
        se réauthentifie avec le compte de service et l'appel aboutit — sans
        intervention humaine."""
        self.faux.uid_acceptes = {9}
        self.faux.comptes[(BASE, LOGIN, CLE)] = 9
        self.assertEqual(odoo_session.client_pour(self.connecteur).compter("hr.employee"), 42)
        self.assertEqual(self.faux.compte("common", "authenticate"), 1)
        self.assertEqual(self.faux.compte("object", "execute_kw"), 2)

    def test_pas_de_boucle_si_le_refus_persiste(self):
        """Clé révoquée : le rejeu échoue aussi, et on s'arrête là."""
        self.faux.comptes[(BASE, LOGIN, CLE)] = False
        with self.assertRaises(OdooError) as ctx:
            odoo_session.client_pour(self.connecteur).compter("hr.employee")
        self.assertEqual(ctx.exception.kind, "auth")
        self.assertEqual(self.faux.compte("common", "authenticate"), 1)
        self.assertEqual(self.faux.compte("object", "execute_kw"), 1)

    def test_une_panne_reseau_ne_declenche_pas_de_reauthentification(self):
        self.faux.panne_reseau = True
        with self.assertRaises(OdooError) as ctx:
            odoo_session.client_pour(self.connecteur, max_tentatives=1).compter("hr.employee")
        self.assertEqual(ctx.exception.kind, "reseau")
        self.assertEqual(self.faux.compte("common", "authenticate"), 0)

    def test_single_flight_une_seule_authentification_pour_dix_requetes(self):
        cache.clear()
        odoo_session._vider_les_sessions()
        self.faux.delai_auth = 0.2  # élargit la fenêtre de course
        clients = [odoo_session.client_pour(self.connecteur) for _ in range(10)]
        resultats, erreurs = [], []

        def lire(client):
            try:
                resultats.append(client.compter("hr.employee"))
            except Exception as exc:  # noqa: BLE001
                erreurs.append(exc)

        fils = [threading.Thread(target=lire, args=(c,)) for c in clients]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(erreurs, [])
        self.assertEqual(resultats, [42] * 10)
        self.assertEqual(self.faux.compte("common", "authenticate"), 1)

    def test_apres_un_refus_on_ne_relance_pas_odoo_pendant_le_refroidissement(self):
        """Chaque carte d'un écran rejouerait sinon le refus, jusqu'à faire
        verrouiller le compte technique côté Odoo."""
        cache.clear()
        odoo_session._vider_les_sessions()
        self.faux.comptes[(BASE, LOGIN, CLE)] = False
        for _ in range(5):
            with self.assertRaises(OdooError):
                odoo_session.client_pour(self.connecteur).compter("hr.employee")
        self.assertEqual(self.faux.compte("common", "authenticate"), 1)

    def test_changer_de_cle_change_de_session(self):
        """L'empreinte inclut la clé : une rotation ouvre une session neuve, sans
        hériter d'un refroidissement ni d'un uid de l'ancienne."""
        a = odoo_session.session_pour(URL, BASE, LOGIN, CLE)
        b = odoo_session.session_pour(URL, BASE, LOGIN, "cle-neuve")
        self.assertIsNot(a, b)


class EnregistrementVerifieTest(SocleOdoo):
    """Rien n'est écrit avant les trois preuves : version, authentification, lecture RH."""

    def test_succes_ecrit_chiffre_et_connecte(self):
        ok, cause, message = self._enregistrer()
        self.assertTrue(ok, message)
        kinds = set(ConnectorCredential.objects.filter(connector=self.connecteur)
                    .values_list("kind", flat=True))
        self.assertEqual(kinds, {CredentialKind.DATABASE, CredentialKind.LOGIN, CredentialKind.API_KEY})
        cred = ConnectorCredential.objects.get(connector=self.connecteur, kind=CredentialKind.API_KEY)
        self.assertNotIn(CLE, cred.secret_ciphertext)
        self.source.refresh_from_db()
        self.assertEqual(self.source.status, "connected")
        etat = odoo_session.etat_odoo(self.connecteur)
        self.assertEqual(etat["etat"], "connected")
        self.assertEqual(etat["version"], "18.0")
        self.assertTrue(etat["reconnexion_automatique"])
        self.assertEqual(etat["compte_de_service"], "int***@kaydan.tech")
        self.assertEqual(etat["base"], BASE)

    def test_les_valeurs_en_clair_d_une_config_anterieure_sont_retirees(self):
        self.connecteur.config = {"database": BASE, "login": LOGIN}
        self.connecteur.save()
        self._enregistrer()
        self.connecteur.refresh_from_db()
        self.assertNotIn("login", self.connecteur.config)
        self.assertNotIn("database", self.connecteur.config)

    def test_aucun_echec_n_ecrit_quoi_que_ce_soit(self):
        cas = {
            "auth": {"cle": "mauvaise-cle"},
            "base": {"base": "base_inexistante"},
            "config": {"login": ""},
        }
        for attendu, surcharge in cas.items():
            with self.subTest(cause=attendu):
                ok, cause, _ = self._enregistrer(**surcharge)
                self.assertFalse(ok)
                self.assertEqual(cause, attendu)
                self.assertFalse(ConnectorCredential.objects.filter(connector=self.connecteur).exists())

    def test_un_compte_qui_ne_lit_pas_la_rh_est_refuse(self):
        self.faux.droits_rh = False
        ok, cause, message = self._enregistrer()
        self.assertFalse(ok)
        self.assertEqual(cause, "droits")
        self.assertIn("hr.employee", message)
        self.assertFalse(ConnectorCredential.objects.filter(connector=self.connecteur).exists())

    def test_un_refus_ne_remplace_pas_un_compte_qui_fonctionnait(self):
        self._enregistrer()
        ok, _, _ = self._enregistrer(cle="faute-de-frappe")
        self.assertFalse(ok)
        self.assertEqual(odoo_session.cle_api(self.connecteur), CLE)

    def test_odoo_injoignable_n_ecrit_rien_et_n_est_pas_un_refus(self):
        self.faux.panne_reseau = True
        ok, cause, _ = self._enregistrer()
        self.assertFalse(ok)
        self.assertEqual(cause, "reseau")
        self.assertFalse(ConnectorCredential.objects.filter(connector=self.connecteur).exists())

    def test_trop_d_essais_refuses_bloque_temporairement(self):
        for _ in range(odoo_session.ESSAIS_ENREGISTREMENT):
            self._enregistrer(cle="mauvaise")
        ok, cause, _ = self._enregistrer()
        self.assertFalse(ok)
        self.assertEqual(cause, "trop_d_essais")


class EtatsEtVerificationTest(SocleOdoo):
    def test_identifiants_absents_auth_required(self):
        self.assertEqual(odoo_session.etat_odoo(self.connecteur)["etat"], "auth_required")

    def test_compte_desactive_apres_coup_auth_required(self):
        self._enregistrer()
        self.faux.comptes[(BASE, LOGIN, CLE)] = False  # désactivé dans Odoo
        ok, cause, _ = odoo_session.verifier_odoo(self.connecteur)
        self.assertFalse(ok)
        self.assertEqual(cause, "auth")
        etat = odoo_session.etat_odoo(self.connecteur)
        self.assertEqual(etat["etat"], "auth_required")
        self.assertFalse(etat["reconnexion_automatique"])

    def test_panne_reseau_rend_error_et_pas_auth_required(self):
        self._enregistrer()
        self.faux.panne_reseau = True
        ok, cause, _ = odoo_session.verifier_odoo(self.connecteur)
        self.assertFalse(ok)
        etat = odoo_session.etat_odoo(self.connecteur)
        self.assertEqual(etat["etat"], "error")
        # Le compte n'est pas condamné par une coupure réseau.
        self.assertTrue(etat["reconnexion_automatique"])

    def test_une_verification_reussie_leve_le_verdict(self):
        self._enregistrer()
        self.faux.comptes[(BASE, LOGIN, CLE)] = False
        odoo_session.verifier_odoo(self.connecteur)
        self.faux.comptes[(BASE, LOGIN, CLE)] = 7  # compte réactivé côté Odoo
        ok, _, _ = odoo_session.verifier_odoo(self.connecteur)
        self.assertTrue(ok)
        self.assertEqual(odoo_session.etat_odoo(self.connecteur)["etat"], "connected")

    def test_verification_ancienne_rend_stale(self):
        self._enregistrer()
        config = dict(self.connecteur.config)
        config["odoo_auth"]["derniere_verification"] = (timezone.now() - timedelta(days=2)).isoformat()
        self.connecteur.config = config
        self.connecteur.save()
        self.assertEqual(odoo_session.etat_odoo(self.connecteur)["etat"], "stale")

    def test_le_test_de_connexion_authentifie_vraiment(self):
        """Avant : une sonde RÉSEAU sur l'URL suffisait à afficher « connectée »,
        sans authentification ni base vérifiée."""
        from .services import run_test

        self._enregistrer()
        self.faux.appels.clear()
        ok, _ = run_test(self.source)
        self.assertTrue(ok)
        self.assertEqual(self.faux.compte("common", "authenticate"), 1)

        self.faux.comptes[(BASE, LOGIN, CLE)] = False
        ok, _ = run_test(self.source)
        self.assertFalse(ok)
        self.source.refresh_from_db()
        self.assertEqual(self.source.status, "error")


class AucunSecretNeFuitTest(SocleOdoo):
    def test_ni_cle_ni_login_complet_nulle_part(self):
        self._enregistrer()
        self._enregistrer(cle="mauvaise-cle")         # un échec tracé
        odoo_session.verifier_odoo(self.connecteur)   # une vérification tracée
        rendu = self._rendu_complet()
        self.assertNotIn(CLE, rendu)
        self.assertNotIn("mauvaise-cle", rendu)
        self.assertNotIn(LOGIN, rendu)
        self.assertNotIn("/opt/odoo", rendu)

    def test_une_config_ancienne_ne_renvoie_pas_le_login_en_clair(self):
        from .serializers import DataConnectorSerializer

        self.connecteur.config = {"database": BASE, "login": LOGIN}
        self.connecteur.save()
        rendu = json.dumps(DataConnectorSerializer(self.connecteur).data, default=str)
        self.assertNotIn(LOGIN, rendu)

    def test_on_ne_peut_pas_reecrire_le_login_en_clair_dans_la_config(self):
        from .serializers import DataConnectorSerializer

        s = DataConnectorSerializer(self.connecteur, data={"config": {"login": LOGIN}}, partial=True)
        self.assertFalse(s.is_valid())


class VueCompteOdooTest(SocleOdoo):
    def setUp(self):
        super().setUp()
        self.client_api = APIClient()
        admin = get_user_model().objects.create_superuser("admin.odoo", "a@b.c", "mdp-admin-x")
        self.client_api.force_authenticate(admin)

    def _poster(self, **surcharges):
        corps = {"url": URL, "database": BASE, "login": LOGIN, "secret": CLE, **surcharges}
        return self.client_api.post(f"/api/v1/integrations/sources/{self.source.id}/odoo-account/",
                                    corps, format="json")

    def test_codes_http_qui_disent_la_cause(self):
        self.assertEqual(self._poster(secret="mauvaise").status_code, 401)
        self.assertEqual(self._poster(database="inexistante").status_code, 409)
        self.faux.panne_reseau = True
        self.assertEqual(self._poster().status_code, 503)
        self.faux.panne_reseau = False
        reponse = self._poster()
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["odoo_auth"]["etat"], "connected")

    def test_la_reponse_et_l_audit_ne_portent_pas_le_secret(self):
        reponse = self._poster()
        self.assertNotIn(CLE, reponse.content.decode())
        audit = AccessLog.objects.filter(action="integration.odoo.compte_service").last()
        self.assertEqual(audit.payload.get("compte"), "int***@kaydan.tech")
        self.assertNotIn(CLE, json.dumps(audit.payload))

    def test_reserve_aux_sources_odoo(self):
        shield = DataSource.objects.create(name="S", slug="kaydan-shield",
                                           source_type=SourceType.KAYDAN_SHIELD, target_module="rh")
        DataConnector.objects.create(source=shield, base_url="https://x")
        reponse = self.client_api.post(f"/api/v1/integrations/sources/{shield.id}/odoo-account/",
                                       {}, format="json")
        self.assertEqual(reponse.status_code, 400)


class CorrespondanceSocietesTest(SocleOdoo):
    def setUp(self):
        super().setUp()
        for code in ("KRE", "KSH", "MYK"):
            Subsidiary.objects.get_or_create(code=code, defaults={"name": code})
        self.client_api = APIClient()
        admin = get_user_model().objects.create_superuser("admin.map", "m@b.c", "mdp-admin-y")
        self.client_api.force_authenticate(admin)
        self._enregistrer()
        self.source.refresh_from_db()

    def test_les_societes_sont_lues_et_rien_n_est_devine(self):
        donnees = self.client_api.get("/api/v1/integrations/odoo/companies/").json()
        self.assertEqual(donnees["status"], "connected")
        self.assertEqual([c["name"] for c in donnees["companies"]],
                         ["Kaydan Real Estate", "Kaydan Shield SARL"])
        # « Kaydan Real Estate » ressemble à KRE — mais personne ne l'a affirmé.
        self.assertEqual({c["subsidiary"] for c in donnees["companies"]}, {""})

    def test_une_correspondance_declaree_est_enregistree(self):
        reponse = self.client_api.put("/api/v1/integrations/odoo/companies/",
                                      {"mapping": {"1": "KRE", "2": ""}}, format="json")
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.json()["mapping"], {"1": "KRE"})
        donnees = self.client_api.get("/api/v1/integrations/odoo/companies/").json()
        self.assertEqual(donnees["companies"][0]["subsidiary"], "KRE")

    def test_un_code_filiale_inconnu_est_refuse(self):
        reponse = self.client_api.put("/api/v1/integrations/odoo/companies/",
                                      {"mapping": {"1": "XXX"}}, format="json")
        self.assertEqual(reponse.status_code, 400)

    def test_reserve_aux_administrateurs_d_integration(self):
        lecteur = get_user_model().objects.create_user("lecteur.map", password="x")
        client = APIClient()
        client.force_authenticate(lecteur)
        self.assertIn(client.get("/api/v1/integrations/odoo/companies/").status_code, (403, 401))

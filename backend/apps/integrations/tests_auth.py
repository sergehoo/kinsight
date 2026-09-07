"""La session Shield se prolonge-t-elle seule, sans jamais boucler ni fuir ?

Contrat vérifié sur le schéma OpenAPI live de Shield :
    POST /api/v1/auth/token/refresh/   {"refresh": …} → {"access": …, "refresh": …}
Les deux champs sont requis en réponse : la rotation est active, et ne pas persister
le nouveau `refresh` ramènerait l'authentification manuelle au premier cycle.
"""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AccessLog

from . import shield, shield_auth
from .models import ConnectorCredential, CredentialKind, DataConnector, DataSource, SourceType
from .shield_client import ShieldClient, ShieldError

BASE_SHIELD = "https://api.kaydanshield.com/api/v1"


def jwt_factice(*, dans: timedelta | None = None, charge: dict | None = None) -> str:
    """Un JWT de forme réelle, dont seul le claim `exp` nous intéresse.

    Non signé : le module ne vérifie pas la signature, et n'a pas à le faire — il
    lit `exp` pour choisir QUAND renouveler, Shield restant seul juge de la validité.
    """
    claims = dict(charge or {})
    if dans is not None:
        claims["exp"] = (timezone.now() + dans).timestamp()

    def segment(donnees: dict) -> str:
        brut = json.dumps(donnees).encode()
        return base64.urlsafe_b64encode(brut).decode().rstrip("=")

    return f"{segment({'alg': 'HS256', 'typ': 'JWT'})}.{segment(claims)}.signature-factice"


class SocleShield(TestCase):
    def setUp(self):
        self.source = DataSource.objects.create(
            name="Kaydan Shield", slug="kaydan-shield",
            source_type=SourceType.KAYDAN_SHIELD, target_module="rh")
        self.connecteur = DataConnector.objects.create(
            source=self.source, base_url=BASE_SHIELD, auth_method="bearer")

    def _deposer(self, kind: str, valeur: str) -> ConnectorCredential:
        cred, _ = ConnectorCredential.objects.get_or_create(connector=self.connecteur, kind=kind)
        cred.set_secret(valeur)
        cred.save()
        return cred

    def _recharger(self):
        self.connecteur.refresh_from_db()
        self.source.refresh_from_db()


class EcheanceDuJetonTest(SocleShield):
    """Savoir quand renouveler, sans que l'API ne le dise."""

    def test_lecheance_est_lue_dans_le_claim_exp(self):
        jeton = jwt_factice(dans=timedelta(hours=1))
        echeance = shield_auth.echeance_du_jeton(jeton)
        self.assertIsNotNone(echeance)
        self.assertAlmostEqual((echeance - timezone.now()).total_seconds(), 3600, delta=5)

    def test_un_jeton_opaque_rend_une_echeance_inconnue(self):
        """Plutôt que d'inventer une durée de vie : inconnue, et c'est Shield qui
        tranchera par un 401."""
        for opaque in ("", "pas-un-jwt", "a.b", "a.b.c.d", "entete.charge-illisible.sig"):
            self.assertIsNone(shield_auth.echeance_du_jeton(opaque), opaque)

    def test_un_jwt_sans_exp_rend_une_echeance_inconnue(self):
        self.assertIsNone(shield_auth.echeance_du_jeton(jwt_factice(charge={"sub": "1"})))


class JetonUtilisableTest(SocleShield):
    def test_un_access_valide_est_employe_tel_quel(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(hours=1)))
        self.assertTrue(shield_auth.jeton_utilisable(self.connecteur))

    def test_un_access_expire_nest_pas_employe(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(minutes=-5)))
        self.assertEqual(shield_auth.jeton_utilisable(self.connecteur), "")

    def test_un_access_proche_de_lexpiration_est_deja_ecarte(self):
        """Renouveler AVANT l'échéance évite un 401 pendant le vol d'une requête,
        donc un aller-retour de plus sur le chemin critique."""
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(seconds=30)))
        self.assertEqual(shield_auth.jeton_utilisable(self.connecteur), "")

    def test_sans_access_il_ny_a_rien_a_employer(self):
        self.assertEqual(shield_auth.jeton_utilisable(self.connecteur), "")


class RenouvellementTest(SocleShield):
    """Le cœur : la session se prolonge, et la rotation est respectée."""

    def _reponse(self, acces: str, refresh: str):
        class _Flux:
            def read(_self):
                return json.dumps({"access": acces, "refresh": refresh}).encode()

            def __enter__(_self):
                return _self

            def __exit__(_self, *a):
                return False

        return _Flux()

    def test_un_renouvellement_reussi_persiste_les_DEUX_jetons(self):
        """La réponse documentée porte un NOUVEAU refresh : le jeter condamnerait le
        cycle suivant."""
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(minutes=-1)))
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-initial")
        neuf = jwt_factice(dans=timedelta(hours=2))

        with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                   return_value=self._reponse(neuf, "refresh-tourne")) as appel:
            ok, message = shield_auth.renouveler(self.connecteur)

        self.assertTrue(ok, message)
        self.assertEqual(appel.call_count, 1)
        self._recharger()
        self.assertEqual(
            self.connecteur.credentials.get(kind=CredentialKind.API_TOKEN).secret, neuf)
        self.assertEqual(
            self.connecteur.credentials.get(kind=CredentialKind.OAUTH_REFRESH).secret,
            "refresh-tourne", "le refresh tourné n'a pas été persisté")

    def test_lurl_appelee_est_celle_documentee(self):
        """Aucun chemin inventé : c'est celui du schéma live."""
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                   return_value=self._reponse(jwt_factice(dans=timedelta(hours=1)), "r2")) as appel:
            shield_auth.renouveler(self.connecteur, force=True)
        requete = appel.call_args[0][0]
        self.assertEqual(requete.full_url,
                         "https://api.kaydanshield.com/api/v1/auth/token/refresh/")
        self.assertEqual(requete.method, "POST")
        self.assertEqual(json.loads(requete.data.decode()), {"refresh": "r"})

    def test_une_base_sans_prefixe_donne_la_meme_url(self):
        self.connecteur.base_url = "https://api.kaydanshield.com"
        self.connecteur.save(update_fields=["base_url"])
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                   return_value=self._reponse(jwt_factice(dans=timedelta(hours=1)), "r2")) as appel:
            shield_auth.renouveler(self.connecteur, force=True)
        self.assertEqual(appel.call_args[0][0].full_url,
                         "https://api.kaydanshield.com/api/v1/auth/token/refresh/")

    def test_un_refresh_refuse_demande_une_reauthentification(self):
        """401/403 sur le renouvellement : le refresh est expiré ou révoqué. Aucune
        reprise ne le ressuscitera."""
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-mort")
        for code in (401, 403):
            with self.subTest(code=code):
                erreur = urllib.error.HTTPError("u", code, "refus", {}, None)
                with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                           side_effect=erreur):
                    ok, message = shield_auth.renouveler(self.connecteur, force=True)
                self.assertFalse(ok)
                self.assertIn("réauthentification", message.lower())

    def test_un_quota_de_renouvellement_est_dit_comme_tel(self):
        """Shield documente que le renouvellement a sa propre cadence : insister
        aggrave la limite."""
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        erreur = urllib.error.HTTPError("u", 429, "trop", {}, None)
        with patch("apps.integrations.shield_auth.urllib.request.urlopen", side_effect=erreur):
            ok, message = shield_auth.renouveler(self.connecteur, force=True)
        self.assertFalse(ok)
        self.assertIn("débit", message.lower())

    def test_sans_refresh_le_message_dit_quoi_faire(self):
        ok, message = shield_auth.renouveler(self.connecteur, force=True)
        self.assertFalse(ok)
        self.assertIn("access + refresh", message)

    def test_une_reponse_sans_access_est_refusee(self):
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                   return_value=self._reponse("", "r2")):
            ok, message = shield_auth.renouveler(self.connecteur, force=True)
        self.assertFalse(ok)
        self.assertIn("sans jeton d'accès", message)


class ConcurrenceTest(SocleShield):
    """Un seul renouvellement, même si dix appels le réclament ensemble.

    Shield le documente noir sur blanc : « deux rechargements suffisaient à épuiser
    le quota d'une minute ». Sans ce verrou, plusieurs threads d'un même worker
    grilleraient ce quota, et Shield refuserait jusqu'à la connexion.
    """

    def test_deux_appels_simultanes_ne_produisent_quun_renouvellement(self):
        """La base est neutralisée ici, à dessein.

        SQLite verrouille la table entre threads à l'intérieur de la transaction de
        test : le premier thread mourrait sur « database table is locked » avant
        d'atteindre l'appel réseau, et l'échec masquerait le mécanisme même qu'on
        veut mesurer. Ce qui est sous test est le verrou et le contrôle qui le suit —
        un seul appel HTTP, le second appelant réutilisant le jeton du premier.
        """
        neuf = jwt_factice(dans=timedelta(hours=1))
        appels = []
        premier_entre = threading.Event()
        obtenu = {"valeur": ""}

        def faux_urlopen(*_a, **_k):
            appels.append(1)
            premier_entre.set()
            threading.Event().wait(0.15)  # laisse le second thread se présenter

            class _Flux:
                def read(_s):
                    return json.dumps({"access": neuf, "refresh": "r2"}).encode()

                def __enter__(_s):
                    return _s

                def __exit__(_s, *a):
                    return False

            return _Flux()

        def faux_depot(_connector, kind, valeur, _libelle):
            if kind == CredentialKind.API_TOKEN:
                obtenu["valeur"] = valeur

        resultats = []

        def travailler():
            resultats.append(shield_auth.renouveler(self.connecteur))

        with patch("apps.integrations.shield_auth.urllib.request.urlopen",
                   side_effect=faux_urlopen), \
             patch.object(shield_auth, "jeton_utilisable", lambda _c: obtenu["valeur"]), \
             patch.object(shield_auth, "_secret", lambda _c, _k: "refresh-en-place"), \
             patch.object(shield_auth, "_deposer", faux_depot), \
             patch.object(shield_auth, "_memoriser", lambda _c, **_k: None), \
             patch.object(shield_auth, "_tracer", lambda _c, **_k: None), \
             patch.object(type(self.connecteur), "refresh_from_db", lambda _s, **_k: None):
            t1 = threading.Thread(target=travailler)
            t2 = threading.Thread(target=travailler)
            t1.start()
            premier_entre.wait(2)
            t2.start()
            t1.join(5)
            t2.join(5)

        self.assertEqual(len(appels), 1, f"{len(appels)} renouvellements au lieu d'un seul")
        self.assertTrue(all(ok for ok, _ in resultats), resultats)
        self.assertTrue(any("déjà renouvelé" in m for _ok, m in resultats),
                        "le second appel doit réutiliser le jeton du premier")


class RejeuApres401Test(SocleShield):
    """401 → renouvellement → rejeu UNE fois → 200. Jamais de boucle."""

    def test_un_401_est_rattrape_par_un_renouvellement_et_un_seul_rejeu(self):
        appels = {"n": 0}

        def faux_fetch(_self, _url):
            appels["n"] += 1
            if appels["n"] == 1:
                raise urllib.error.HTTPError("u", 401, "expiré", {}, None)
            return {"count": 1, "results": []}

        client = ShieldClient(BASE_SHIELD, {"Authorization": "Bearer perime"},
                              max_attempts=1,
                              on_auth_failure=lambda: {"Authorization": "Bearer neuf"})
        with patch.object(ShieldClient, "_fetch", faux_fetch):
            donnees = client.get_json("/api/v1/sites/sites/", {"limit": 1}, use_cache=False)

        self.assertEqual(donnees["count"], 1)
        self.assertEqual(appels["n"], 2, "un seul rejeu attendu")
        self.assertEqual(client.headers["Authorization"], "Bearer neuf")
        self.assertEqual(client.metrics.as_dict()["reauth"], 1)

    def test_un_401_qui_persiste_apres_renouvellement_ne_boucle_pas(self):
        appels = {"n": 0}

        def toujours_401(_self, _url):
            appels["n"] += 1
            raise urllib.error.HTTPError("u", 401, "refus", {}, None)

        client = ShieldClient(BASE_SHIELD, {"Authorization": "Bearer x"},
                              max_attempts=3,
                              on_auth_failure=lambda: {"Authorization": "Bearer y"})
        with patch.object(ShieldClient, "_fetch", toujours_401), patch("time.sleep"):
            with self.assertRaises(ShieldError) as ctx:
                client.get_json("/api/v1/sites/sites/", use_cache=False)

        self.assertEqual(ctx.exception.kind, "auth")
        self.assertIn("même après renouvellement", str(ctx.exception))
        self.assertEqual(appels["n"], 2, "deux appels au total : l'original et le rejeu")

    def test_un_403_ne_declenche_aucun_renouvellement(self):
        """403 est un défaut de droits, pas de session : renouveler n'y changerait
        rien et gaspillerait le quota."""
        tentatives = {"reauth": 0}

        def rappel():
            tentatives["reauth"] += 1
            return {"Authorization": "Bearer y"}

        def toujours_403(_self, _url):
            raise urllib.error.HTTPError("u", 403, "interdit", {}, None)

        client = ShieldClient(BASE_SHIELD, {}, max_attempts=1, on_auth_failure=rappel)
        with patch.object(ShieldClient, "_fetch", toujours_403):
            with self.assertRaises(ShieldError):
                client.get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(tentatives["reauth"], 0)

    def test_sans_rappel_le_comportement_dorigine_est_conserve(self):
        def toujours_401(_self, _url):
            raise urllib.error.HTTPError("u", 401, "refus", {}, None)

        client = ShieldClient(BASE_SHIELD, {}, max_attempts=1)
        with patch.object(ShieldClient, "_fetch", toujours_401):
            with self.assertRaises(ShieldError) as ctx:
                client.get_json("/api/v1/sites/sites/", use_cache=False)
        self.assertEqual(ctx.exception.kind, "auth")


class EtatEtTracabiliteTest(SocleShield):
    """Ce que l'écran peut dire, et ce que l'audit garde — sans jamais un jeton."""

    def test_letat_annonce_une_session_valide_et_le_renouvellement_automatique(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(hours=3)))
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        etat = shield_auth.etat_auth(self.connecteur)
        self.assertEqual(etat["etat"], "valide")
        self.assertTrue(etat["renouvellement_automatique"])
        self.assertIsNotNone(etat["expire_le"])

    def test_un_access_expire_avec_refresh_valide_nest_pas_une_panne(self):
        """Point 6 de la mission : cet état doit rester renouvelable, pas `error`."""
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(minutes=-10)))
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        self.assertEqual(shield_auth.etat_auth(self.connecteur)["etat"], "renouvelable")

    def test_sans_refresh_un_access_expire_exige_une_reauthentification(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(minutes=-10)))
        self.assertEqual(shield_auth.etat_auth(self.connecteur)["etat"], "auth_required")

    def test_letat_ne_contient_aucun_jeton(self):
        acces = jwt_factice(dans=timedelta(hours=1))
        self._deposer(CredentialKind.API_TOKEN, acces)
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-tres-secret")
        rendu = json.dumps(shield_auth.etat_auth(self.connecteur))
        self.assertNotIn(acces, rendu)
        self.assertNotIn("refresh-tres-secret", rendu)

    def test_le_renouvellement_est_trace_sans_le_moindre_secret(self):
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-tres-secret")
        neuf = jwt_factice(dans=timedelta(hours=1))

        class _Flux:
            def read(_s):
                return json.dumps({"access": neuf, "refresh": "refresh-neuf-secret"}).encode()

            def __enter__(_s):
                return _s

            def __exit__(_s, *a):
                return False

        AccessLog.objects.all().delete()
        with patch("apps.integrations.shield_auth.urllib.request.urlopen", return_value=_Flux()):
            shield_auth.renouveler(self.connecteur, force=True)

        trace = AccessLog.objects.order_by("-occurred_at").first()
        self.assertIsNotNone(trace)
        self.assertEqual(trace.action, "shield.auth.refresh")
        self.assertTrue(trace.payload["succes"])
        depose = json.dumps(trace.payload)
        for secret in ("refresh-tres-secret", "refresh-neuf-secret", neuf):
            self.assertNotIn(secret, depose)

    def test_un_echec_est_trace_avec_sa_cause_et_sans_secret(self):
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-tres-secret")
        AccessLog.objects.all().delete()
        erreur = urllib.error.HTTPError("u", 401, "refus", {}, None)
        with patch("apps.integrations.shield_auth.urllib.request.urlopen", side_effect=erreur):
            shield_auth.renouveler(self.connecteur, force=True)
        trace = AccessLog.objects.order_by("-occurred_at").first()
        self.assertFalse(trace.payload["succes"])
        self.assertEqual(trace.payload["cause"], "refresh_refuse")
        self.assertNotIn("refresh-tres-secret", json.dumps(trace.payload))

    def test_les_journaux_ne_portent_aucun_jeton(self):
        """Un secret dans un journal survit à toutes les rotations."""
        self._deposer(CredentialKind.OAUTH_REFRESH, "refresh-tres-secret")
        erreur = urllib.error.HTTPError("u", 500, "boum", {}, None)
        with self.assertLogs("apps.integrations", level="DEBUG") as journaux:
            with patch("apps.integrations.shield_auth.urllib.request.urlopen", side_effect=erreur):
                shield_auth.renouveler(self.connecteur, force=True)
            # Au moins une ligne, sinon assertLogs échoue et masque le sujet.
            shield_auth.logger.debug("sonde")
        self.assertNotIn("refresh-tres-secret", "\n".join(journaux.output))


class EnTetesDeSessionTest(SocleShield):
    """Le chemin complet : de la source aux en-têtes HTTP."""

    def test_les_entetes_portent_le_jeton_de_session(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(hours=1)))
        self._recharger()
        entetes = shield._auth_headers(self.source)
        self.assertTrue(entetes["Authorization"].startswith("Bearer "))

    def test_un_access_expire_declenche_le_renouvellement_a_la_construction(self):
        """C'est ce qui rend la session permanente : le renouvellement se fait avant
        l'appel métier, pas après son échec."""
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(minutes=-5)))
        self._deposer(CredentialKind.OAUTH_REFRESH, "r")
        neuf = jwt_factice(dans=timedelta(hours=2))

        class _Flux:
            def read(_s):
                return json.dumps({"access": neuf, "refresh": "r2"}).encode()

            def __enter__(_s):
                return _s

            def __exit__(_s, *a):
                return False

        self._recharger()
        with patch("apps.integrations.shield_auth.urllib.request.urlopen", return_value=_Flux()):
            entetes = shield._auth_headers(self.source)
        self.assertEqual(entetes["Authorization"], f"Bearer {neuf}")

    def test_sans_session_aucun_entete_dautorisation_nest_pose(self):
        """Mieux vaut pas d'en-tête qu'un en-tête vide : Shield répondra 401, et la
        santé du connecteur le qualifiera."""
        self._recharger()
        self.assertNotIn("Authorization", shield._auth_headers(self.source))

    def test_le_client_construit_sait_se_reauthentifier(self):
        self._deposer(CredentialKind.API_TOKEN, jwt_factice(dans=timedelta(hours=1)))
        self._recharger()
        client = shield.build_client(self.source)
        self.assertIsNotNone(client.on_auth_failure)

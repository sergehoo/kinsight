"""Diagnostic réseau à lancer DEPUIS le conteneur backend.

    docker compose exec backend python manage.py integrations_doctor
    docker compose exec backend python manage.py integrations_doctor --url https://api.kaydanshield.com/api/v1

Répond à une question que ni les logs ni le navigateur ne tranchent : quand un
test de connexion échoue en production, est-ce le DNS du conteneur, son magasin
de certificats, un pare-feu sortant, l'endpoint, ou le jeton ?

Chaque couche est vérifiée SÉPARÉMENT, dans l'ordre où elle peut casser, et la
dernière étape réutilise le client HTTP du connecteur — pas une requête écrite
pour l'occasion, sinon le diagnostic ne prouve rien sur le code réel.

Complémentaire de `shield_smoke`, qui valide le CONTRAT de l'API (comptages,
énumérations, filtres) sur une source déjà configurée : ici on descend sous
l'API, et la commande fonctionne même quand aucune source n'existe encore.

N'affiche jamais de jeton ni de donnée personnelle : adresses, codes HTTP,
métadonnées de certificat et compteurs uniquement.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from django.core.management.base import BaseCommand

from apps.integrations import shield
from apps.integrations.shield_client import ShieldError

# Endpoint métier documenté, volontairement le plus léger possible.
# `/api/v1` seul est à proscrire : il renvoie 404 par construction, ce qui
# n'apprend rien sur la joignabilité réelle de l'API.
ENDPOINT_TEMOIN = "/sites/sites/"
DEFAUT_BASE = "https://api.kaydanshield.com/api/v1"

OK, KO, INFO = "  OK  ", " ÉCHEC", " INFO "


class Command(BaseCommand):
    help = "Diagnostique, couche par couche, la sortie réseau du backend vers Kaydan Shield."

    def add_arguments(self, parser):
        parser.add_argument("--url", default="", help=f"URL de base à tester (défaut : source configurée, sinon {DEFAUT_BASE}).")
        parser.add_argument("--source", default="kaydan-shield", help="Code de la source à utiliser pour l'essai authentifié.")
        parser.add_argument("--timeout", type=int, default=8)

    # ── Rendu ────────────────────────────────────────────────────────────────
    def _ligne(self, marqueur: str, titre: str, detail: str = "") -> None:
        self.stdout.write(f"[{marqueur}] {titre}" + (f"\n         {detail}" if detail else ""))

    # ── Couches ──────────────────────────────────────────────────────────────
    def _dns(self, hote: str, port: int) -> bool:
        try:
            infos = socket.getaddrinfo(hote, port, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            self._ligne(KO, f"DNS — {hote} non résolu",
                        f"{exc}. Le résolveur du conteneur ne connaît pas ce nom : "
                        f"vérifiez la configuration DNS de Docker et l'accès sortant UDP/53.")
            return False
        adresses = sorted({info[4][0] for info in infos})
        self._ligne(OK, f"DNS — {hote} résolu", ", ".join(adresses))
        return True

    def _tls(self, hote: str, port: int, timeout: int) -> bool:
        contexte = ssl.create_default_context()
        try:
            with socket.create_connection((hote, port), timeout=timeout) as brut:
                with contexte.wrap_socket(brut, server_hostname=hote) as tls:
                    cert = tls.getpeercert() or {}
                    sujet = dict(x[0] for x in cert.get("subject", ())).get("commonName", "?")
                    emetteur = dict(x[0] for x in cert.get("issuer", ())).get("commonName", "?")
                    self._ligne(OK, f"TLS — poignée de main réussie ({tls.version()})",
                                f"certificat « {sujet} », émis par « {emetteur} », "
                                f"expire le {cert.get('notAfter', '?')}")
            return True
        except ssl.SSLCertVerificationError as exc:
            self._ligne(KO, "TLS — certificat non vérifiable",
                        f"{exc.verify_message or exc}. Le magasin de certificats du conteneur est "
                        f"absent ou incomplet : installez le paquet des autorités racines "
                        f"(ca-certificates) dans l'image backend.")
            return False
        except (TimeoutError, socket.timeout):
            self._ligne(KO, "TLS — délai dépassé",
                        "Le port n'a jamais répondu : pare-feu sortant ou filtrage sur le port 443.")
            return False
        except OSError as exc:
            self._ligne(KO, "TLS — connexion impossible", f"{type(exc).__name__} : {exc}")
            return False

    def _endpoint_sans_jeton(self, base: str, timeout: int) -> None:
        """Un 401 est le RÉSULTAT ATTENDU : il prouve que l'endpoint existe et
        qu'il exige une authentification. Un 404 signalerait une mauvaise URL."""
        url = f"{base.rstrip('/')}{ENDPOINT_TEMOIN}?limit=1"
        requete = urllib.request.Request(url, headers={"User-Agent": "k-insight-doctor"})
        try:
            with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
                self._ligne(INFO, f"Endpoint témoin — HTTP {reponse.status} sans jeton",
                            "L'API répond sans authentification : à vérifier côté Shield.")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self._ligne(OK, "Endpoint témoin — HTTP 401 sans jeton",
                            f"{ENDPOINT_TEMOIN} existe et exige une authentification : c'est le comportement documenté.")
            elif exc.code == 404:
                self._ligne(KO, "Endpoint témoin — HTTP 404",
                            f"{url} ne correspond à aucun endpoint : l'URL de base est probablement fausse.")
            else:
                self._ligne(INFO, f"Endpoint témoin — HTTP {exc.code}", exc.reason or "")
        except urllib.error.URLError as exc:
            self._ligne(KO, "Endpoint témoin — injoignable", str(exc.reason))

    def _essai_authentifie(self, code_source: str, timeout: int) -> None:
        """Dernière couche : le VRAI client du connecteur, avec le vrai jeton."""
        source = shield.get_shield_source()
        if source is None or source.slug != code_source:
            self._ligne(INFO, f"Essai authentifié — ignoré",
                        f"Aucune source « {code_source} » configurée. Créez-la depuis "
                        f"/admin/integrations/new, puis relancez cette commande.")
            return

        connecteur = getattr(source, "connector", None)
        jetons = list(connecteur.credentials.all()) if connecteur else []
        if not jetons:
            self._ligne(KO, "Essai authentifié — aucun secret enregistré",
                        "Le connecteur n'a pas de jeton : ajoutez-le depuis la fiche de la source.")
            return
        # Le masque, jamais la valeur.
        self._ligne(INFO, "Secret présent", ", ".join(f"{j.kind} · {j.masked}" for j in jetons))

        client = shield.build_client(source)
        client.timeout = timeout
        try:
            client.get_json(f"/api/v1{ENDPOINT_TEMOIN}", {"limit": 1}, use_cache=False)
            self._ligne(OK, "Essai authentifié — lecture autorisée",
                        "Le jeton est accepté : la source peut passer à l'état « connectée ».")
        except ShieldError as exc:
            explications = {
                "auth": "Jeton refusé (401/403) : il est absent, expiré, ou n'a pas les droits requis.",
                "timeout": "Shield n'a pas répondu à temps.",
                "network": "Shield injoignable depuis ce conteneur.",
                "rate_limit": "Quota atteint (429).",
                "http": "Shield a renvoyé une erreur explicite.",
                "payload": "Réponse illisible ou de forme inattendue.",
            }
            self._ligne(KO, f"Essai authentifié — échec qualifié « {exc.kind} »",
                        explications.get(exc.kind, str(exc)))

    def _boucle_locale(self, timeout: int) -> None:
        """Le backend se voit-il lui-même ? Sépare « backend mort » de « proxy mal câblé »."""
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/healthz/", timeout=timeout) as reponse:  # noqa: S310
                self._ligne(OK, f"Backend local — HTTP {reponse.status} sur /healthz/",
                            "gunicorn écoute bien : un 502 sur /api/ vient alors du proxy, pas du backend.")
        except urllib.error.HTTPError as exc:
            # Quelque chose ÉCOUTE et a répondu : ce n'est pas une panne de service,
            # c'est une route absente — ou un tout autre service sur le port 8000.
            self._ligne(KO, f"Backend local — HTTP {exc.code} sur /healthz/",
                        "Un service répond sur le port 8000 mais ne connaît pas cette route. "
                        "Hors du conteneur backend, c'est attendu.")
        except Exception as exc:  # noqa: BLE001
            self._ligne(KO, "Backend local — rien n'écoute sur 127.0.0.1:8000",
                        f"{type(exc).__name__}. Dans le conteneur backend, cela signifie que gunicorn "
                        f"n'a pas démarré : lisez les journaux du conteneur.")

    # ── Enchaînement ─────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        timeout = options["timeout"]
        base = options["url"]
        if not base:
            source = shield.get_shield_source()
            base = (shield._base_url(source) if source else "") or DEFAUT_BASE

        decoupe = urllib.parse.urlparse(base if "://" in base else f"https://{base}")
        hote = decoupe.hostname or ""
        port = decoupe.port or (443 if decoupe.scheme == "https" else 80)

        self.stdout.write(f"Cible : {base}\n")
        self._boucle_locale(timeout)
        if not hote:
            self._ligne(KO, "URL de base illisible", base)
            return
        # On descend couche par couche et on s'arrête à la première qui casse :
        # tester TLS quand le DNS échoue ne produirait qu'un second message inutile.
        if not self._dns(hote, port):
            return
        if decoupe.scheme == "https" and not self._tls(hote, port, timeout):
            return
        self._endpoint_sans_jeton(base, timeout)
        self._essai_authentifie(options["source"], timeout)

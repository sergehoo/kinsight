"""À qui fait-on confiance pour dire d'où vient une requête ?

Le backend est joignable sur un réseau Docker PARTAGÉ par tous les projets de la
plateforme : Traefik y est, mais aussi les conteneurs d'autres locataires. Or
`X-Forwarded-For` et `X-Forwarded-Proto` sont de simples en-têtes HTTP — n'importe
quel appelant les écrit comme il veut. Les croire sans condition, c'est laisser
choisir à l'appelant l'adresse IP inscrite dans la piste d'audit et le protocole
que Django croit voir.

Deux défauts symétriques existaient :

  — `SECURE_PROXY_SSL_HEADER` acceptait `X-Forwarded-Proto: https` de n'importe qui,
    donc `request.is_secure()` était contrôlé par l'appelant ;
  — l'audit enregistrait `REMOTE_ADDR`, infalsifiable mais inutile derrière un
    proxy : c'était l'adresse de Traefik, jamais celle de l'utilisateur.

Ce module tranche selon le PAIR de la connexion, seule valeur que l'appelant ne
peut pas choisir :

  pair reconnu comme proxy   → on lit `X-Forwarded-*` et on remonte au vrai client ;
  pair inconnu               → les en-têtes de proxy sont RETIRÉS de la requête, et
                               l'adresse retenue est celle du pair lui-même.

Un conteneur tiers qui forge `X-Forwarded-For: 8.8.8.8` voit donc sa propre adresse
inscrite dans l'audit, et son `X-Forwarded-Proto` ignoré. La falsification échoue
sans qu'il en soit averti.

Par défaut, aucun proxy n'est reconnu : la posture stricte est celle qui ne fait
confiance à personne. `TRUSTED_PROXY_HOSTS` / `TRUSTED_PROXY_CIDRS` l'ouvrent
explicitement — sur Dokploy, le nom du conteneur Traefik suffit.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# En-têtes par lesquels un appelant pourrait se réclamer d'un proxy.
EN_TETES_DE_PROXY = (
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_FORWARDED_PROTO",
    "HTTP_X_FORWARDED_HOST",
    "HTTP_X_FORWARDED_PORT",
    "HTTP_X_FORWARDED_SCHEME",
    "HTTP_X_REAL_IP",
    "HTTP_FORWARDED",
)

# Le conteneur du proxy est recréé à chaque déploiement, avec une nouvelle adresse :
# on résout son nom régulièrement plutôt que de figer une IP. Fenêtre courte, pour
# suivre un redéploiement sans interroger le DNS à chaque requête.
_TTL_RESOLUTION = 30.0
_verrou = threading.Lock()
_cache: tuple[float, tuple] = (0.0, ())


def _reseaux_declares() -> list:
    """Les réseaux de confiance, tels que déclarés en configuration."""
    reseaux = []
    for brut in getattr(settings, "TRUSTED_PROXY_CIDRS", ()):
        try:
            reseaux.append(ipaddress.ip_network(brut.strip(), strict=False))
        except ValueError:
            logger.warning("TRUSTED_PROXY_CIDRS : « %s » n'est pas un réseau valide.", brut)
    return reseaux


def _reseaux_resolus() -> list:
    """Les adresses actuelles des hôtes de proxy déclarés, en /32 ou /128."""
    reseaux = []
    for hote in getattr(settings, "TRUSTED_PROXY_HOSTS", ()):
        hote = hote.strip()
        if not hote:
            continue
        try:
            infos = socket.getaddrinfo(hote, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            # Nom inconnu : on ne fait alors confiance à personne de ce côté, ce qui
            # est le comportement voulu — mieux vaut une piste d'audit qui pointe le
            # proxy qu'une piste falsifiable.
            logger.warning("TRUSTED_PROXY_HOSTS : « %s » ne se résout pas.", hote)
            continue
        for info in infos:
            try:
                reseaux.append(ipaddress.ip_network(info[4][0], strict=False))
            except ValueError:
                continue
    return reseaux


def reseaux_de_confiance() -> tuple:
    """Ensemble des réseaux de confiance, avec un cache borné dans le temps."""
    global _cache
    maintenant = time.monotonic()
    expiration, valeur = _cache
    if maintenant < expiration:
        return valeur
    with _verrou:
        expiration, valeur = _cache
        if maintenant < expiration:
            return valeur
        calcule = tuple(_reseaux_declares() + _reseaux_resolus())
        _cache = (maintenant + _TTL_RESOLUTION, calcule)
        return calcule


def oublier_les_resolutions() -> None:
    """Vide le cache. Utile aux tests, et après un changement de configuration."""
    global _cache
    _cache = (0.0, ())


def _adresse(valeur: str | None):
    """Analyse une adresse, en tolérant la forme `ip:port` et les crochets IPv6."""
    if not valeur:
        return None
    brut = valeur.strip()
    if brut.startswith("["):  # [2001:db8::1]:443
        brut = brut.partition("]")[0].lstrip("[")
    elif brut.count(":") == 1:  # 10.0.0.1:443
        brut = brut.split(":", 1)[0]
    try:
        return ipaddress.ip_address(brut)
    except ValueError:
        return None


def _est_de_confiance(adresse) -> bool:
    return adresse is not None and any(adresse in reseau for reseau in reseaux_de_confiance())


def _client_derriere_le_proxy(entetes: str, pair):
    """Remonte la chaîne `X-Forwarded-For` jusqu'au premier maillon non fiable.

    La chaîne se lit « client, proxy1, proxy2 » : la droite est le plus proche de
    nous. On écarte les maillons de confiance en partant de la droite ; le premier
    qui ne l'est pas est le client. Prendre la gauche à l'aveugle, comme on le voit
    souvent, revient à laisser le client écrire lui-même son adresse.
    """
    maillons = [_adresse(m) for m in entetes.split(",")]
    for adresse in reversed(maillons):
        if adresse is not None and not _est_de_confiance(adresse):
            return adresse
    # Tous les maillons sont des proxys connus : le pair reste la meilleure réponse.
    return pair


class TrustedProxyMiddleware:
    """Pose `request.client_ip` et `request.via_trusted_proxy`, et neutralise les
    en-têtes de proxy quand ils viennent d'un appelant inconnu.

    À placer EN PREMIER : `SecurityMiddleware` et la protection CSRF lisent
    `request.is_secure()`, qui dépend de `X-Forwarded-Proto`. Nettoyer après elles
    ne servirait à rien.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        pair = _adresse(request.META.get("REMOTE_ADDR"))
        de_confiance = _est_de_confiance(pair)

        if de_confiance:
            transmis = request.META.get("HTTP_X_FORWARDED_FOR", "")
            client = _client_derriere_le_proxy(transmis, pair) if transmis else pair
        else:
            # L'appelant n'est pas un proxy reconnu : tout ce qu'il prétend sur
            # l'origine de la requête est écarté, en-têtes compris — sinon
            # `SECURE_PROXY_SSL_HEADER` les relirait plus loin dans la pile.
            for entete in EN_TETES_DE_PROXY:
                request.META.pop(entete, None)
            client = pair

        request.via_trusted_proxy = de_confiance
        request.client_ip = str(client) if client is not None else None
        return self.get_response(request)


def client_ip(request) -> str | None:
    """L'adresse du client, telle que le middleware l'a établie.

    Retombe sur le pair de la connexion hors requête HTTP complète (tests,
    commandes de gestion) — jamais sur un en-tête.
    """
    ip = getattr(request, "client_ip", None)
    if ip is not None:
        return ip
    adresse = _adresse(request.META.get("REMOTE_ADDR") if hasattr(request, "META") else None)
    return str(adresse) if adresse else None


def audit_source(request) -> dict:
    """Ce qu'il faut inscrire dans la piste d'audit sur l'origine d'une requête.

    Se destine à être déballé : `AccessLog.record(..., **audit_source(request))`.
    Fonctionne même si le middleware n'est pas actif (tests unitaires, commandes),
    en retombant sur le pair de la connexion — jamais sur un en-tête.
    """
    return {"ip": client_ip(request), "via_proxy": getattr(request, "via_trusted_proxy", None)}

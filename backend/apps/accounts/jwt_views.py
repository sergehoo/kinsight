"""Renouvellement de session JWT, durci.

POURQUOI CE MODULE EXISTE. `TokenRefreshSerializer` de simplejwt résout
l'utilisateur porté par le jeton avec un `objects.get()` nu :

    user := get_user_model().objects.get(**{api_settings.USER_ID_FIELD: user_id})

Si le compte a disparu entre l'émission du jeton et son renouvellement — départ
d'un collaborateur, purge, restauration de base — l'exception `DoesNotExist`
remonte jusqu'au gestionnaire d'erreurs de Django et le point d'accès répond
**500**, accompagné d'une page de traceback de 18 Ko.

Trois conséquences, toutes mauvaises :
  - le navigateur ne peut pas distinguer « jeton mort » de « serveur en panne »,
    et notre client traite justement un 5xx comme un incident passager : il ne
    déconnecte pas, et l'écran reste bloqué sur une erreur dont il ne sort plus ;
  - chaque onglet encore ouvert rejoue l'appel en boucle et remplit les journaux
    de tracebacks identiques ;
  - en DEBUG, ce traceback expose le chemin des fichiers et la configuration.

Le défaut était DORMANT tant que le frontend n'appelait jamais le
renouvellement. Il est devenu atteignable le jour où on l'a branché : c'est la
rançon ordinaire d'un chemin qu'on vient d'ouvrir, et c'est pour cela qu'on le
ferme ici plutôt que de le découvrir en production.

Un jeton qui désigne un compte inexistant est un jeton INVALIDE, pas une panne
de serveur : il se répond 401, et le navigateur ramène alors à la connexion.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

MOTIF = "Jeton de renouvellement invalide : reconnectez-vous."


class SerialiseurRenouvellement(TokenRefreshSerializer):
    def validate(self, attrs):
        # Le compte porté par le jeton doit EXISTER et être ACTIF. simplejwt ne le
        # vérifie qu'à partir de 5.4 ; la production épingle 5.3.1, où un compte
        # désactivé ou supprimé renouvelait sa session (200) — la vérification est
        # donc faite ici, quelle que soit la version.
        try:
            porteur = RefreshToken(attrs["refresh"]).payload.get(api_settings.USER_ID_CLAIM)
        except TokenError:
            porteur = None  # jeton illisible : le parent lève l'InvalidToken habituel
        if porteur is not None:
            compte = get_user_model().objects.filter(**{api_settings.USER_ID_FIELD: porteur}).first()
            if compte is None or not api_settings.USER_AUTHENTICATION_RULE(compte):
                raise InvalidToken(MOTIF)
        try:
            return super().validate(attrs)
        except ObjectDoesNotExist as exc:
            # On ne dit PAS « ce compte n'existe pas » : la réponse servirait à
            # énumérer les comptes. Le porteur d'un jeton n'a besoin que de
            # savoir que ce jeton ne vaut plus rien.
            raise InvalidToken(MOTIF) from exc


class VueRenouvellement(TokenRefreshView):
    serializer_class = SerialiseurRenouvellement

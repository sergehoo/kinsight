"""La piste d'audit enregistre-t-elle la bonne adresse ?

    docker compose exec backend python manage.py proxy_doctor

Question qui ne se lit ni dans le navigateur ni dans les journaux du proxy. Le
backend partage un réseau Docker avec les autres projets : il ne croit
`X-Forwarded-For` que si le pair de la connexion est le proxy déclaré dans
`TRUSTED_PROXY_HOSTS`. Ce réglage est donc le seul à devoir être juste — et
l'adresse du conteneur Traefik changeant à chaque déploiement, c'est son NOM qui
est déclaré, résolu à la volée.

Trois issues, et la commande dit laquelle est en vigueur :

  proxy reconnu, adresses publiques dans la trace  → l'audit désigne l'utilisateur ;
  proxy non reconnu                                → la trace retient l'adresse du
                                                     proxy : infalsifiable, mais elle
                                                     ne désigne personne ;
  lignes marquées « appel direct »                 → quelqu'un a interrogé le backend
                                                     sans passer par le proxy.

Affiche des adresses IP — donnée à caractère personnel — donc uniquement les
dernières lignes, et rien d'autre de la charge d'audit.
"""

from __future__ import annotations

import ipaddress

from django.core.management.base import BaseCommand

from apps.audit.middleware import oublier_les_resolutions, reseaux_de_confiance
from apps.audit.models import AccessLog

OK, KO, INFO = "  OK  ", " ÉCHEC", " INFO "
DERNIERES = 10


class Command(BaseCommand):
    help = "Vérifie que la piste d'audit retient l'adresse réelle du client, et non celle du proxy."

    def add_arguments(self, parser):
        parser.add_argument("--lignes", type=int, default=DERNIERES,
                            help=f"Nombre de lignes d'audit à examiner (défaut : {DERNIERES}).")

    def _ligne(self, marqueur: str, titre: str, detail: str = "") -> None:
        self.stdout.write(f"[{marqueur}] {titre}" + (f"\n         {detail}" if detail else ""))

    def handle(self, *args, **options):
        from django.conf import settings

        hotes = list(getattr(settings, "TRUSTED_PROXY_HOSTS", []))
        cidrs = list(getattr(settings, "TRUSTED_PROXY_CIDRS", []))
        self.stdout.write(f"TRUSTED_PROXY_HOSTS : {hotes or '(vide)'}")
        self.stdout.write(f"TRUSTED_PROXY_CIDRS : {cidrs or '(vide)'}\n")

        # On repart d'une résolution fraîche : un cache tiède masquerait un nom devenu faux.
        oublier_les_resolutions()
        reseaux = reseaux_de_confiance()

        if not reseaux:
            self._ligne(KO, "Aucun proxy reconnu",
                        "Les en-têtes X-Forwarded-* seront ignorés et la piste d'audit retiendra "
                        "l'adresse du proxy — infalsifiable, mais elle ne désigne personne. "
                        "Renseignez le nom du conteneur Traefik : "
                        "docker ps --format '{{.Names}}' | grep -i traefik")
        else:
            self._ligne(OK, f"{len(reseaux)} adresse(s) de proxy reconnue(s)",
                        ", ".join(str(r) for r in reseaux))

        self._analyser_les_traces(options["lignes"], reseaux)

    def _analyser_les_traces(self, combien: int, reseaux) -> None:
        lignes = list(AccessLog.objects.order_by("-occurred_at")[:combien])
        if not lignes:
            self._ligne(INFO, "Aucune trace d'accès enregistrée",
                        "Ouvrez une page du tableau de bord, puis relancez cette commande.")
            return

        self.stdout.write(f"\nDernières {len(lignes)} traces :")
        reels = proxys = directs = inconnus = 0
        for trace in lignes:
            adresse = self._adresse(trace.ip_address)
            if trace.payload.get("appel_direct"):
                marque, directs = "appel DIRECT (hors proxy)", directs + 1
            elif adresse is None:
                marque, inconnus = "adresse absente", inconnus + 1
            elif any(adresse in r for r in reseaux):
                marque, proxys = "adresse du PROXY", proxys + 1
            elif adresse.is_private:
                marque, inconnus = "adresse privée (conteneur ?)", inconnus + 1
            else:
                marque, reels = "client réel", reels + 1
            self.stdout.write(
                f"  {trace.occurred_at:%d/%m %H:%M}  {str(trace.ip_address or '—'):>16}  "
                f"{trace.action[:22]:22}  {marque}"
            )

        self.stdout.write("")
        if reels:
            self._ligne(OK, f"{reels} trace(s) portent une adresse publique",
                        "L'audit désigne bien l'utilisateur : le proxy est reconnu et sa chaîne "
                        "X-Forwarded-For est remontée correctement.")
        if proxys:
            self._ligne(KO, f"{proxys} trace(s) portent l'adresse du proxy",
                        "Ces lignes ne désignent personne. Si elles sont récentes, "
                        "TRUSTED_PROXY_HOSTS ne correspond pas au conteneur Traefik en service.")
        if directs:
            self._ligne(KO, f"{directs} trace(s) marquée(s) « appel direct »",
                        "Le backend a été interrogé sans passer par le proxy — depuis un autre "
                        "conteneur du réseau partagé. L'adresse retenue est celle de l'appelant, "
                        "pas ce qu'il prétendait : à investiguer, mais la trace est fiable.")
        if inconnus:
            self._ligne(INFO, f"{inconnus} trace(s) sans adresse publique exploitable",
                        "Normal pour du trafic interne (healthcheck, tâche planifiée).")

    @staticmethod
    def _adresse(valeur):
        try:
            return ipaddress.ip_address(valeur) if valeur else None
        except ValueError:
            return None

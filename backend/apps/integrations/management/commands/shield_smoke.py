"""Smoke test Kaydan Shield — peu d'appels, avant toute série lourde.

    python manage.py shield_smoke

Vérifie ce qui doit être confirmé sur l'instance RÉELLE avant de lui envoyer des
collectes de période : que l'authentification passe, que `count` reflète bien le
total filtré, que les booléens documentés sont acceptés, et que les valeurs
d'énumération se comportent comme le Swagger l'annonce.

N'affiche jamais le jeton, ni aucune donnée personnelle : uniquement des
compteurs et des codes de retour.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.integrations import shield
from apps.integrations import shield_endpoints as EP
from apps.integrations.shield_client import ShieldError

OK, KO, WARN = "  OK  ", " ÉCHEC", " ALERTE"

# Identifiant de site qui ne peut correspondre à aucune ligne. Sert de SENTINELLE :
# un filtre honoré rend zéro, un filtre ignoré rend le total non filtré. Le choix
# d'un très grand entier plutôt que 0 ou -1 est délibéré : ces deux valeurs sont
# parfois traitées comme « pas de filtre » par les couches de validation.
SITE_IMPOSSIBLE = 999_999_999


class Command(BaseCommand):
    help = "Vérifie l'accès Kaydan Shield en une poignée d'appels, avant les séries."

    def handle(self, *args, **options):
        source = shield.get_shield_source()
        if source is None:
            self.stderr.write("Aucune source `kaydan-shield` configurée.")
            return
        base = shield._base_url(source)
        if not base:
            self.stderr.write("Source sans URL de base.")
            return

        client = shield.build_client(source)
        self.stdout.write(f"Instance : {base}\n")
        checks: list[tuple[str, bool, str]] = []

        def run(label, fn):
            try:
                value = fn()
                checks.append((label, True, str(value)))
                return value
            except ShieldError as exc:
                checks.append((label, False, f"{exc.kind}{f'/{exc.status}' if exc.status else ''}"))
                return None

        # 1. Authentification et joignabilité, au coût d'un seul appel.
        run("auth + joignabilité", lambda: client.get_json(EP.SITES, {"limit": 1}, use_cache=False) and "réponse reçue")
        # 2. Compteurs de référentiel.
        sites = run("sites (count)", lambda: client.count(EP.SITES))
        run("employés (count)", lambda: client.count(EP.EMPLOYEES))
        run("ouvriers (count)", lambda: client.count(EP.WORKERS))
        # 3. Présence du jour.
        run("présence du jour", lambda: client.get_json(EP.ATTENDANCE_TODAY) and "réponse reçue")
        # 4. Le booléen documenté est-il accepté ?
        #
        # Une seule lecture ne peut pas le dire : si DRF ignore `present`, il rend
        # le total, et « présents ≤ total » reste vrai. On lit donc les DEUX faces
        # du booléen — leur somme doit valoir le total quand le filtre est honoré.
        total = run("attendance (sans filtre)", lambda: client.count(EP.ATTENDANCE_DAYS))
        presents = run("attendance present=true", lambda: client.count(EP.ATTENDANCE_DAYS, {"present": "true"}))
        non_presents = run("attendance present=false",
                           lambda: client.count(EP.ATTENDANCE_DAYS, {"present": "false"}))
        # 5. Le filtre site est-il effectif ?
        first_site = None
        try:
            rows = client.results(EP.SITES, {"limit": 1})
            first_site = rows[0].get("id") if rows else None
        except ShieldError:
            pass
        scoped = run(f"attendance site={first_site}",
                     lambda: client.count(EP.ATTENDANCE_DAYS, {"site": first_site})) if first_site else None
        # La sentinelle, appliquée AUSSI au site — c'est la correction du contrôle
        # précédent, qui concluait « filtre site effectif » sur la seule inégalité
        # `scoped <= total`. Un filtre ignoré rend exactement le total : l'inégalité
        # large était donc satisfaite par le cas même qu'elle prétendait détecter.
        # Un identifiant de site qui ne peut pas exister tranche sans ambiguïté.
        site_sentinelle = run("attendance site=<id inexistant>",
                              lambda: client.count(EP.ATTENDANCE_DAYS, {"site": SITE_IMPOSSIBLE}))
        # 6. La pagination expose-t-elle bien un total cohérent ?
        page = run("pagination (count vs results)",
                   lambda: client.get_json(EP.SITES, {"limit": 2}, use_cache=False))
        # 7. Les énumérations sont-elles VRAIMENT honorées ?
        #
        # C'est le piège le plus coûteux de cette API : DRF ignore SILENCIEUSEMENT
        # un filtre inconnu et renvoie l'ensemble non filtré, avec un 200. Un KPI
        # « accès refusés » bâti sur une valeur d'énumération erronée compterait
        # donc TOUS les événements — un chiffre faux, jamais signalé comme tel.
        # Une valeur sentinelle absurde tranche : si elle renvoie le même total que
        # l'absence de filtre, le serveur ignore ce qu'on lui demande.
        acces_total = run("accès (sans filtre)", lambda: client.count(EP.ACCESS_EVENTS))
        acces_refuses = run("accès decision=denied",
                            lambda: client.count(EP.ACCESS_EVENTS, {"decision": "denied"}))
        acces_sentinelle = run("accès decision=<valeur absurde>",
                               lambda: client.count(EP.ACCESS_EVENTS, {"decision": "zzz-inexistant"}))

        self.stdout.write("")
        for label, ok, detail in checks:
            self.stdout.write(f"[{OK if ok else KO}] {label:32s} {detail}")

        # ── Confirmations explicites demandées avant toute collecte lourde ──
        self.stdout.write("\nConfirmations :")

        if isinstance(total, int) and isinstance(presents, int) and isinstance(non_presents, int):
            # Somme des deux faces == total : le booléen partitionne réellement.
            partitionne = presents + non_presents == total
            self.stdout.write(f"[{OK if partitionne else WARN}] filtre `present` HONORÉ "
                              f"(true {presents} + false {non_presents} = {presents + non_presents}, "
                              f"total {total})")
            if not partitionne:
                self.stdout.write("      → le booléen n'est pas appliqué comme un partitionnement : "
                                  "NE PAS bâtir de série sur ces comptes.")
            if presents == total and non_presents == total:
                self.stdout.write("      → les deux faces rendent le total : le filtre est IGNORÉ.")
        else:
            self.stdout.write(f"[{WARN}] filtre `present` non vérifiable (lecture en échec)")

        if isinstance(scoped, int) and isinstance(total, int) and isinstance(site_sentinelle, int):
            # Le verdict tient à la SENTINELLE, pas à l'inégalité : un site
            # impossible doit rendre autre chose que le total non filtré.
            ignore = site_sentinelle == total
            self.stdout.write(f"[{KO if ignore else OK}] filtre `site` effectif "
                              f"(site réel {scoped}, site impossible {site_sentinelle}, total {total})")
            if ignore:
                self.stdout.write("      → un site inexistant renvoie le total : le filtre `site` est "
                                  "IGNORÉ. Toute ventilation par site serait le total répété.")
        elif isinstance(scoped, int):
            self.stdout.write(f"[{WARN}] filtre `site` non concluant (sentinelle non lue)")

        if isinstance(page, dict):
            forme = {"count", "results"} <= set(page)
            n = len(page.get("results") or [])
            self.stdout.write(f"[{OK if forme else WARN}] enveloppe paginée count/results "
                              f"(count={page.get('count')}, page={n})")
            if isinstance(sites, int) and page.get("count") != sites:
                self.stdout.write("      → le total varie entre deux lectures : à investiguer.")

        if isinstance(acces_total, int) and isinstance(acces_sentinelle, int):
            if acces_sentinelle == acces_total:
                self.stdout.write(f"[{KO}] énumération `decision` IGNORÉE par le serveur "
                                  f"(valeur absurde → {acces_sentinelle}, comme sans filtre)")
                self.stdout.write("      → tout indicateur bâti sur `decision` serait FAUX : "
                                  "ne pas alimenter le cockpit Risques.")
            else:
                lisible = acces_refuses if isinstance(acces_refuses, int) else "?"
                self.stdout.write(f"[{OK}] énumération `decision` honorée "
                                  f"(absurde {acces_sentinelle} ≠ total {acces_total}, "
                                  f"denied {lisible})")
                if isinstance(acces_refuses, int) and acces_refuses > acces_total:
                    self.stdout.write(f"[{WARN}] refusés ({acces_refuses}) > total ({acces_total}) : incohérent.")
        else:
            self.stdout.write(f"[{WARN}] énumération `decision` non vérifiable (lecture en échec)")

        m = client.metrics.as_dict()
        moyenne = (m["duration_ms"] / m["calls"]) if m["calls"] else 0
        self.stdout.write(f"\nCoût du smoke test : {m['calls']} appels, "
                          f"{m['duration_ms']:.0f} ms au total, {moyenne:.0f} ms par appel, "
                          f"erreurs {m['errors'] or 'aucune'}")
        if any(not ok for _, ok, _ in checks):
            self.stdout.write("\nDes vérifications ont échoué : ne pas lancer les séries.")

"""GET /api/v1/governance/hr/history/ — une métrique RH sur une période réelle.

Paramètres :
  metric      identifiant canonique (`hr.taux_presence_jour`)            — requis
  periode     7j | 30j | 90j | trimestre | annee | personnalisee        — défaut 30j
  year, quarter                       (trimestre, annee)
  date_from, date_to                  (personnalisee, ≤ 366 jours)
  compare     precedente | n-1 | les-deux | aucune                       — défaut les-deux
  dimension   groupe | site | type | departement                          — défaut groupe
  code        un code de la dimension (site, employee/worker…)
  ventilation 1 → la valeur de la période pour CHAQUE code de la dimension
  subsidiary  filiale demandée, toujours intersectée avec le périmètre

Toute période s'arrête à la VEILLE : la journée en cours n'est pas close, elle
reste live (`aujourd_hui`). Une période sans mesure rend `unknown`, jamais 0.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.rbac import can_access_domain
from apps.audit.middleware import audit_source
from apps.audit.models import AccessLog

from . import historique as H
from .hr_registry import ODOO, REGISTRE, SHIELD, resoudre
from .hr_sources import contexte_pour, societes_des_filiales
from .models import Dimension, KpiSnapshot

FENETRES = {"7j": 7, "30j": 30, "90j": 90}
MAX_JOURS_PERSONNALISES = 366
DIMENSIONS_SHIELD = {Dimension.GROUPE, Dimension.SITE, Dimension.TYPE}
DIMENSIONS_ODOO = {Dimension.GROUPE, Dimension.DEPARTEMENT}


class _Refus(Exception):
    def __init__(self, motif: str, code_http: int = status.HTTP_200_OK):
        super().__init__(motif)
        self.motif, self.code_http = motif, code_http


def periode_demandee(params, aujourd_hui: date) -> tuple[H.Periode, str]:
    """La période et son libellé, bornée à la veille. Lève `_Refus` si invalide."""
    hier = aujourd_hui - timedelta(days=1)
    nature = params.get("periode") or "30j"
    if nature in FENETRES:
        n = FENETRES[nature]
        return H.Periode(hier - timedelta(days=n - 1), hier), f"{n} derniers jours"
    try:
        annee = int(params.get("year") or aujourd_hui.year)
    except ValueError as exc:
        raise _Refus("Année invalide.", status.HTTP_400_BAD_REQUEST) from exc
    if nature == "trimestre":
        try:
            t = int(params.get("quarter") or (aujourd_hui.month - 1) // 3 + 1)
        except ValueError as exc:
            raise _Refus("Trimestre invalide.", status.HTTP_400_BAD_REQUEST) from exc
        if not 1 <= t <= 4:
            raise _Refus("Le trimestre doit être entre 1 et 4.", status.HTTP_400_BAD_REQUEST)
        mois_fin = t * 3
        debut, fin = date(annee, mois_fin - 2, 1), date(annee, mois_fin, monthrange(annee, mois_fin)[1])
        libelle = f"T{t} {annee}"
    elif nature == "annee":
        debut, fin, libelle = date(annee, 1, 1), date(annee, 12, 31), f"Année {annee}"
    elif nature == "personnalisee":
        try:
            debut = date.fromisoformat(params.get("date_from") or "")
            fin = date.fromisoformat(params.get("date_to") or "")
        except ValueError as exc:
            raise _Refus("Dates de période illisibles (AAAA-MM-JJ attendu).",
                         status.HTTP_400_BAD_REQUEST) from exc
        if fin < debut:
            raise _Refus("La date de fin précède la date de début.", status.HTTP_400_BAD_REQUEST)
        if (fin - debut).days + 1 > MAX_JOURS_PERSONNALISES:
            raise _Refus(f"Période limitée à {MAX_JOURS_PERSONNALISES} jours.", status.HTTP_400_BAD_REQUEST)
        libelle = f"{debut.isoformat()} → {fin.isoformat()}"
    else:
        raise _Refus(f"Période inconnue : « {nature} ».", status.HTTP_400_BAD_REQUEST)
    if debut > hier:
        raise _Refus(f"{libelle} n'a pas encore commencé : aucune journée close à lire.")
    nature_calendaire = nature if nature in ("trimestre", "annee") else "fenetre"
    return H.Periode(debut, min(fin, hier), nature_calendaire), libelle


def _portee(user, metric, dimension: str, filiale_demandee: str | None) -> list[str] | None:
    """Codes de la dimension à lire pour CET utilisateur, ou None = tous.

    Lève `_Refus` quand la portée ne peut pas être honorée sans inventer un
    rattachement ou servir des chiffres hors périmètre."""
    scope = user.scope()
    filiales = set(scope.subsidiaries) if not scope.is_group else None
    if filiale_demandee and filiale_demandee != "all":
        if filiales is not None and filiale_demandee not in filiales:
            # Le filtre ne peut JAMAIS élargir le périmètre : on n'ira pas chercher
            # la filiale demandée, on refuse.
            raise _Refus("Filiale demandée hors de votre périmètre.", status.HTTP_403_FORBIDDEN)
        filiales = {filiale_demandee}

    if metric.source == SHIELD:
        if dimension not in DIMENSIONS_SHIELD:
            raise _Refus(f"La dimension « {dimension} » n'existe pas pour Shield.",
                         status.HTTP_400_BAD_REQUEST)
        if filiales is not None:
            raise _Refus("Non rattaché : Shield ne rattache pas ses sites aux filiales, son "
                         "historique est un historique Groupe.")
        return None

    if dimension not in DIMENSIONS_ODOO:
        raise _Refus(f"La dimension « {dimension} » n'existe pas pour Odoo.", status.HTTP_400_BAD_REQUEST)
    if filiales is None:
        return None
    if dimension != Dimension.GROUPE:
        raise _Refus("Ventilation Odoo par département réservée au périmètre Groupe : elle "
                     "n'est pas historisée par société.")
    societes = societes_des_filiales(frozenset(filiales))
    if not societes:
        raise _Refus("Hors périmètre : aucune société Odoo n'est rattachée à cette filiale.")
    return [str(s) for s in societes]


class HrHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        p = request.query_params
        metric_id = p.get("metric") or ""
        metric = REGISTRE.get(metric_id)
        if metric is None:
            return Response({"detail": f"Métrique inconnue : « {metric_id} »."},
                            status=status.HTTP_400_BAD_REQUEST)
        if not can_access_domain(request.user, metric.domaine):
            return Response({"detail": f"Accès au domaine « {metric.domaine} » non autorisé pour votre rôle."},
                            status=status.HTTP_403_FORBIDDEN)

        base = {"metric_id": metric.id, "label": metric.libelle, "definition": metric.definition,
                "unit": metric.unite, "format": metric.format, "source": metric.source,
                "regle": metric.agregat}
        if metric.source not in (SHIELD, ODOO):
            return Response({**base, "status": "disconnected", "reason": metric.motif_absence,
                             "points": []})

        dimension = p.get("dimension") or Dimension.GROUPE
        code = p.get("code") or ""
        try:
            periode, libelle = periode_demandee(p, timezone.localdate())
            codes = _portee(request.user, metric, dimension, p.get("subsidiary"))
        except _Refus as refus:
            if refus.code_http != status.HTTP_200_OK:
                return Response({**base, "detail": refus.motif}, status=refus.code_http)
            return Response({**base, "status": "disconnected", "reason": refus.motif, "points": []})

        # Pour une filiale Odoo, la « dimension » lue est la société ; le code
        # demandé ne peut que la restreindre davantage.
        dimension_lue = Dimension.SOCIETE if codes is not None else dimension
        if code and dimension_lue != Dimension.GROUPE:
            codes = [code] if codes is None else [c for c in codes if c == code]
        codes_lus = codes if dimension_lue != Dimension.GROUPE else None

        resultat = H.agreger(metric.id, periode, dimension=dimension_lue, codes=codes_lus)
        points = H.serie(metric.id, periode, dimension=dimension_lue, codes=codes_lus)

        comparer = p.get("compare") or "les-deux"
        comparaisons = {}
        est_taux = metric.format == "pct"
        if comparer in ("precedente", "les-deux"):
            ref = H.agreger(metric.id, periode.precedente(), dimension=dimension_lue, codes=codes_lus)
            comparaisons["precedente"] = H.comparer(resultat, ref, est_taux=est_taux)
        if comparer in ("n-1", "les-deux"):
            ref = H.agreger(metric.id, periode.annee_precedente(), dimension=dimension_lue, codes=codes_lus)
            comparaisons["n_1"] = H.comparer(resultat, ref, est_taux=est_taux)

        ventilation = None
        if p.get("ventilation") == "1" and dimension_lue in (Dimension.SITE, Dimension.TYPE,
                                                             Dimension.DEPARTEMENT):
            ventilation = self._ventiler(metric.id, periode, dimension_lue)

        premiere = (KpiSnapshot.objects.filter(metric_id__in=[metric.id, *metric.numerateur,
                                                              *metric.denominateur],
                                               statut="measured")
                    .order_by("jour").values_list("jour", flat=True).first())

        # La valeur du JOUR, live, à côté de la période — marquée comme telle.
        aujourd_hui = None
        if metric.instant:
            live = resoudre(metric.id, contexte_pour(request.user))
            aujourd_hui = {"value": live.get("value"), "status": live.get("status"),
                           "reason": live.get("reason"), "date": timezone.localdate().isoformat()}

        scope = request.user.scope()
        AccessLog.record(
            user=request.user, action="query_hr_history", metric_key=metric.id,
            scope_codes=(["*"] if scope.is_group else sorted(scope.subsidiaries)),
            payload={"periode": libelle, "debut": periode.debut.isoformat(), "fin": periode.fin.isoformat(),
                     "dimension": dimension, "code": code, "subsidiary": p.get("subsidiary") or ""},
            **audit_source(request),
        )
        return Response({
            **base,
            "status": resultat["status"],
            "periode": {"debut": periode.debut.isoformat(), "fin": periode.fin.isoformat(),
                        "libelle": libelle, "jusqu_a": "veille"},
            "valeur": {k: resultat[k] for k in ("value", "status", "couverture")},
            "points": points,
            "comparaisons": comparaisons,
            "ventilation": ventilation,
            "aujourd_hui": aujourd_hui,
            "historique_depuis": premiere.isoformat() if premiere else None,
            "dimension": dimension, "code": code,
            "perimetre": "GROUP" if scope.is_group else sorted(scope.subsidiaries),
        })

    @staticmethod
    def _ventiler(metric_id: str, periode: H.Periode, dimension: str) -> list[dict]:
        metric = REGISTRE[metric_id]
        composantes = {metric_id, *metric.numerateur, *metric.denominateur}
        codes = (KpiSnapshot.objects.filter(metric_id__in=composantes, dimension=dimension,
                                            jour__gte=periode.debut, jour__lte=periode.fin)
                 .values_list("code", "libelle").distinct())
        lignes = []
        for code, libelle in sorted(set(codes)):
            agregat = H.agreger(metric_id, periode, dimension=dimension, codes=[code])
            lignes.append({"code": code, "libelle": libelle, "value": agregat["value"],
                           "couverture": agregat["couverture"]})
        # Tri par valeur décroissante, les inconnues à la fin : un classement ne
        # range pas un site sans mesure parmi les plus faibles.
        return sorted(lignes, key=lambda l: (l["value"] is None, -(l["value"] or 0)))

"""Filtres du cockpit RH : UNE lecture des paramètres, pour toutes les vues.

L'inventaire a trouvé le sélecteur de période écrit quatre fois, des bornes de fin
incluses côté écran et exclues côté serveur, un défaut figé à « T1 2026 » quand
l'année était à son quatrième trimestre, et des filtres affichés qui ne
modifiaient aucune requête. Toutes les vues RH lisent désormais leurs filtres ici :
deux écrans ne peuvent plus diverger sur ce que « T3 » ou « ce site » veut dire.

Paramètres reconnus (mêmes noms partout — modules, historique, alertes, exports) :
  periode      trimestre | annee | 7j | 30j | 90j | personnalisee   défaut : trimestre
  year, quarter                                                       défaut : courants
  date_from, date_to   (personnalisee)
  subsidiary   filiale, toujours intersectée avec le périmètre serveur
  site         code de site Shield
  type         employee | worker
  departement  libellé de département Odoo

Toute période s'arrête à la VEILLE : la journée en cours n'est pas close.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from rest_framework import status

from . import historique as H
from .models import Dimension

FENETRES = {"7j": 7, "30j": 30, "90j": 90}
MAX_JOURS_PERSONNALISES = 366
TYPES = {"employee": "Employés", "worker": "Ouvriers"}


class FiltreInvalide(Exception):
    """Un filtre que la requête ne peut pas honorer.

    `code_http` 200 : la requête est légitime mais n'a rien à lire (période future,
    portée impossible) — on répond avec un motif. 400/403 : la requête elle-même
    est fautive ou interdite."""

    def __init__(self, motif: str, code_http: int = status.HTTP_200_OK):
        super().__init__(motif)
        self.motif, self.code_http = motif, code_http


def trimestre_courant(jour: date) -> int:
    return (jour.month - 1) // 3 + 1


@dataclass(frozen=True)
class Filtres:
    periode: H.Periode
    libelle: str
    nature: str
    subsidiary: str | None
    site: str | None
    type: str | None
    departement: str | None

    def dimension_presence(self) -> tuple[str, str | None]:
        """Dimension de l'historique Shield à lire : site, type, ou Groupe.
        Site ET type à la fois ne se croisent pas : l'historique ne porte pas ce
        croisement, et le reconstituer serait une approximation."""
        if self.site and self.type:
            raise FiltreInvalide("Site et type de personnel ne se combinent pas : l'historique "
                                 "ne croise pas ces deux dimensions.", status.HTTP_400_BAD_REQUEST)
        if self.site:
            return Dimension.SITE, self.site
        if self.type:
            return Dimension.TYPE, self.type
        return Dimension.GROUPE, None

    def comme_trace(self) -> dict:
        return {"periode": self.libelle, "debut": self.periode.debut.isoformat(),
                "fin": self.periode.fin.isoformat(), "subsidiary": self.subsidiary or "",
                "site": self.site or "", "type": self.type or "", "departement": self.departement or ""}


def lire(params, aujourd_hui: date) -> Filtres:
    """Les filtres d'une requête, validés. Lève `FiltreInvalide`."""
    hier = aujourd_hui - timedelta(days=1)
    nature = params.get("periode") or "trimestre"

    if nature in FENETRES:
        n = FENETRES[nature]
        periode, libelle = H.Periode(hier - timedelta(days=n - 1), hier), f"{n} derniers jours"
    else:
        try:
            annee = int(params.get("year") or aujourd_hui.year)
        except (TypeError, ValueError) as exc:
            raise FiltreInvalide("Année invalide.", status.HTTP_400_BAD_REQUEST) from exc
        if nature == "trimestre":
            try:
                t = int(params.get("quarter") or trimestre_courant(aujourd_hui))
            except (TypeError, ValueError) as exc:
                raise FiltreInvalide("Trimestre invalide.", status.HTTP_400_BAD_REQUEST) from exc
            if not 1 <= t <= 4:
                raise FiltreInvalide("Le trimestre doit être entre 1 et 4.", status.HTTP_400_BAD_REQUEST)
            mois_fin = t * 3
            debut = date(annee, mois_fin - 2, 1)
            fin = date(annee, mois_fin, monthrange(annee, mois_fin)[1])
            libelle = f"T{t} {annee}"
        elif nature == "annee":
            debut, fin, libelle = date(annee, 1, 1), date(annee, 12, 31), f"Année {annee}"
        elif nature == "personnalisee":
            try:
                debut = date.fromisoformat(params.get("date_from") or "")
                fin = date.fromisoformat(params.get("date_to") or "")
            except ValueError as exc:
                raise FiltreInvalide("Dates de période illisibles (AAAA-MM-JJ attendu).",
                                     status.HTTP_400_BAD_REQUEST) from exc
            if fin < debut:
                raise FiltreInvalide("La date de fin précède la date de début.", status.HTTP_400_BAD_REQUEST)
            if (fin - debut).days + 1 > MAX_JOURS_PERSONNALISES:
                raise FiltreInvalide(f"Période limitée à {MAX_JOURS_PERSONNALISES} jours.",
                                     status.HTTP_400_BAD_REQUEST)
            libelle = f"{debut.strftime('%d/%m/%Y')} → {fin.strftime('%d/%m/%Y')}"
        else:
            raise FiltreInvalide(f"Période inconnue : « {nature} ».", status.HTTP_400_BAD_REQUEST)
        if debut > hier:
            raise FiltreInvalide(f"{libelle} n'a pas encore commencé : aucune journée close à lire.")
        if fin > hier:
            libelle = f"{libelle} à date"
        nature_calendaire = nature if nature in ("trimestre", "annee") else "fenetre"
        periode = H.Periode(debut, min(fin, hier), nature_calendaire)

    type_ = params.get("type") or None
    if type_ and type_ not in TYPES:
        raise FiltreInvalide(f"Type de personnel inconnu : « {type_} ».", status.HTTP_400_BAD_REQUEST)
    if type_ and params.get("site"):
        raise FiltreInvalide("Site et type de personnel ne se combinent pas : l'historique ne "
                             "croise pas ces deux dimensions.", status.HTTP_400_BAD_REQUEST)
    filiale = params.get("subsidiary") or None
    return Filtres(periode=periode, libelle=libelle, nature=nature,
                   subsidiary=None if filiale in (None, "all") else filiale,
                   site=params.get("site") or None, type=type_,
                   departement=params.get("departement") or None)

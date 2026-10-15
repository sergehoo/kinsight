"""HRDecisionEngine — données réelles → calculs déterministes → IA → synthèse.

L'IA est une couche d'ANALYSE, jamais une source de chiffres. Le moteur procède
en deux temps, et seul le second touche à un modèle de langage :

1. CONSTATS (déterministes). Chaque constat est une règle écrite appliquée à
   l'historique réel, sous les filtres et le périmètre de l'utilisateur : un
   signal hors zone normale, un site loin du Groupe, des retards concentrés sur
   quelques sites, une variation notable, un historique trop mince pour conclure.
   Il porte sa valeur, sa comparaison, sa période, sa source, sa confiance, un
   lien d'exploration et une action recommandée — écrite, pas générée.

2. SYNTHÈSE (sur demande). Le modèle reçoit les seuls constats et rédige : résumé
   exécutif, anomalies, causes probables MARQUÉES comme hypothèses, risques,
   recommandations, priorités, questions. Garde-fou : toute phrase qui contient
   un nombre absent des constats est retirée — un chiffre que le modèle aurait
   « déduit » ne passe pas. Sans modèle disponible, la synthèse est composée des
   constats eux-mêmes, et le dit.

Aucun constat n'est fabriqué pour atteindre un quota : moins de trois constats,
c'est une information (« rien d'autre à signaler »), pas un vide à combler.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import historique as H
from .filtres import Filtres
from .lecture_rh import portee
from .hr_registry import REGISTRE
from .models import Dimension
from .signaux_rh import SOURCE_DE, confiance, evaluer

# ── Règles d'analyse, écrites une fois ───────────────────────────────────────
ECART_SITE_NOTABLE = 10.0        # pts de présence sous le Groupe
VARIATION_NOTABLE = 3.0          # pts de présence vs la période précédente
CONCENTRATION_RETARDS = 50.0     # % des retards portés par les 3 sites les plus touchés
SITES_MIN_CONCENTRATION = 4      # en deçà, « concentré sur 3 sites » ne dit rien
COUVERTURE_MINCE = 0.5           # part de jours mesurés sous laquelle on prévient
MAX_CONSTATS = 7

ORDRE = {"critique": 0, "surveillance": 1, "info": 2}
PRESENCE = "/dashboard/capital-humain/presence"

ACTIONS = {
    "presence_faible": "Identifier les sites et les jours qui tirent la présence vers le bas, puis revoir "
                       "les plannings avec les responsables de site.",
    "absenteisme": "Croiser les absences pointées avec les congés et autorisations déclarés ; ouvrir un point "
                   "avec les managers des sites les plus touchés.",
    "retard_eleve": "Vérifier les horaires de démarrage et les conditions d'accès (transport, terminaux) sur "
                    "les sites concernés.",
    "site_sous_effectif": "Valider la capacité opérationnelle des sites listés et arbitrer un renfort ou une "
                          "réaffectation.",
    "effectif_critique": "Rapprocher la baisse des sorties déclarées et vérifier l'exhaustivité de la "
                         "déclaration dans Shield.",
}

# Ce que mesure le signal, pour que le constat ne répète pas son titre.
GRANDEUR = {"presence_faible": "Taux de présence", "absenteisme": "Taux d'absence pointée",
            "retard_eleve": "Taux de retard"}

NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")


def _fr(v: float) -> str:
    texte = f"{v:.1f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _ecart_pts(e: float) -> str:
    return f"{'+' if e > 0 else '−' if e < 0 else ''}{_fr(abs(e))} pt{'s' if abs(e) >= 2 else ''}"


class HRDecisionEngine:
    def __init__(self, user, filtres: Filtres):
        self.user = user
        self.filtres = filtres
        self.periode = filtres.libelle
        self._signaux = evaluer(user, filtres)["signaux"]

    # ── 1. Constats déterministes ────────────────────────────────────────────
    def constats(self) -> list[dict[str, Any]]:
        sortie: list[dict[str, Any]] = []
        par_cle = {s["cle"]: s for s in self._signaux}

        for s in self._signaux:
            if s["etat"] in ("critique", "surveillance"):
                sortie.append(self._depuis_signal(s))

        presence = par_cle.get("presence_faible")
        if presence and presence["etat"] == "normal":
            variation = self._variation(presence)
            if variation:
                sortie.append(variation)
        sortie.extend(self._ecarts_au_groupe(presence))
        concentration = self._concentration_retards()
        if concentration:
            sortie.append(concentration)
        mince = self._couverture_mince(presence)
        if mince:
            sortie.append(mince)

        sortie.sort(key=lambda c: ORDRE[c["severite"]])
        return sortie[:MAX_CONSTATS]

    def angles_morts(self) -> list[dict[str, str]]:
        """Les signaux non mesurés : ce que la décision ne peut pas encore voir."""
        return [{"libelle": s["libelle"], "motif": s.get("motif") or ""}
                for s in self._signaux if s["etat"] == "non_mesure"]

    def _base(self, ident: str, titre: str, constat: str, severite: str, **extra) -> dict[str, Any]:
        return {"id": ident, "titre": titre, "constat": constat, "severite": severite,
                "periode": self.periode, "lien": PRESENCE, **extra}

    def _depuis_signal(self, s: dict) -> dict[str, Any]:
        seuils = s["seuils"]
        palier = seuils["critique"] if s["etat"] == "critique" else seuils["surveillance"]
        op = "<" if seuils["sens"] == "bas" else ">"
        comparaison = None
        c = s.get("comparaison") or {}
        if s["cle"] == "site_sous_effectif":
            pire = s["pire"]
            n = len(s.get("details") or [])
            constat = (f"{n} site(s) sous {_fr(seuils['surveillance'])} % de présence ; le plus faible, "
                       f"{pire['libelle']}, est à {_fr(pire['valeur'])} %.")
        elif s["cle"] == "effectif_critique":
            constat = (f"Effectif déclaré de {_fr(s['effectif'])} contre {_fr(c['value'])} sur la période "
                       f"précédente, soit une baisse de {_fr(s['valeur'])} %.")
        else:
            constat = (f"{GRANDEUR.get(s['cle'], s['libelle'])} de {_fr(s['valeur'])} % sur la période "
                       f"(seuil {s['etat']} {op} {_fr(palier)} %).")
            if c.get("ecart") is not None:
                comparaison = f"{_ecart_pts(c['ecart'])} vs période précédente"
                constat = constat[:-1] + f", {comparaison}."
        return self._base(f"signal.{s['cle']}", s["libelle"], constat, s["etat"],
                          valeur=s["valeur"], unite="%", comparaison=comparaison,
                          source=s.get("source"), confiance=s.get("confiance"),
                          regle=s["regle"], action=ACTIONS.get(s["cle"]), lien=s["lien"],
                          details=s.get("details") or None)

    def _variation(self, presence: dict) -> dict[str, Any] | None:
        c = presence.get("comparaison") or {}
        ecart = c.get("ecart")
        if ecart is None or abs(ecart) < VARIATION_NOTABLE:
            return None
        baisse = ecart < 0
        return self._base(
            "variation.presence", "Présence en baisse" if baisse else "Présence en hausse",
            f"Taux de présence de {_fr(presence['valeur'])} %, {_ecart_pts(ecart)} vs la période précédente "
            f"({_fr(c['value'])} %).",
            "surveillance" if baisse else "info",
            valeur=presence["valeur"], unite="%", comparaison=f"{_ecart_pts(ecart)} vs période précédente",
            source=presence.get("source"), confiance=presence.get("confiance"),
            regle=f"Variation du taux de présence d'au moins {_fr(VARIATION_NOTABLE)} pts entre deux périodes.",
            action=("Rechercher ce qui a changé entre les deux périodes (sites, plannings, événements)."
                    if baisse else None))

    def _lecture_sites(self, metric_id: str):
        """Ventilation par site permise ? Seulement sur l'ensemble des sites (Groupe)."""
        try:
            dimension, codes = portee(self.user, REGISTRE[metric_id], self.filtres)
        except Exception:  # noqa: BLE001 — périmètre restreint ou filtre : pas de comparaison de sites
            return False
        return dimension == Dimension.GROUPE and codes is None

    def _ecarts_au_groupe(self, presence: dict | None) -> list[dict[str, Any]]:
        if not presence or presence.get("valeur") is None or not self._lecture_sites("hr.taux_presence_jour"):
            return []
        groupe = presence["valeur"]
        sites = [l for l in H.ventiler("hr.taux_presence_jour", self.filtres.periode, Dimension.SITE)
                 if l["value"] is not None and l["value"] - groupe <= -ECART_SITE_NOTABLE]
        if not sites:
            return []
        sites.sort(key=lambda l: l["value"])
        lignes = [f"{l['libelle']} : présence {_fr(l['value'])} %, {_ecart_pts(round(l['value'] - groupe, 1))} vs Groupe"
                  for l in sites[:3]]
        return [self._base(
            "ecart.sites", f"{len(sites)} site(s) loin derrière le Groupe",
            "; ".join(lignes) + f" (Groupe : {_fr(groupe)} %).", "surveillance",
            valeur=sites[0]["value"], unite="%", source="Kaydan Shield", confiance=confiance(sites[0]["couverture"]),
            regle=f"Sites dont la présence de la période est inférieure d'au moins {_fr(ECART_SITE_NOTABLE)} pts "
                  f"à celle du Groupe.",
            action="Comparer l'organisation de ces sites à celle des sites au niveau du Groupe.",
            details=[{"code": l["code"], "libelle": l["libelle"], "valeur": l["value"]} for l in sites[:5]])]

    def _concentration_retards(self) -> dict[str, Any] | None:
        if not self._lecture_sites("hr.retards_jour"):
            return None
        sites = [l for l in H.ventiler("hr.retards_jour", self.filtres.periode, Dimension.SITE)
                 if l["value"] is not None]
        total = sum(l["value"] for l in sites)
        if len(sites) < SITES_MIN_CONCENTRATION or total <= 0:
            return None
        top = sorted(sites, key=lambda l: -l["value"])[:3]
        part = round(sum(l["value"] for l in top) * 100 / total, 1)
        if part < CONCENTRATION_RETARDS:
            return None
        noms = ", ".join(l["libelle"] for l in top)
        return self._base(
            "concentration.retards", "Retards concentrés sur 3 sites",
            f"{_fr(part)} % des retards de la période viennent de 3 sites sur {len(sites)} : {noms}.", "info",
            valeur=part, unite="%", source="Kaydan Shield",
            regle=f"Part des retards (moyenne par jour) portée par les 3 sites les plus touchés, signalée au-delà "
                  f"de {_fr(CONCENTRATION_RETARDS)} % dès {SITES_MIN_CONCENTRATION} sites mesurés.",
            action="Traiter ces sites en priorité : une action ciblée y pèse plus qu'une mesure générale.",
            details=[{"code": l["code"], "libelle": l["libelle"], "valeur": l["value"]} for l in top])

    def _couverture_mince(self, presence: dict | None) -> dict[str, Any] | None:
        couverture = (presence or {}).get("couverture")
        if not couverture or not couverture.get("jours"):
            return None
        part = couverture["jours_mesures"] / couverture["jours"]
        if part >= COUVERTURE_MINCE:
            return None
        return self._base(
            "couverture.mince", "Historique trop mince pour conclure",
            f"{couverture['jours_mesures']} jour(s) mesuré(s) sur {couverture['jours']} : les constats de la "
            f"période sont de confiance faible.", "info",
            source="Kaydan Shield", confiance="faible",
            regle=f"Moins de {int(COUVERTURE_MINCE * 100)} % des jours de la période sont mesurés.",
            action="Rejouer la collecte des journées manquantes (historiser --presence).")

    # ── 2. Synthèse (IA sous garde-fou) ──────────────────────────────────────
    def synthese(self, constats: list[dict], router=None) -> dict[str, Any]:
        from apps.ai_copilot.providers import AIProviderRouter, GroundedFacts, ProviderUnavailable

        angles = self.angles_morts()
        deterministe = synthese_deterministe(constats, angles)
        faits = {"periode": self.periode, "constats": constats, "angles_morts": angles}
        consigne = (
            "Rédige une synthèse de gouvernance RH à partir des SEULS constats fournis. Réponds par un "
            "objet JSON strict aux clés : resume, anomalies, hypotheses, risques, recommandations, priorites, "
            "questions — chacune une liste de phrases courtes en français. N'écris AUCUN nombre qui ne figure "
            "pas dans les constats. Chaque cause probable va dans « hypotheses » et commence par "
            "« Hypothèse : ». Constats : " + json.dumps(faits, ensure_ascii=False, default=str)
        )
        routeur = router or AIProviderRouter()
        try:
            resultat = routeur.complete(consigne, {"periode": self.periode},
                                        GroundedFacts(grounded=True, answer=json.dumps(deterministe, ensure_ascii=False)))
        except ProviderUnavailable:
            return {"sections": deterministe, "fournisseur": None, "ia": False, "phrases_retirees": 0}

        sections = _lire_json(resultat.text)
        ia = resultat.provider != "offline-grounded"
        if sections is None:
            return {"sections": deterministe, "fournisseur": resultat.provider, "ia": False,
                    "phrases_retirees": 0, "note": "Réponse du modèle illisible : synthèse composée des constats."}
        sections, retirees = garde_fou(sections, autorises=_nombres(json.dumps(faits, ensure_ascii=False, default=str)))
        return {"sections": sections, "fournisseur": resultat.provider, "ia": ia, "phrases_retirees": retirees}


CLES_SYNTHESE = ("resume", "anomalies", "hypotheses", "risques", "recommandations", "priorites", "questions")


def synthese_deterministe(constats: list[dict], angles: list[dict]) -> dict[str, list[str]]:
    """La synthèse SANS modèle : les constats eux-mêmes, rangés. Aucune hypothèse —
    on n'avance pas de cause sans analyse."""
    graves = [c for c in constats if c["severite"] in ("critique", "surveillance")]
    return {
        "resume": [c["constat"] for c in constats[:3]] or ["Aucun seuil franchi sur la période : rien à signaler."],
        "anomalies": [f"{c['titre']} — {c['constat']}" for c in graves],
        "hypotheses": [],
        "risques": [f"{c['titre']} ({c['severite']})" for c in constats if c["severite"] == "critique"],
        "recommandations": [c["action"] for c in constats if c.get("action")],
        "priorites": [c["titre"] for c in graves[:3]],
        "questions": [f"{a['libelle']} : {a['motif']}" for a in angles],
    }


def _lire_json(texte: str) -> dict | None:
    if not texte:
        return None
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut < 0 or fin <= debut:
        return None
    try:
        brut = json.loads(texte[debut:fin + 1])
    except ValueError:
        return None
    if not isinstance(brut, dict):
        return None
    return {k: [str(x) for x in brut.get(k) or [] if isinstance(x, (str, int, float))] for k in CLES_SYNTHESE}


def _nombres(texte: str) -> set[float]:
    return {round(float(n.replace(",", ".")), 1) for n in NOMBRE.findall(texte)}


def garde_fou(sections: dict[str, list[str]], *, autorises: set[float]) -> tuple[dict[str, list[str]], int]:
    """Retire toute phrase portant un nombre absent des constats ; marque les hypothèses."""
    retirees = 0
    propre: dict[str, list[str]] = {}
    for cle in CLES_SYNTHESE:
        gardees = []
        for phrase in sections.get(cle, []):
            if _nombres(phrase) - autorises:
                retirees += 1
                continue
            if cle == "hypotheses" and not phrase.lower().startswith("hypothèse"):
                phrase = f"Hypothèse : {phrase}"
            gardees.append(phrase)
        propre[cle] = gardees
    return propre, retirees

"""Extraction des entreprises citées dans les articles de presse."""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel

from ..modeles import Signal
from .client import ClientIA, lire_prompt

log = logging.getLogger(__name__)
TAILLE_LOT = 40


class ArticleAnalyse(BaseModel):
    numero: int
    entreprise: str | None
    francaise: bool
    evenement: Literal[
        "levee_de_fonds", "rachat_croissance_externe", "nouvelle_usine_ou_site",
        "recrutement_massif", "projet_ia", "contrat_important", "difficulte", "autre",
    ]
    metier_ia: bool
    ville: str | None
    resume: str


class AnalyseLot(BaseModel):
    articles: list[ArticleAnalyse]


# Mode dégradé : « Acme lève 3 millions », « Acme rachète Beta », « Acme ouvre une usine »…
RE_VERBE = re.compile(
    r"^(?:[^:]{0,40}:\s*)?(?P<nom>[A-Z0-9][\w&'’\.\- ]{1,50}?)\s+"
    r"(?:lève|boucle|réalise|annonce|rachète|acquiert|s'offre|ouvre|inaugure|investit|recrute|déploie)\b"
)
RE_SOURCE = re.compile(r"\s+-\s+[^-]+$")  # « Titre - Les Echos » -> « Titre »


def extraire_par_regles(signal: Signal) -> Signal | None:
    titre = RE_SOURCE.sub("", signal.titre)
    m = RE_VERBE.match(titre)
    if not m:
        return None
    signal.entreprise_nom = m.group("nom").strip(" -’'")
    signal.meta["evenement"] = "autre"
    return signal


def extraire(articles: list[Signal], ia: ClientIA | None, effort: str = "low") -> list[Signal]:
    """Renvoie les articles rattachés à une entreprise française hors métier IA."""
    if not ia:
        retenus = [s for s in (extraire_par_regles(a) for a in articles) if s]
        log.info("Extraction par règles : %d articles rattachés à une entreprise", len(retenus))
        return retenus

    systeme = lire_prompt("extraction.md")
    retenus: list[Signal] = []
    for debut in range(0, len(articles), TAILLE_LOT):
        lot = articles[debut : debut + TAILLE_LOT]
        lignes = [
            f"[{i}] {a.date.isoformat() if a.date else 'date inconnue'} | {a.titre}\n    {a.texte[:400]}"
            for i, a in enumerate(lot)
        ]
        analyse = ia.structurer(systeme, "\n".join(lignes), AnalyseLot, effort=effort)
        if not analyse:
            retenus += [s for s in (extraire_par_regles(a) for a in lot) if s]
            continue
        for item in analyse.articles:
            if not (0 <= item.numero < len(lot)) or not item.entreprise:
                continue
            if not item.francaise or item.metier_ia or item.evenement == "difficulte":
                continue
            signal = lot[item.numero]
            signal.entreprise_nom = item.entreprise
            signal.ville = item.ville
            signal.meta.update({"evenement": item.evenement, "resume": item.resume})
            retenus.append(signal)
    log.info("Extraction IA : %d articles rattachés à une entreprise cible", len(retenus))
    return retenus

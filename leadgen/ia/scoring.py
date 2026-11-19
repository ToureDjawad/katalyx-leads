"""Pré-tri déterministe puis qualification de chaque entreprise par Claude."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ..modeles import Candidat
from .client import ClientIA, lire_prompt

log = logging.getLogger(__name__)

POIDS_SIGNAL = {
    "offre_emploi_ia": 40,
    "appel_offres": 35,
    "projet_ia": 35,
    "offre_emploi_douleur": 25,
    "levee_de_fonds": 22,
    "rachat_croissance_externe": 20,
    "nouvelle_usine_ou_site": 20,
    "recrutement_massif": 18,
    "contrat_important": 15,
    "autre": 8,
}
SIGNAUX_EXPLICITES = {"offre_emploi_ia", "appel_offres", "projet_ia"}
TRANCHES_PME_ETI = {"11", "12", "21", "22", "31", "32", "41", "42"}

LIBELLES_TRANCHES = {
    "00": "0 salarié", "01": "1-2", "02": "3-5", "03": "6-9", "11": "10-19", "12": "20-49",
    "21": "50-99", "22": "100-199", "31": "200-249", "32": "250-499", "41": "500-999",
    "42": "1 000-1 999", "51": "2 000-4 999", "52": "5 000-9 999", "53": "10 000 et plus",
}

CasUsage = Literal["Audit IA", "Agent Devis", "Agent Qualité", "Agent Commercial",
                   "Agent Administratif", "Agent Documentation", "Agent Reporting"]


class Evaluation(BaseModel):
    eligible: bool
    raison_exclusion: str | None = Field(description="Pourquoi le lead est écarté, sinon null")
    temperature: Literal["chaud", "tiède", "froid"]
    score: int = Field(description="Score de 0 à 100")
    signal_cle: str = Field(description="Le signal le plus fort, en une phrase, avec sa date et sa source")
    justification: str = Field(description="Trois à cinq phrases qui expliquent la température et le score")
    cas_usage: list[CasUsage]
    decideur_cible: str = Field(description="Fonction à appeler")
    accroche_appel: str
    questions_decouverte: list[str]
    confiance: Literal["haute", "moyenne", "faible"]


def type_effectif(signal) -> str:
    """Le type utile au scoring : l'événement pour un article, le type de signal sinon."""
    if signal.type == "actualite":
        return signal.meta.get("evenement") or "autre"
    return signal.type


def pre_score(candidat: Candidat, config: dict, aujourdhui: date | None = None) -> float:
    """Classement grossier, gratuit et reproductible, pour n'envoyer à Claude que les meilleurs."""
    cible = config["cible"]
    fraicheur_max = config["general"]["fraicheur_max_jours"]
    forces = sorted((POIDS_SIGNAL.get(type_effectif(s), 8) for s in candidat.signaux), reverse=True)
    score = forces[0] + min(10, 5 * (len(forces) - 1)) if forces else 0
    ages = [a for a in (s.age_jours(aujourdhui) for s in candidat.signaux) if a is not None]
    if ages:
        score += 15 * max(0.0, 1 - min(ages) / fraicheur_max)
    e = candidat.entreprise
    if e:
        naf = (e.naf or "").replace(".", "")
        if any(naf.startswith(p.replace(".", "")) for p in cible["naf_prioritaires"]):
            score += 15
        if e.tranche_effectif in TRANCHES_PME_ETI:
            score += 10
        if e.departement in cible["departements_prioritaires"]:
            score += 10
    return round(score, 1)


def fiche(candidat: Candidat, aujourdhui: date) -> str:
    e = candidat.entreprise
    donnees = {
        "date_du_jour": aujourdhui.isoformat(),
        "entreprise": {
            "nom": e.nom,
            "siren": e.siren,
            "activite_naf": e.naf,
            "effectif": LIBELLES_TRANCHES.get(e.tranche_effectif or "", "inconnu"),
            "categorie": e.categorie,
            "chiffre_affaires": f"{e.chiffre_affaires:,.0f} € ({e.annee_ca})".replace(",", " ") if e.chiffre_affaires else None,
            "siege": f"{e.code_postal} {e.ville}",
            "date_creation": e.date_creation,
            "dirigeants": [f"{d.nom_complet} ({d.qualite})" for d in e.dirigeants[:6]],
            "site_web": e.site_web,
        },
        "signaux": [
            {
                "source": s.source,
                "type": type_effectif(s),
                "date": s.date.isoformat() if s.date else None,
                "anciennete_jours": s.age_jours(aujourdhui),
                "titre": s.titre,
                "resume": s.meta.get("resume"),
                "extrait": (s.texte or "")[:1500],
                "lieu": s.ville,
                "url": s.url,
                **({"date_limite_reponse": s.meta["date_limite"]} if s.meta.get("date_limite") else {}),
            }
            for s in sorted(candidat.signaux, key=lambda s: s.date or date.min, reverse=True)[:5]
        ],
    }
    return json.dumps(donnees, ensure_ascii=False, indent=2)


def evaluer_ia(candidat: Candidat, ia: ClientIA, effort: str, aujourdhui: date) -> dict | None:
    systeme = lire_prompt("scoring.md").replace("{offre}", lire_prompt("offre_katalyx.md"))
    message = "Qualifie ce lead.\n\n" + fiche(candidat, aujourdhui)
    evaluation = ia.structurer(systeme, message, Evaluation, effort=effort)
    if not evaluation:
        return None
    resultat = evaluation.model_dump()
    resultat["score"] = max(0, min(100, resultat["score"]))
    resultat["mode"] = "claude"
    return resultat


def evaluer_heuristique(candidat: Candidat, aujourdhui: date) -> dict:
    """Mode dégradé sans clé Anthropic : règles simples, clairement signalées dans l'export."""
    principal = max(candidat.signaux, key=lambda s: (POIDS_SIGNAL.get(type_effectif(s), 8), s.date or date.min))
    age = principal.age_jours(aujourdhui)
    explicite = type_effectif(principal) in SIGNAUX_EXPLICITES
    if explicite and age is not None and age <= 21 and candidat.pre_score >= 50:
        temperature = "chaud"
    elif candidat.pre_score >= 45:
        temperature = "tiède"
    else:
        temperature = "froid"
    cas = {
        "offre_emploi_douleur": ["Audit IA", "Agent Devis"],
        "appel_offres": ["Audit IA"],
        "levee_de_fonds": ["Audit IA", "Agent Administratif"],
        "rachat_croissance_externe": ["Audit IA", "Agent Reporting"],
    }.get(type_effectif(principal), ["Audit IA"])
    quand = principal.date.strftime("%d/%m/%Y") if principal.date else "récemment"
    return {
        "eligible": True,
        "raison_exclusion": None,
        "temperature": temperature,
        "score": int(min(100, candidat.pre_score)),
        "signal_cle": f"{principal.titre} ({quand}, {principal.source})",
        "justification": "Évaluation automatique par règles (mode dégradé sans Claude) : "
                         f"force du signal « {type_effectif(principal)} », fraîcheur de {age} jours, "
                         "secteur, taille et localisation de l'entreprise.",
        "cas_usage": cas,
        "decideur_cible": "Dirigeant",
        "accroche_appel": f"Bonjour, j'ai vu le {quand} : {principal.titre}. Chez Katalyx, nous construisons des agents IA "
                          "qui font gagner des heures sur ce type de process. Auriez-vous 20 minutes pour estimer le gain ?",
        "questions_decouverte": [
            "Quels process répétitifs prennent le plus de temps à vos équipes ?",
            "Avez-vous déjà testé des outils d'IA, et qu'est-ce qui a bloqué ?",
            "Qui serait impliqué dans la décision d'un audit ?",
        ],
        "confiance": "faible",
        "mode": "heuristique",
    }

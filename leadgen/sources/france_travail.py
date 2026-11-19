"""Offres d'emploi via l'API officielle France Travail (Offres d'emploi v2).

Une entreprise qui recrute un « chef de projet IA » a un besoin explicite et daté.
Une PME industrielle qui recrute un « deviseur » révèle une douleur que l'agent Devis de Katalyx résout.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests

from ..http import DELAI
from ..modeles import Signal
from ..texte import nettoyer_html

log = logging.getLogger(__name__)

URL_JETON = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
URL_RECHERCHE = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def _jeton(session: requests.Session, client_id: str, secret: str) -> str:
    reponse = session.post(
        URL_JETON,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": secret,
            "scope": "api_offresdemploiv2 o2dsoffre",
        },
        timeout=DELAI,
    )
    reponse.raise_for_status()
    return reponse.json()["access_token"]


def _vers_signal(offre: dict, type_signal: str, mot_cle: str) -> Signal | None:
    entreprise = offre.get("entreprise") or {}
    nom = (entreprise.get("nom") or "").strip()
    if not nom:  # offre anonyme : inexploitable pour un appel
        return None
    lieu = offre.get("lieuTravail") or {}
    date_creation = offre.get("dateCreation")
    try:
        jour = datetime.fromisoformat(date_creation.replace("Z", "+00:00")).date() if date_creation else None
    except ValueError:
        jour = None
    url = (offre.get("origineOffre") or {}).get("urlOrigine") or (
        f"https://candidat.francetravail.fr/offres/recherche/detail/{offre.get('id')}"
    )
    return Signal(
        source="france_travail",
        type=type_signal,
        titre=f"Offre d'emploi : {offre.get('intitule', '')}",
        url=url,
        date=jour,
        texte=nettoyer_html(offre.get("description", "")),
        entreprise_nom=nom,
        code_postal=lieu.get("codePostal"),
        ville=lieu.get("libelle"),
        meta={
            "mot_cle": mot_cle,
            "intitule": offre.get("intitule"),
            "type_contrat": offre.get("typeContratLibelle"),
            "code_naf": offre.get("codeNAF"),
            "secteur": offre.get("secteurActiviteLibelle"),
            "tranche_effectif": offre.get("trancheEffectifEtab"),
            "site_web": entreprise.get("url"),
            "description_entreprise": entreprise.get("description"),
        },
    )


def collecter(session: requests.Session, config: dict, secrets) -> list[Signal]:
    reglages = config["sources"]["france_travail"]
    if not reglages.get("active", True):
        return []
    if not (secrets.france_travail_id and secrets.france_travail_secret):
        log.warning("France Travail ignoré : FRANCE_TRAVAIL_CLIENT_ID / SECRET absents du .env")
        return []

    jeton = _jeton(session, secrets.france_travail_id, secrets.france_travail_secret)
    entetes = {"Authorization": f"Bearer {jeton}", "Accept": "application/json"}
    groupes = [
        ("offre_emploi_ia", reglages.get("mots_cles_explicites", [])),
        ("offre_emploi_douleur", reglages.get("mots_cles_douleur", [])),
    ]
    signaux: list[Signal] = []
    vus: set[str] = set()
    for type_signal, mots_cles in groupes:
        for mot_cle in mots_cles:
            params = {
                "motsCles": mot_cle,
                "publieeDepuis": reglages.get("publiee_depuis_jours", 7),
                "range": f"0-{reglages.get('max_offres_par_mot_cle', 50) - 1}",
                "sort": 1,  # les plus récentes d'abord
            }
            try:
                reponse = session.get(URL_RECHERCHE, params=params, headers=entetes, timeout=DELAI)
                if reponse.status_code == 204:  # aucun résultat
                    continue
                reponse.raise_for_status()
            except requests.RequestException as erreur:
                log.warning("France Travail « %s » : %s", mot_cle, erreur)
                continue
            for offre in reponse.json().get("resultats", []):
                if offre.get("id") in vus:
                    continue
                vus.add(offre.get("id"))
                signal = _vers_signal(offre, type_signal, mot_cle)
                if signal:
                    signaux.append(signal)
    log.info("France Travail : %d offres nominatives", len(signaux))
    return signaux

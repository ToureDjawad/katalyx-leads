"""Identification légale des entreprises via l'API Recherche d'entreprises (data.gouv.fr).

Gratuite et sans clé. Elle renvoie le SIREN, l'activité (NAF), l'effectif, la catégorie,
l'adresse du siège, les dirigeants inscrits au RNE et le dernier chiffre d'affaires publié.
"""

from __future__ import annotations

import logging
import time

import requests

from ..http import DELAI
from ..modeles import Dirigeant, Entreprise
from ..texte import similarite

log = logging.getLogger(__name__)

URL = "https://recherche-entreprises.api.gouv.fr/search"
SEUIL_SIMILARITE = 0.72
PAUSE = 0.16  # l'API autorise 7 requêtes par seconde


def _vers_entreprise(r: dict) -> Entreprise:
    siege = r.get("siege") or {}
    finances = r.get("finances") or {}
    annee_ca = max(finances) if finances else None
    ca = (finances.get(annee_ca) or {}).get("ca") if annee_ca else None
    dirigeants = [
        Dirigeant(
            prenoms=d.get("prenoms") or "",
            nom=d.get("nom") or "",
            qualite=d.get("qualite") or "",
            annee_naissance=d.get("annee_de_naissance"),
        )
        for d in r.get("dirigeants") or []
        if d.get("type_dirigeant") == "personne physique" and d.get("nom")
    ]
    return Entreprise(
        siren=r["siren"],
        nom=r.get("nom_complet") or r.get("nom_raison_sociale") or "",
        naf=r.get("activite_principale"),
        libelle_naf=None,
        tranche_effectif=r.get("tranche_effectif_salarie") or siege.get("tranche_effectif_salarie"),
        categorie=r.get("categorie_entreprise"),
        nature_juridique=r.get("nature_juridique"),
        adresse=siege.get("adresse"),
        code_postal=siege.get("code_postal"),
        ville=siege.get("libelle_commune"),
        departement=siege.get("departement"),
        date_creation=r.get("date_creation"),
        chiffre_affaires=ca,
        annee_ca=annee_ca,
        dirigeants=dirigeants,
    )


def _noms_possibles(r: dict) -> list[str]:
    noms = [r.get("nom_complet") or "", r.get("nom_raison_sociale") or "", r.get("sigle") or ""]
    siege = r.get("siege") or {}
    noms += siege.get("liste_enseignes") or []
    if siege.get("nom_commercial"):
        noms.append(siege["nom_commercial"])
    return [n for n in noms if n]


class Sirene:
    def __init__(self, session: requests.Session):
        self.session = session
        self.cache: dict[str, Entreprise | None] = {}

    def _requete(self, params: dict) -> list[dict]:
        time.sleep(PAUSE)
        try:
            reponse = self.session.get(URL, params=params, timeout=DELAI)
            reponse.raise_for_status()
            return reponse.json().get("results", [])
        except requests.RequestException as erreur:
            log.warning("Recherche d'entreprises « %s » : %s", params.get("q"), erreur)
            return []

    def par_siren(self, siren_ou_siret: str) -> Entreprise | None:
        siren = siren_ou_siret[:9]
        if siren in self.cache:
            return self.cache[siren]
        resultats = self._requete({"q": siren, "per_page": 1})
        entreprise = _vers_entreprise(resultats[0]) if resultats and resultats[0]["siren"] == siren else None
        self.cache[siren] = entreprise
        return entreprise

    def par_nom(self, nom: str, code_postal: str | None = None) -> Entreprise | None:
        """Retrouve l'entreprise la plus probable ; None si le rapprochement est incertain."""
        cle = f"{nom}|{code_postal or ''}"
        if cle in self.cache:
            return self.cache[cle]
        params = {"q": nom, "per_page": 10, "etat_administratif": "A"}
        resultats = self._requete(params)
        meilleur, meilleur_score = None, 0.0
        for r in resultats:
            score = max(similarite(nom, n) for n in _noms_possibles(r)) if _noms_possibles(r) else 0
            siege = r.get("siege") or {}
            # Départage : même département que le lieu du signal.
            if code_postal and (siege.get("code_postal") or "")[:2] == code_postal[:2]:
                score += 0.05
            # Départage : on préfère la structure qui emploie (pas une holding vide).
            if (r.get("tranche_effectif_salarie") or "NN") not in ("NN", "00"):
                score += 0.03
            if score > meilleur_score:
                meilleur, meilleur_score = r, score
        entreprise = _vers_entreprise(meilleur) if meilleur and meilleur_score >= SEUIL_SIMILARITE else None
        if not entreprise:
            log.debug("Aucun rapprochement fiable pour « %s » (%.2f)", nom, meilleur_score)
        self.cache[cle] = entreprise
        return entreprise

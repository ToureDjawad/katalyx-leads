"""Petites fonctions de nettoyage de texte et de rapprochement de noms d'entreprise."""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher

FORMES_JURIDIQUES = {
    "sas", "sasu", "sa", "sarl", "eurl", "sci", "snc", "scop", "sca", "selarl", "selas",
    "groupe", "group", "france", "societe", "ste", "ets", "etablissements", "et", "cie",
    "the", "le", "la", "les", "de", "des", "du",
}


def sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )


def normaliser_nom(nom: str) -> str:
    """« Groupe Durand Industries SAS » -> « durand industries »."""
    nom = sans_accents(nom or "").lower()
    nom = re.sub(r"\(.*?\)", " ", nom)
    nom = re.sub(r"[^a-z0-9]+", " ", nom)
    mots = [m for m in nom.split() if m not in FORMES_JURIDIQUES]
    return " ".join(mots).strip()


def similarite(a: str, b: str) -> float:
    na, nb = normaliser_nom(a), normaliser_nom(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    # Bonus si tous les mots du nom recherché figurent dans le nom officiel.
    if set(na.split()) <= set(nb.split()):
        ratio = max(ratio, 0.9)
    return ratio


def nettoyer_html(texte: str) -> str:
    texte = re.sub(r"<[^>]+>", " ", texte or "")
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()

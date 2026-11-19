"""Actualités d'entreprises : levées de fonds, rachats, nouvelles usines, projets IA.

Sources : Google Actualités (RSS de recherche) et flux RSS de la presse business française.
Le nom de l'entreprise est extrait ensuite (par Claude, ou par règles en mode dégradé).
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

from ..http import DELAI
from ..modeles import Signal
from ..texte import nettoyer_html

log = logging.getLogger(__name__)

GOOGLE_NEWS = "https://news.google.com/rss/search?q={q}&hl=fr&gl=FR&ceid=FR:fr"


def _date(texte: str | None) -> date | None:
    try:
        return parsedate_to_datetime(texte).date() if texte else None
    except (TypeError, ValueError):
        return None


def lire_flux(contenu: bytes | str, origine: str) -> list[Signal]:
    signaux = []
    racine = ET.fromstring(contenu)
    for item in racine.iter("item"):
        titre = nettoyer_html(item.findtext("title") or "")
        if not titre:
            continue
        signaux.append(
            Signal(
                source="actualites",
                type="actualite",
                titre=titre,
                url=(item.findtext("link") or "").strip(),
                date=_date(item.findtext("pubDate")),
                texte=nettoyer_html(item.findtext("description") or "")[:1500],
                meta={"flux": origine},
            )
        )
    return signaux


def collecter(session: requests.Session, config: dict) -> list[Signal]:
    reglages = config["sources"]["actualites"]
    if not reglages.get("active", True):
        return []
    fraicheur = config["general"]["fraicheur_max_jours"]
    urls = [(GOOGLE_NEWS.format(q=quote_plus(r)), f"google:{r}") for r in reglages.get("requetes_google_news", [])]
    urls += [(u, u) for u in reglages.get("flux_rss", [])]

    signaux: list[Signal] = []
    titres_vus: set[str] = set()
    for url, origine in urls:
        try:
            reponse = session.get(url, timeout=DELAI)
            reponse.raise_for_status()
            articles = lire_flux(reponse.content, origine)
        except (requests.RequestException, ET.ParseError) as erreur:
            log.warning("Flux %s indisponible : %s", origine, erreur)
            continue
        for article in articles:
            cle = article.titre.lower()[:80]
            age = article.age_jours()
            if cle in titres_vus or (age is not None and age > fraicheur):
                continue
            titres_vus.add(cle)
            signaux.append(article)
    signaux.sort(key=lambda s: s.date or date.min, reverse=True)
    signaux = signaux[: reglages.get("max_articles", 120)]
    log.info("Actualités : %d articles récents", len(signaux))
    return signaux

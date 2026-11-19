"""Appels d'offres publics via l'API open data du BOAMP (DILA).

Un acheteur public qui publie un marché « intelligence artificielle » a un besoin explicite,
daté et budgété. Le canal est la réponse à l'appel d'offres, pas l'appel à froid.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date

import requests

from ..http import DELAI
from ..modeles import Signal

log = logging.getLogger(__name__)

URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"
CHAMPS = "idweb,objet,nomacheteur,dateparution,datelimitereponse,nature_libelle,code_departement,descripteur_libelle,url_avis,donnees"
RE_SIRET = re.compile(r'"(?:siret|codeIdentificationNational|cbc:ID)"\s*:\s*"(\d{14})"')
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
# Adresses des plateformes de publication, pas de l'acheteur.
PLATEFORMES = ("aws-france", "achatpublic", "marches-securises", "megalis", "maximilien", "e-marchespublics",
               "klekoon", "dematis", "marches-publics.info", "boamp", "francemarches", "omnikles", "atexo")
RE_CP = re.compile(r'"(?:cp|cbc:PostalZone)"\s*:\s*"(\d{5})"')
RE_VILLE = re.compile(r'"(?:ville|cbc:CityName)"\s*:\s*"([^"]+)"')


def _extraire(donnees: str | dict | None) -> dict:
    """Le champ « donnees » est un JSON imbriqué dont le schéma varie selon le formulaire."""
    brut = donnees if isinstance(donnees, str) else json.dumps(donnees or {}, ensure_ascii=False)
    siret = RE_SIRET.search(brut)
    emails = [
        e for e in RE_EMAIL.findall(brut)
        if not e.lower().endswith((".png", ".jpg")) and not any(p in e.lower() for p in PLATEFORMES)
    ]
    cp, ville = RE_CP.search(brut), RE_VILLE.search(brut)
    return {
        "siret": siret.group(1) if siret else None,
        "email_acheteur": emails[0] if emails else None,
        "code_postal": cp.group(1) if cp else None,
        "ville": ville.group(1) if ville else None,
    }


def collecter(session: requests.Session, config: dict) -> list[Signal]:
    reglages = config["sources"]["boamp"]
    if not reglages.get("active", True):
        return []
    fraicheur = config["general"]["fraicheur_max_jours"]
    delai = reglages.get("delai_reponse_min_jours", 5)
    conditions = " OR ".join(f'objet like "*{m}*"' for m in reglages["mots_cles"])
    where = (
        f"({conditions}) AND nature=\"APPEL_OFFRE\" "
        f"AND datelimitereponse > now(days={delai}) AND dateparution >= now(days=-{fraicheur})"
    )
    params = {"where": where, "select": CHAMPS, "order_by": "dateparution desc", "limit": 100}
    try:
        reponse = session.get(URL, params=params, timeout=DELAI)
        reponse.raise_for_status()
    except requests.RequestException as erreur:
        log.warning("BOAMP indisponible : %s", erreur)
        return []

    signaux = []
    for avis in reponse.json().get("results", []):
        infos = _extraire(avis.get("donnees"))
        parution = avis.get("dateparution")
        signaux.append(
            Signal(
                source="boamp",
                type="appel_offres",
                titre=f"Appel d'offres : {avis.get('objet', '').strip()}",
                url=avis.get("url_avis") or f"https://www.boamp.fr/pages/avis/?q=idweb:{avis.get('idweb')}",
                date=date.fromisoformat(parution) if parution else None,
                texte=(avis.get("objet") or "").strip(),
                entreprise_nom=avis.get("nomacheteur"),
                code_postal=infos["code_postal"],
                ville=infos["ville"],
                siret=infos["siret"],
                meta={
                    "date_limite": avis.get("datelimitereponse"),
                    "categorie": avis.get("descripteur_libelle"),
                    "email_acheteur": infos["email_acheteur"],
                    "idweb": avis.get("idweb"),
                },
            )
        )
    log.info("BOAMP : %d appels d'offres ouverts", len(signaux))
    return signaux

"""Choix du décideur et recherche de ses coordonnées professionnelles.

1. Le nom vient du registre officiel (RNE, via la Recherche d'entreprises) : gratuit et fiable.
2. L'e-mail et le téléphone professionnels viennent d'un service conforme RGPD, si une clé est fournie :
   Dropcontact (recommandé : société française, ne stocke pas de base de contacts) ou Lusha.
3. Sans clé, le lead garde le nom, la fonction, le standard via l'annuaire et un lien de recherche LinkedIn.

Base légale de la prospection B2B : intérêt légitime (RGPD art. 6.1.f). La personne est contactée
sur ses coordonnées professionnelles, pour une offre liée à sa fonction, avec possibilité de s'opposer.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus

import requests

from ..http import DELAI
from ..modeles import Contact, Dirigeant, Entreprise

log = logging.getLogger(__name__)

PRIORITE_QUALITES = [
    "président",
    "directeur général",
    "gérant",
    "directeur général délégué",
    "président du conseil",
    "président du directoire",
    "co-gérant",
]


def choisir_dirigeant(dirigeants: list[Dirigeant]) -> Dirigeant | None:
    """Le décideur d'un projet d'agents IA en PME est presque toujours le dirigeant opérationnel."""

    def rang(d: Dirigeant) -> int:
        q = (d.qualite or "").lower()
        for i, mot in enumerate(PRIORITE_QUALITES):
            if q.startswith(mot):
                return i
        return len(PRIORITE_QUALITES)

    candidats = [d for d in dirigeants if rang(d) < len(PRIORITE_QUALITES)]
    return min(candidats, key=rang) if candidats else (dirigeants[0] if dirigeants else None)


def lien_linkedin(nom: str, entreprise: str) -> str:
    return "https://www.linkedin.com/search/results/people/?keywords=" + quote_plus(f"{nom} {entreprise}")


class Dropcontact:
    URL = "https://api.dropcontact.com/v1/enrich/all"

    def __init__(self, session: requests.Session, cle: str):
        self.session, self.cle = session, cle

    def enrichir(self, prenom: str, nom: str, entreprise: Entreprise) -> dict:
        entetes = {"X-Access-Token": self.cle, "Content-Type": "application/json"}
        corps = {
            "data": [{
                "first_name": prenom,
                "last_name": nom,
                "company": entreprise.nom,
                "num_siren": entreprise.siren,
                **({"website": entreprise.site_web} if entreprise.site_web else {}),
            }],
            "siren": True,
            "language": "fr",
        }
        reponse = self.session.post(self.URL, json=corps, headers=entetes, timeout=DELAI)
        reponse.raise_for_status()
        identifiant = reponse.json().get("request_id")
        for _ in range(20):  # traitement asynchrone : jusqu'à ~5 minutes
            time.sleep(15)
            resultat = self.session.get(f"{self.URL}/{identifiant}", headers=entetes, timeout=DELAI).json()
            if resultat.get("success") and resultat.get("data"):
                c = resultat["data"][0]
                emails = [e.get("email") for e in c.get("email") or [] if "nominative" in (e.get("qualification") or "")]
                return {
                    "email": emails[0] if emails else None,
                    "telephone": c.get("mobile_phone") or c.get("phone"),
                    "linkedin": c.get("linkedin"),
                    "site_web": c.get("website"),
                }
        return {}


class Lusha:
    URL = "https://api.lusha.com/v2/person"

    def __init__(self, session: requests.Session, cle: str):
        self.session, self.cle = session, cle

    def enrichir(self, prenom: str, nom: str, entreprise: Entreprise) -> dict:
        params = {"firstName": prenom, "lastName": nom, "companyName": entreprise.nom}
        reponse = self.session.get(self.URL, params=params, headers={"api_key": self.cle}, timeout=DELAI)
        if reponse.status_code == 404:
            return {}
        reponse.raise_for_status()
        donnees = (reponse.json().get("contact") or {}).get("data") or reponse.json().get("data") or {}
        telephones = [t.get("number") for t in donnees.get("phoneNumbers") or [] if t.get("number")]
        emails = [e.get("email") for e in donnees.get("emailAddresses") or [] if e.get("email")]
        return {
            "email": emails[0] if emails else None,
            "telephone": telephones[0] if telephones else None,
            "linkedin": (donnees.get("socialLinks") or {}).get("linkedin"),
        }


def trouver_contact(session: requests.Session, secrets, entreprise: Entreprise, signal_meta: dict | None = None) -> Contact | None:
    dirigeant = choisir_dirigeant(entreprise.dirigeants)
    if not dirigeant:
        # Acheteur public (BOAMP) : le contact est celui de l'avis.
        email = (signal_meta or {}).get("email_acheteur")
        if email:
            return Contact(nom_complet="Service achats", fonction="Acheteur public (avis BOAMP)", source="avis BOAMP", email=email)
        return None

    contact = Contact(
        nom_complet=dirigeant.nom_complet,
        fonction=dirigeant.qualite,
        source="registre (RNE)",
        linkedin=lien_linkedin(dirigeant.nom_complet, entreprise.nom),
    )
    fournisseurs = []
    if secrets.dropcontact:
        fournisseurs.append(("dropcontact", Dropcontact(session, secrets.dropcontact)))
    if secrets.lusha:
        fournisseurs.append(("lusha", Lusha(session, secrets.lusha)))
    for nom_fournisseur, fournisseur in fournisseurs:
        try:
            infos = fournisseur.enrichir(dirigeant.prenom, dirigeant.nom.title(), entreprise)
        except requests.RequestException as erreur:
            log.warning("%s : %s", nom_fournisseur, erreur)
            continue
        if infos.get("site_web") and not entreprise.site_web:
            entreprise.site_web = infos["site_web"]
        if infos.get("email") or infos.get("telephone"):
            contact.email = contact.email or infos.get("email")
            contact.telephone = contact.telephone or infos.get("telephone")
            contact.linkedin = infos.get("linkedin") or contact.linkedin
            contact.source = f"registre (RNE) + {nom_fournisseur}"
        if contact.email and contact.telephone:
            break
    return contact

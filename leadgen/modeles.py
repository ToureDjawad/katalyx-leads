"""Structures de données manipulées par le pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass
class Signal:
    """Un fait observé publiquement qui laisse penser qu'une entreprise a un besoin."""

    source: str                 # france_travail | boamp | actualites
    type: str                   # offre_emploi_ia | offre_emploi_douleur | appel_offres | actualite
    titre: str
    url: str
    date: date | None
    texte: str = ""
    entreprise_nom: str | None = None
    code_postal: str | None = None
    ville: str | None = None
    siret: str | None = None
    meta: dict = field(default_factory=dict)

    def age_jours(self, aujourdhui: date | None = None) -> int | None:
        if not self.date:
            return None
        return ((aujourdhui or date.today()) - self.date).days

    def resume(self, longueur: int = 1200) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat() if self.date else None
        d["texte"] = (self.texte or "")[:longueur]
        return d


@dataclass
class Dirigeant:
    prenoms: str
    nom: str
    qualite: str
    annee_naissance: str | None = None

    @property
    def prenom(self) -> str:
        return (self.prenoms or "").split(" ")[0].title()

    @property
    def nom_complet(self) -> str:
        return f"{self.prenom} {self.nom.title()}".strip()


@dataclass
class Entreprise:
    siren: str
    nom: str
    naf: str | None
    libelle_naf: str | None
    tranche_effectif: str | None
    categorie: str | None          # PME | ETI | GE
    nature_juridique: str | None
    adresse: str | None
    code_postal: str | None
    ville: str | None
    departement: str | None
    date_creation: str | None
    chiffre_affaires: float | None = None
    annee_ca: str | None = None
    dirigeants: list[Dirigeant] = field(default_factory=list)
    site_web: str | None = None

    @property
    def lien_annuaire(self) -> str:
        return f"https://annuaire-entreprises.data.gouv.fr/entreprise/{self.siren}"


@dataclass
class Contact:
    nom_complet: str
    fonction: str
    source: str                     # registre (RNE) | dropcontact | lusha | avis BOAMP
    email: str | None = None
    telephone: str | None = None
    linkedin: str | None = None


@dataclass
class Candidat:
    """Une entreprise et tous les signaux qui la concernent."""

    cle: str
    nom_signal: str
    signaux: list[Signal] = field(default_factory=list)
    entreprise: Entreprise | None = None
    pre_score: float = 0.0
    evaluation: dict | None = None
    contact: Contact | None = None

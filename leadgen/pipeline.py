"""Orchestration : collecte -> extraction -> identification -> filtres -> pré-tri -> scoring -> contacts -> export."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date
from pathlib import Path

from .config import RACINE, Secrets
from .enrichissement.contacts import trouver_contact
from .enrichissement.sirene import Sirene
from .export import exporter
from .filtres import raison_exclusion
from .historique import Historique
from .http import nouvelle_session
from .ia.client import ClientIA
from .ia.extraction import extraire
from .ia.scoring import evaluer_heuristique, evaluer_ia, pre_score
from .modeles import Candidat, Signal
from .sources import actualites, boamp, france_travail
from .texte import normaliser_nom

log = logging.getLogger("leadgen")
ORDRE_TEMPERATURE = {"chaud": 0, "tiède": 1, "froid": 2}


def regrouper(signaux: list[Signal]) -> list[Candidat]:
    groupes: dict[str, Candidat] = {}
    for s in signaux:
        cle = s.siret[:9] if s.siret else normaliser_nom(s.entreprise_nom or "")
        if not cle:
            continue
        groupes.setdefault(cle, Candidat(cle=cle, nom_signal=s.entreprise_nom or "")).signaux.append(s)
    return list(groupes.values())


def identifier(candidats: list[Candidat], sirene: Sirene) -> list[Candidat]:
    """Rattache chaque groupe à un SIREN, puis fusionne les groupes qui désignent la même entreprise."""
    par_siren: dict[str, Candidat] = {}
    for c in candidats:
        s = c.signaux[0]
        c.entreprise = sirene.par_siren(s.siret) if s.siret else sirene.par_nom(c.nom_signal, s.code_postal)
        if not c.entreprise:
            continue
        site = next((x.meta.get("site_web") for x in c.signaux if x.meta.get("site_web")), None)
        c.entreprise.site_web = c.entreprise.site_web or site
        if c.entreprise.siren in par_siren:
            par_siren[c.entreprise.siren].signaux += c.signaux
        else:
            par_siren[c.entreprise.siren] = c
    return list(par_siren.values())


def selectionner(evalues: list[Candidat], nombre: int, max_boamp: int) -> list[Candidat]:
    evalues.sort(key=lambda c: (ORDRE_TEMPERATURE[c.evaluation["temperature"]], -c.evaluation["score"]))
    retenus, nb_boamp = [], 0
    for c in evalues:
        public = all(s.source == "boamp" for s in c.signaux)
        if public and nb_boamp >= max_boamp:
            continue
        nb_boamp += public
        retenus.append(c)
        if len(retenus) == nombre:
            break
    return retenus


def executer(config: dict, nombre: int | None = None, essai: bool = False, sans_ia: bool = False) -> dict:
    general = config["general"]
    nombre = nombre or general["nombre_leads"]
    secrets = Secrets.depuis_env()
    session = nouvelle_session()
    aujourdhui = date.today()
    ia = None if sans_ia or not secrets.anthropic else ClientIA(secrets.anthropic, config["ia"]["modele"])
    if not ia:
        log.warning("Scoring en mode dégradé (règles) : ajoutez ANTHROPIC_API_KEY pour la qualification par Claude.")
    historique = Historique(RACINE / general["fichier_historique"])

    # 1. Collecte des signaux
    log.info("Étape 1/6 : collecte des signaux")
    offres = france_travail.collecter(session, config, secrets)
    appels = boamp.collecter(session, config)
    articles = actualites.collecter(session, config)

    # 2. Rattachement des articles à une entreprise
    log.info("Étape 2/6 : extraction des entreprises citées dans la presse")
    articles = extraire(articles, ia, config["ia"]["effort_extraction"])
    signaux = offres + appels + articles

    # 3. Identification au registre
    log.info("Étape 3/6 : identification de %d signaux au registre (SIREN)", len(signaux))
    candidats = identifier(regrouper(signaux), Sirene(session))

    # 4. Filtres et pré-tri
    log.info("Étape 4/6 : filtres et pré-tri de %d entreprises", len(candidats))
    exclusions = Counter()
    retenus = []
    for c in candidats:
        raison = raison_exclusion(c, config, historique)
        if raison:
            exclusions[raison.split(" (")[0]] += 1
            continue
        c.pre_score = pre_score(c, config, aujourdhui)
        retenus.append(c)
    retenus.sort(key=lambda c: c.pre_score, reverse=True)
    a_evaluer = retenus[: general["candidats_max_scoring"]]

    # 5. Qualification
    log.info("Étape 5/6 : qualification de %d entreprises (%s)", len(a_evaluer), "Claude" if ia else "règles")
    evalues = []
    for i, c in enumerate(a_evaluer, 1):
        c.evaluation = (evaluer_ia(c, ia, config["ia"]["effort_scoring"], aujourdhui) if ia else None) \
            or evaluer_heuristique(c, aujourdhui)
        log.info("  [%d/%d] %s : %s %s", i, len(a_evaluer), c.entreprise.nom,
                 c.evaluation["temperature"] if c.evaluation["eligible"] else "écarté", c.evaluation["score"])
        if c.evaluation["eligible"]:
            evalues.append(c)
        else:
            exclusions["écarté par Claude"] += 1
    leads = selectionner(evalues, nombre, config["sources"]["boamp"].get("max_leads_boamp", 2))

    # 6. Décideurs et export
    log.info("Étape 6/6 : décideurs et export de %d leads", len(leads))
    for c in leads:
        meta = next((s.meta for s in c.signaux if s.source == "boamp"), None)
        c.contact = trouver_contact(session, secrets, c.entreprise, meta)
        historique.ajouter(c.entreprise.siren, c.entreprise.nom, c.evaluation["temperature"])

    temperatures = Counter(c.evaluation["temperature"] for c in leads)
    statistiques = {
        "signaux exploités": len(signaux),
        "offres d'emploi": len(offres),
        "appels d'offres": len(appels),
        "articles rattachés": len(articles),
        "entreprises identifiées": len(candidats),
        "entreprises qualifiées": len(a_evaluer),
        "leads livrés": len(leads),
        "chauds": temperatures.get("chaud", 0),
        "tièdes": temperatures.get("tiède", 0),
        "froids": temperatures.get("froid", 0),
        "scoring": "Claude " + config["ia"]["modele"] if ia else "règles (mode dégradé)",
    }
    chemins = exporter(leads, RACINE / general["dossier_sortie"], statistiques)
    if not essai:
        historique.enregistrer()
    if len(leads) < nombre:
        log.warning("Seulement %d leads trouvés sur %d demandés : élargissez les sources ou la fraîcheur.", len(leads), nombre)
    if ia:
        log.info("Consommation Claude : %d jetons en entrée, %d en sortie", ia.jetons_entree, ia.jetons_sortie)
    return {"leads": leads, "fichiers": chemins, "statistiques": statistiques, "exclusions": dict(exclusions)}


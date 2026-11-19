"""Règles d'exclusion déterministes, appliquées avant tout appel payant."""

from __future__ import annotations

from .modeles import Candidat

ORDRE_TRANCHES = ["NN", "00", "01", "02", "03", "11", "12", "21", "22", "31", "32", "41", "42", "51", "52", "53"]


def raison_exclusion(candidat: Candidat, config: dict, historique) -> str | None:
    e = candidat.entreprise
    if not e:
        return "entreprise introuvable au registre"
    if historique.contient(e.siren):
        return "déjà livrée lors d'une exécution précédente"
    public = all(s.source == "boamp" for s in candidat.signaux)
    naf = e.naf or ""
    for prefixe in config["cible"]["naf_exclus"]:
        if naf.startswith(prefixe) and not (public and prefixe == "84"):
            return f"activité exclue (NAF {naf})"
    if public:
        return None  # un acheteur public n'a pas de tranche d'effectif pertinente
    tranche = e.tranche_effectif or "NN"
    mini, maxi = config["cible"]["tranche_effectif_min"], config["cible"]["tranche_effectif_max"]
    if tranche != "NN":
        rang = ORDRE_TRANCHES.index(tranche) if tranche in ORDRE_TRANCHES else 0
        if rang < ORDRE_TRANCHES.index(mini):
            return f"trop petite (tranche INSEE {tranche})"
        if rang > ORDRE_TRANCHES.index(maxi):
            return f"trop grande (tranche INSEE {tranche})"
    elif e.categorie == "GE":
        return "grande entreprise"
    else:
        # Effectif non diffusé : on exige une preuve d'activité réelle, sinon risque d'homonyme ou de coquille vide.
        recrute = any(s.source == "france_travail" for s in candidat.signaux)
        if not recrute and (e.chiffre_affaires or 0) < 1_000_000:
            return "effectif non diffusé et activité non prouvée"
    return None

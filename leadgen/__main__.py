"""Point d'entrée : python -m leadgen [--nombre 10] [--essai] [--sans-ia]"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import Secrets, charger_config
from .pipeline import executer


def main() -> int:
    parser = argparse.ArgumentParser(prog="leadgen", description="Génère des leads B2B qualifiés pour l'offre Agents IA de Katalyx.")
    parser.add_argument("--nombre", type=int, help="nombre de leads à livrer (défaut : config.toml)")
    parser.add_argument("--config", help="chemin d'un autre fichier de configuration")
    parser.add_argument("--essai", action="store_true", help="n'enregistre pas les leads dans l'historique")
    parser.add_argument("--sans-ia", action="store_true", help="force le scoring par règles, sans appel à Claude")
    parser.add_argument("--verifier", action="store_true", help="affiche les clés configurées puis quitte")
    parser.add_argument("-v", "--verbeux", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbeux else logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    for bruyant in ("urllib3", "httpx", "anthropic", "httpcore"):
        logging.getLogger(bruyant).setLevel(logging.WARNING)

    config = charger_config(args.config)
    if args.verifier:
        for nom, present in Secrets.depuis_env().etat().items():
            print(f"{'✓' if present else '✗'} {nom}")
        return 0

    resultat = executer(config, nombre=args.nombre, essai=args.essai, sans_ia=args.sans_ia)
    print("\nRésultat :")
    for cle, valeur in resultat["statistiques"].items():
        print(f"  {cle} : {valeur}")
    if resultat["exclusions"]:
        print("Exclusions :", ", ".join(f"{k} ({v})" for k, v in resultat["exclusions"].items()))
    for nature, chemin in resultat["fichiers"].items():
        print(f"  {nature.upper()} : {chemin}")
    return 0 if resultat["leads"] else 1


if __name__ == "__main__":
    sys.exit(main())

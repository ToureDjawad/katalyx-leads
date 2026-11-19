# Machine à leads Katalyx

Ce système génère, à chaque exécution, **10 nouveaux leads B2B qualifiés** pour l'offre **Agents IA et Audit IA** de [Katalyx](https://katalyx.fr/agents-ia).

Il repère des signaux publics et récents qui montrent un besoin : offres d'emploi, appels d'offres et actualités d'entreprise. Il identifie ensuite l'entreprise au registre officiel et trouve son dirigeant. Claude qualifie chaque lead en chaud, tiède ou froid, avec une justification et une accroche d'appel. Le résultat est un fichier prêt à être appelé.

La démarche complète (choix de l'offre, des sources, du scoring, limites et RGPD) est décrite dans **[DEMARCHE.md](DEMARCHE.md)**.

```
Signaux publics ──► Entreprise au registre ──► Filtres ──► Qualification Claude ──► Décideur ──► CSV / fiches d'appel
(emploi, AO, presse)   (SIREN, effectif, NAF)   (règles)    (chaud/tiède/froid)     (RNE + RGPD)
```

## Installation

Python 3.11 ou plus récent.

```bash
git clone https://github.com/ToureDjawad/katalyx-leads.git
cd katalyx-leads
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # puis remplir les clés
```

## Clés à fournir (fichier `.env`)

| Variable | Obligatoire | Coût | Rôle |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Oui, pour la qualité | Environ 2 à 4 $ par exécution (40 leads qualifiés avec Claude Opus 5.5) | Extraction des entreprises citées dans la presse et qualification des leads par Claude. Sans clé, un mode dégradé par règles tourne quand même. |
| `FRANCE_TRAVAIL_CLIENT_ID` et `FRANCE_TRAVAIL_CLIENT_SECRET` | Fortement recommandé | Gratuit | Offres d'emploi, la source des signaux les plus chauds. Créez une application sur [francetravail.io](https://francetravail.io) et abonnez-la à l'API « Offres d'emploi v2 ». |
| `DROPCONTACT_API_KEY` | Optionnel | Payant, au crédit | E-mail et téléphone professionnels du dirigeant. Conforme RGPD. |
| `LUSHA_API_KEY` | Optionnel | Payant, au crédit | Alternative ou complément pour le téléphone direct. |

Les sources BOAMP, Recherche d'entreprises (Sirene et RNE), Google Actualités et les flux RSS sont publiques et ne demandent aucune clé.

Pour vérifier la configuration :

```bash
python -m leadgen --verifier
```

## Utilisation

```bash
python -m leadgen                 # 10 nouveaux leads, enregistrés dans l'historique
python -m leadgen --nombre 20     # un autre volume
python -m leadgen --essai         # n'enregistre pas l'historique (pour tester)
python -m leadgen --sans-ia       # force le mode dégradé, sans appel à Claude
```

Une exécution dure de 3 à 8 minutes. Les leads déjà livrés sont mémorisés dans `data/historique.json` : la relance suivante en produit 10 **nouveaux**.

## Résultats

Dans `sortie/`, à chaque exécution :

- `leads_<date>.csv` : une ligne par lead, séparateur point-virgule, qui s'ouvre directement dans Excel ou Google Sheets (Fichier, puis Importer).
- `leads_<date>.md` : des fiches d'appel lisibles, avec l'entreprise, le décideur, le signal, l'accroche et les questions de découverte.
- `leads_<date>.json` : les mêmes données, avec les statistiques de l'exécution.

Principales colonnes : `temperature`, `score`, `confiance`, `entreprise`, `siren`, `decideur`, `fonction_a_appeler`, `email`, `telephone`, `linkedin`, `signal_cle`, `date_signal`, `url_signal`, `cas_usage`, `accroche_appel`, `questions_decouverte`, `justification`.

## Réglages

Tout se règle dans [`config.toml`](config.toml), sans toucher au code : mots-clés des offres d'emploi, requêtes de presse, fraîcheur maximale, taille d'entreprise, secteurs prioritaires et exclus, départements prioritaires, modèle et effort de Claude.

Les prompts sont dans [`prompts/`](prompts) :

- `offre_katalyx.md` : l'offre, le client idéal et les exclusions.
- `scoring.md` : la grille de qualification.
- `extraction.md` : la lecture des articles de presse.

## Tests

```bash
python -m pytest
```

Les tests tournent hors ligne, sans clé.

## Structure

```
leadgen/
  sources/          france_travail.py · boamp.py · actualites.py
  enrichissement/   sirene.py (registre) · contacts.py (décideur, Dropcontact, Lusha)
  ia/               client.py · extraction.py · scoring.py
  filtres.py        exclusions déterministes
  pipeline.py       orchestration des 6 étapes
  export.py         CSV, JSON, Markdown
  historique.py     déduplication entre exécutions
prompts/            prompts en français
config.toml         réglages
```

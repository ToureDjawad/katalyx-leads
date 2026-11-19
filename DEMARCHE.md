# Démarche : une machine à leads pour les Agents IA de Katalyx

## 1. Le problème

Katalyx veut appeler des entreprises qui ont **aujourd'hui** un besoin que ses agents IA résolvent. Une liste de PME du bon secteur ne suffit pas : sans raison d'appeler maintenant, l'appel est froid et le taux de conversion s'effondre.

Le système part donc du **signal**, un fait public, daté et vérifiable, qui montre un besoin. Il remonte ensuite à l'entreprise, puis au décideur. Chaque lead livré se justifie par une phrase que le commercial peut dire au téléphone : « J'ai vu que vous recrutiez un deviseur le 17 novembre… ».

## 2. Le choix de l'offre : Agents IA et Audit IA

| Critère | Agents IA et Audit IA | Formation IA | Développement sur mesure |
|---|---|---|---|
| Valeur d'un client | Élevée (audit, prototype, production, maintenance) | Moyenne (650 € à quelques jours) | Élevée mais cycle long |
| Signaux publics détectables | Nombreux (recrutements sur des process répétitifs, projets IA, AO) | Peu spécifiques | Rares |
| Différenciation Katalyx | Forte : « des développeurs qui forment » | Concurrence très dense | Concurrence des ESN |
| Porte d'entrée | Audit d'une demi-journée, facile à vendre au téléphone | Bonne | Faible |

L'audit à 800 € HT par jour est une première vente à faible risque pour le client. Il mène ensuite naturellement au prototype et à la mise en production. C'est la meilleure offre pour un appel sortant.

## 3. Le client idéal

Le profil est tiré du site de Katalyx :

- **Taille** : PME ou ETI de 10 à 2 000 salariés. Le dirigeant décide vite et le budget existe.
- **Secteurs** : industrie, BTP, agroalimentaire, aéronautique et défense, santé, services professionnels, SaaS non spécialisés en IA.
- **Douleur** : des process répétitifs comme les devis, l'ADV, la qualité, le reporting et la documentation.
- **Bonus géographique** : la région Sud et l'Occitanie, accessibles depuis Aix-en-Provence.
- **Exclusions** : les éditeurs de logiciels et les ESN (concurrents), l'intérim et le recrutement, les grands groupes, les entreprises sans salarié.

## 4. Les signaux et leurs sources

| Signal | Source | Pourquoi c'est un signal | Température typique |
|---|---|---|---|
| Recrutement « chef de projet IA », « automatisation », « IA générative » dans une entreprise non tech | API France Travail (officielle, gratuite) | Besoin explicite, daté, avec un budget (un salaire) | Chaud |
| Recrutement d'un deviseur, d'un chiffreur, d'une assistante ADV ou d'un assistant qualité | API France Travail | Un process répétitif qui grossit : exactement ce que font les agents Devis, Administratif et Qualité. Un agent coûte moins cher qu'un poste. | Tiède à chaud |
| Appel d'offres public sur l'IA, un chatbot ou l'automatisation | API open data du BOAMP | Besoin explicite, budgété, avec une date limite | Chaud (canal : réponse à l'AO) |
| Levée de fonds, rachat, nouvelle usine, projet IA annoncé | Google Actualités et presse business (RSS) | La croissance fait exploser la charge administrative ; le dirigeant cherche à structurer | Tiède |

Pourquoi ces sources plutôt que du scraping de LinkedIn ou de Welcome to the Jungle : elles sont **officielles ou ouvertes, stables et légales**. Le système est ainsi relançable sans risque de blocage et sans enfreindre des conditions d'utilisation.

## 5. Le pipeline en six étapes

1. **Collecte.** Les offres d'emploi des 7 derniers jours, les appels d'offres ouverts et les articles des 30 derniers jours.
2. **Extraction.** Claude lit les titres et extraits de presse. Il en tire le nom de l'entreprise française concernée et la nature de l'événement, et il écarte les tendances, les tribunes et les entreprises dont le métier est l'IA.
3. **Identification.** Chaque nom est rapproché de la base Recherche d'entreprises (INSEE et RNE) : SIREN, activité NAF, effectif, chiffre d'affaires, siège et dirigeants. Le rapprochement est flou mais strict (seuil de similarité, départage par département et par effectif). Un nom ambigu est abandonné plutôt que mal attribué.
4. **Filtres déterministes.** Sont exclus les leads déjà livrés, les activités hors cible, les entreprises trop petites ou trop grandes, et les structures sans preuve d'activité. Un **pré-score** gratuit (force du signal, fraîcheur, secteur, taille, région) classe ensuite les candidats et seuls les 40 meilleurs vont à Claude.
5. **Qualification par Claude.** Pour chaque entreprise, Claude reçoit sa fiche légale et ses signaux. Il rend une évaluation **structurée et validée par schéma** : éligibilité, température, score sur 100, signal clé, justification, agents Katalyx à proposer, fonction à appeler, accroche d'appel, trois questions de découverte et niveau de confiance.
6. **Décideur et export.** Le nom du dirigeant vient du registre officiel. L'e-mail et le téléphone professionnels viennent de Dropcontact ou de Lusha si une clé est fournie. Les 10 meilleurs leads sont exportés en CSV, en JSON et en fiches d'appel, puis mémorisés pour ne jamais être relivrés.

## 6. La grille de qualification

La température dépend du **signal le plus fort**, pas du volume de signaux.

- **Chaud** : un besoin explicite d'IA ou d'automatisation de moins de 21 jours, couvert par l'offre. Score de 70 ou plus.
- **Tiède** : un besoin probable mais implicite (recrutement sur un process répétitif, croissance forte), ou un besoin explicite plus ancien.
- **Froid** : l'entreprise est dans la cible, mais rien ne dit qu'elle a un besoin. Score de 45 ou moins.

Le score sur 100 se répartit ainsi :

| Composante | Points |
|---|---|
| Force du signal | 40 |
| Adéquation avec la cible (secteur, taille, maturité) | 25 |
| Fraîcheur | 15 |
| Accessibilité du décideur | 10 |
| Proximité d'Aix-en-Provence | 10 |

Claude doit aussi écarter les homonymes et les signaux qui concernent une autre entreprise (le fonds, le client, l'acheteur). Il distingue dans sa justification ce qui est observé de ce qui est déduit. Le classement final trie par température, puis par score. Les acheteurs publics sont plafonnés à deux par livraison, car leur canal est la réponse à l'appel d'offres, pas l'appel téléphonique.

## 7. Pourquoi ce lead est appelable

Chaque ligne du fichier donne au commercial :

- **qui appeler** : le nom du dirigeant au registre, sa fonction et la fonction à viser ;
- **pourquoi maintenant** : le signal, sa date et le lien vers la source, à vérifier en 10 secondes ;
- **quoi proposer** : l'agent Katalyx correspondant et l'audit ;
- **quoi dire** : une accroche de deux ou trois phrases et trois questions de découverte.

## 8. Relance et industrialisation

- `python -m leadgen` produit 10 nouveaux leads. L'historique garantit qu'aucune entreprise n'est livrée deux fois.
- Il est planifiable chaque lundi avec cron ou GitHub Actions. Le coût est d'environ 2 à 4 $ de Claude par exécution, plus les crédits d'enrichissement de contacts.
- Tout est réglable dans `config.toml` (mots-clés, secteurs, région, fraîcheur), et les prompts sont des fichiers texte modifiables par l'équipe commerciale.
- Sans clé Claude, un mode dégradé par règles tourne quand même, et il est signalé dans chaque ligne exportée.

Pistes d'amélioration :

- Ajouter des sources : Welcome to the Jungle et Indeed via un partenaire de données, BODACC pour les créations d'établissements et les cessions, et les profils LinkedIn des dirigeants via un outil autorisé.
- Relier le résultat des appels au score : un feedback « RDV obtenu / pas intéressé » pour recalibrer la grille.
- Pousser les leads directement dans le CRM de Katalyx (HubSpot ou Pipedrive) au lieu d'un CSV.

## 9. RGPD et conformité

- La **base légale** est l'intérêt légitime (art. 6.1.f du RGPD), admis par la CNIL pour la prospection B2B. Les personnes sont contactées sur leurs coordonnées professionnelles, pour une offre en rapport avec leur fonction.
- **Minimisation** : seuls le nom, la fonction et les coordonnées professionnelles sont gardés. Aucune donnée personnelle n'est extraite des offres d'emploi.
- Les **sources** sont publiques et officielles (INSEE, RNE, BOAMP, France Travail). Les enrichisseurs choisis sont conformes RGPD ; Dropcontact, français, ne stocke pas de base de contacts.
- **Information et opposition** : lors du premier contact, Katalyx indique la source des données et permet de s'opposer. L'historique sert aussi de liste d'exclusion.

## 10. Limites connues

- Les offres d'emploi sont la source la plus chaude. Sans clé France Travail, les leads reposent sur la presse et le BOAMP, et sont surtout tièdes.
- La presse ne donne souvent qu'un titre et un extrait. Claude qualifie avec prudence et le niveau de confiance le signale.
- Le rapprochement par nom peut rater une entreprise à l'enseigne différente de sa raison sociale. Le système préfère alors l'abandonner plutôt que de livrer la mauvaise entreprise.
- Les coordonnées directes dépendent d'un enrichisseur payant. Sans lui, le lead contient le nom du dirigeant, la fiche officielle et un lien de recherche LinkedIn.

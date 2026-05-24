# BTS Dashboard — Tunisie Telecom

## Présentation

Ce projet est une solution d'optimisation énergétique des stations de base BTS de Tunisie Telecom. Il combine trois notebooks de data science et une application Streamlit qui présente :

- la prédiction de consommation énergétique,
- la détection d'anomalies,
- l'optimisation décisionnelle et RL,
- une interface de supervision réseau.

## Notebooks

### Notebook 1 — Apprentissage Supervisé
- Objectif : prédire la consommation horaire des stations.
- Étapes :
  - compréhension métier et chargement des données
  - nettoyage et correction des anomalies
  - feature engineering et EDA
  - comparaison de 7 modèles supervisés
  - validation croisée temporelle
  - évaluation finale et interprétabilité SHAP
- Sorties clés :
  - `best_model.joblib`
  - `encodeurs.joblib`
  - `quantile_models.joblib`
  - `df_train_processed.parquet`
  - `df_test_processed.parquet`
  - `df_full_processed.parquet`
  - `resultats_modeles.json`

### Notebook 2 — Détection d'Anomalies (Non Supervisé)
- Prérequis : sorties NB1 (`df_full_processed.parquet`, `config.joblib`).
- Objectif : détecter les anomalies de consommation et qualifier les incidents QoS.
- Étapes :
  - création de features d'anomalie et standardisation
  - estimation data-driven de la contamination
  - entraînement de 7 détecteurs non supervisés
  - calibration des scores et consensus des moteurs
  - évaluation qualitative et visualisations
- Sorties clés :
  - `modeles_anomalie.joblib`
  - `autoencoder.keras` (si TensorFlow)
  - `performance_qualitative_modeles.csv`
  - scores et données préparées pour NB3

### Notebook 3 — Système de Décision & Optimisation Énergétique
- Prérequis : exécutés NB1 et NB2.
- Objectif : définir un moteur de décision et optimiser l'usage électrique via des règles et du Reinforcement Learning.
- Contenu :
  - chargement des artefacts NB1/NB2
  - moteur de décision multi-mode : ECO / NORMAL / ATTENTION / CRITIQUE
  - garde-fou QoS
  - 5 stratégies expertes d'optimisation
  - environnement de simulation BTS
  - 7 agents RL entraînés et comparés
  - visualisations des économies et des profils horaires
  - pipeline d'inférence temps réel
- Sorties clés :
  - `pipeline_inference.joblib`
  - `tableau_de_bord_complet.png`
  - artefacts RL

## Dashboard Streamlit

L'application principale se lance depuis `app.py`.

### Fonctionnalités
- Authentification et gestion des permissions (RLS par station pour les ingénieurs)
- Chargement des artefacts NB1/NB2/NB3
- Navigation :
  - **Admin** : Accueil, Carte, Prédiction (NB1), Anomalies (NB2), Optimisation (NB3), Simulation temps réel, Configuration
  - **Ingénieur réseau** : mêmes pages opérationnelles (stations assignées uniquement, sans résultats ML), plus Simulation
- **Configuration** (admin) : gestion des stations, utilisateurs, import de dataset

### Pages et notebooks
| Page | Notebook | Contenu principal |
|------|----------|-------------------|
| Accueil | — | 4 KPIs, répartition des modes, top 5 stations critiques |
| Carte | — | Carte Mapbox (criticité), filtres sidebar, comparaison gouvernorats |
| Prédiction | NB1 | Réel vs prédit, bande Q10/Q90, R² |
| Anomalies | NB2 | Scatter score × heure, stations prioritaires |
| Optimisation | NB3 | Règles vs RL, courbe d'apprentissage, économies CO₂ |
| Simulation | NB3 | Replay horaire en temps réel |
| Configuration | — | Stations, utilisateurs, upload dataset |

### Structure du code
- `app.py` : point d'entrée Streamlit
- `ui/dashboard.py` : router des pages
- `views/` : pages du tableau de bord
- `services/data_service.py` : accès aux données et calcul des KPI
- `ui/components.py`, `ui/layout.py`, `ui/utils.py` : composants et utilitaires
- `security/middleware.py` : contrôle d'accès

## Installation rapide

1. Créer un environnement Python.
2. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Lancer l'application :
   ```bash
   python app.py
   ```

## Données

- Les données principales sont stockées dans `VF/tunisie_telecom_dataset.csv`.
- Les notebooks produisent des artefacts dans les dossiers `outputs/` et `VF/*/output`.

## Notes

- Le dashboard repose sur des artefacts générés par les notebooks.
- NB1 prépare les prévisions, NB2 prépare la détection d'anomalies, NB3 prépare l'optimisation décisionnelle.
- La vue réseau et les KPIs utilisent à la fois la consommation réelle, les scores QoS et les scores d'anomalie.

### Simulation ML sur Streamlit Cloud

La page **Simulation** charge les modèles depuis [Hugging Face `molkab/dashboard`](https://huggingface.co/molkab/dashboard) (`pipeline_inference.joblib`, `config.joblib`, etc.). Si vous voyez *profil historique* :

1. Dans **Streamlit Cloud → Settings → Secrets**, assurez-vous d’avoir `USE_HF_HUB=True` (ou laissez la valeur par défaut).
2. Au premier lancement, le téléchargement peut prendre 1–2 minutes (cache `.cache/huggingface`).
3. Pour un dépôt privé, ajoutez `HF_TOKEN` dans les secrets.
4. En local sans réseau, placez les `.joblib` dans `VF/NB3/output/` ou `VF/NB1/NB1-P/output/`.

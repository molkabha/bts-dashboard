# BTS Energy Management System — Tunisie Telecom

Ce projet est un système complet et d'optimisation énergétique pour les stations de base (BTS) de Tunisie Telecom. Il combine des modèles d'intelligence artificielle (LightGBM), de la détection d'anomalies multi-modèles (Isolation Forest, Autoencoder, etc.), et de l'apprentissage par renforcement (Q-Learning, SARSA) avec une interface utilisateur interactive et professionnelle conçue avec Streamlit.

---

## Architecture Fonctionnelle et Modulaire

L'application suit une structure moderne en 8 vues (pages) pour centraliser la supervision réseau tout en respectant un haut standard esthétique professionnel (charte TT, mode présentation PFE, design unifié sans emojis).

### Couches de l'Application

1. **Interface Utilisateur (UI)** :
   - `app.py` : Point d'entrée de l'application. Initialise la configuration et route vers le dashboard.
   - `ui/dashboard.py` : Routeur principal. Gère le contrôle d'accès, la session utilisateur et le chargement de la sidebar globale.
   - `ui/components.py` : Composants réutilisables (cartes KPIs, alertes, badges) et filtre unifié (Sidebar Globale).
   - `config/theme.py` : Injection de CSS brut (vanilla CSS) pour assurer une présentation élégante, sombre ou claire, et l'intégration du *Mode Présentation*.

2. **Vues du Dashboard (`views/`)** :
   - **`0_accueil.py`** : Résumé exécutif dynamique, alertes récentes et génération de rapports PDF en un clic.
   - **`1_vue_reseau.py`** : Cartographie Folium avancée avec popups HTML montrant les scores et modes (ECO, NORMAL, CRITIQUE) géolocalisés.
   - **`2_prediction.py`** : Validation du modèle prédictif (NB1) avec intervalles de confiance, profil horaire et explicabilité SHAP.
   - **`3_anomalies.py`** : Détection NB2, fil d'actualité des anomalies (avec possibilité de les acquitter) et "Heatmap" temporelle des dysfonctionnements.
   - **`4_optimisation_rl.py`** : Simulateur interactif d'économies, comparaison des 7 agents RL, et courbes horaires d'optimisation (règles expertes vs IA).
   - **`5_simulation.py`** : **Le Cockpit Temps Réel.** Simulation de flux de données avec contrôle de vitesse (jusqu'à x3600), injection de pannes (surcharge, canicule), et affichage oscilloscope des KPIs réseau.
   - **`6_upload_admin.py`** : Page d'administration pour injecter de nouveaux datasets (Parquet/CSV), valider le schéma et relancer le pipeline de calcul.
   - **`7_configuration.py`** : Tableau de bord technique pour calibrer les seuils métiers (QoS minimale, niveau CPU) et les paramètres d'apprentissage RL en temps réel.

3. **Logique Métier et Services (`services/`)** :
   - **`data_service.py`** : Accès SQLite (via requêtes paramétrées sécurisées), chargement de fichiers `.parquet`, et intégration automatique avec HuggingFace Hub (fallback local garanti).
   - **`pipeline_service.py`** : Exécution combinée de la chaîne de décision IA (NB1 → NB2 → NB3). Remplissage intelligent des métriques manquantes lors des simulations ou uploads.
   - **`decision_service.py`** : Moteur de décision experte calculant la criticité d'une station (Score QoS, impact anomalies, charge serveur).
   - **`optimization_service.py`** : Implémentation des stratégies de "Sleep Mode", de réduction de puissance et de free-cooling en fonction des règles métiers (température < 22°C, trafic < 15%, etc.).
   - **`realtime_generator.py`** : Moteur de simulation qui interpole de manière réaliste les séries temporelles de trafic voix/data et simule l'impact d'événements extérieurs (météo, pannes).

4. **Sécurité et Authentification (`auth/`, `security/`)** :
   - Système RBAC (Role-Based Access Control) robuste.
   - Utilisateurs stockés sur SQLite via `bcrypt` (mot de passe haché).
   - Distinction claire entre `ADMIN` (accès total, configuration) et `INGENIEUR` (limité à un périmètre de stations précis et bloqué hors des panels de configuration).

---

## Logique de Décision et Pipeline Data

Le cycle de vie de la donnée se décompose en 3 "Notebooks" (NB) intégrés directement dans le moteur Python du dashboard :

### 1. NB1 : Prédiction (Machine Learning)
Le dashboard charge le dataset Parquet. Si la prédiction n'est pas présente, un modèle Ridge/LightGBM (ou le fallback du pipeline de simulation) prédit la consommation énergétique attendue d'une station en fonction de l'heure, de la météo et du trafic attendu.

### 2. NB2 : Détection d'Anomalies (Ensemble Learning)
L'écart entre la prédiction (NB1) et la réalité, couplé à une chute de qualité de service (QoS) ou un pic CPU, est analysé. Si le `score_anom_moy` dépasse le seuil configuré par l'Admin (ex: `0.60`), le système marque la station comme `CRITIQUE`.

### 3. NB3 : Optimisation (Reinforcement Learning et Règles)
Une fois l'état du réseau connu, le moteur de décision évalue si une action est possible (QoS > 0.60).
Le système propose alors :
- *Sleep mode sectoriel* la nuit.
- *Réduction de puissance (-3dB)* si la couverture 4G le permet.
- *Free Cooling* si la météo est favorable.
Ces décisions sont auditables sur la page de simulation où le mode de la station bascule dynamiquement en **ECO**.

---

## Installation et Exécution Rapide

### Prérequis
- Python 3.11+
- Pip
- L'environnement doit posséder les fichiers de données dans `outputs/` ou utiliser HuggingFace Hub (configuré dans `.env`).

### Commandes
```bash
# 1. Cloner ou naviguer dans le dossier du projet
cd dashboard_project

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application Streamlit (Port par défaut: 8501)
python -m streamlit run app.py
```

### Accès par défaut
L'application requiert une authentification basée sur la base de données locale SQLite (`dashboard_ops.sqlite3`).
- Compte Administrateur typique: `admin@tt.tn` (ou selon configuration DB existante).
- Compte Ingénieur typique: `ingenieur@tt.tn`.

---

## Génération de Rapports PDF
Le système embarque `fpdf2` (via `utils/pdf_export.py`) permettant de générer en 1 clic un rapport de supervision A4 professionnel. Le rapport inclut le logotype TT, les KPIs majeurs (économies en DT, kWh et réduction CO2) ainsi que les alertes prioritaires prêtes à être envoyées à la direction technique.

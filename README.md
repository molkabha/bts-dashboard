# BTS Energy Monitor — Tunisie Telecom

Application **Streamlit** de supervision énergétique des stations BTS, alimentée par trois notebooks de data science (prédiction, anomalies, optimisation / RL) et leurs artefacts.

**Dépôt :** [github.com/molkabha/bts-dashboard](https://github.com/molkabha/bts-dashboard)

---

## Vue d'ensemble

| Composant | Rôle |
|-----------|------|
| **NB1** | Prédiction horaire de la consommation (LightGBM, bandes Q10–Q90, SHAP) |
| **NB2** | Détection d'anomalies non supervisée (7 détecteurs, vote d'ensemble) |
| **NB3** | Moteur de décision (ECO / NORMAL / ATTENTION / CRITIQUE), stratégies expertes, 7 agents RL |
| **Dashboard** | Visualisation, filtres réseau, rôles admin / ingénieur, simulation what-if |

**Chaîne de données (hors ligne → interface) :**

```
Notebooks (nb1, nb2, nb3)
    → parquets / joblib / JSON
    → Hub Hugging Face molkab/dashboard  (ou copie locale VF/*/output)
    → enrich_dashboard_data() + KPI
    → pages Streamlit
```

Sur la plupart des pages, le dashboard **lit et agrège** les exports notebook (pas de réentraînement à chaque filtre). La page **Simulation** recalcule un pas horaire via profils historiques et, si disponible, le pipeline d'inférence NB3.

---

## Notebooks (fichiers du dépôt)

| Fichier | Thème |
|---------|--------|
| `nb1-prediction.ipynb` | Apprentissage supervisé — consommation horaire |
| `nb2-d.ipynb` | Détection d'anomalies non supervisée |
| `nb3-p.ipynb` | Décision, optimisation par règles et RL |

### NB1 — Prédiction supervisée

- Nettoyage, feature engineering (temps, météo, trafic, calendrier TN), comparaison de **7 modèles** supervisés, validation croisée temporelle, SHAP.
- **Sorties utilisées par le dashboard :**
  - Modèles : `best_model.joblib`, `encodeurs.joblib`, `quantile_models.joblib`, `config.joblib`
  - Données : `df_full_processed.parquet`, `df_train_processed.parquet`, `df_test_processed.parquet`
  - Métriques / viz : `resultats_modeles.json`, `shap_*.png`

### NB2 — Anomalies

- Prérequis : sorties NB1 (`df_full_processed.parquet`, `config.joblib`).
- Features d'anomalie, **7 détecteurs**, calibration, **vote d'ensemble**, profils K-Means.
- **Sorties utilisées par le dashboard :**
  - `modeles_anomalie.joblib`, `df_avec_anomalies.parquet`, `resultats_anomalie.json`
  - `performance_qualitative_modeles.csv`, `score_stations.parquet`
  - `autoencoder.keras` (si TensorFlow), images `tsne_anomalies.png`, `precision_recall_modeles.png`

### NB3 — Décision et optimisation

- Prérequis : NB1 + NB2.
- Moteur **ECO / NORMAL / ATTENTION / CRITIQUE**, garde-fou QoS, **5 stratégies** expertes, environnement de simulation, **7 agents RL**, pipeline d'inférence.
- **Sorties utilisées par le dashboard :**
  - `streamlit_data.parquet` (jeu principal fusionné), `decisions_par_station.parquet`
  - `pipeline_inference.joblib`, `agents_rl_7.pkl`
  - `kpi_reseau.json`, `rapport_optimisation.json`
  - `streamlit_profil_horaire.parquet`, `streamlit_timeseries.parquet`, `streamlit_carte_stations.parquet`
  - `rl_7agents_apprentissage.png`, `tableau_de_bord_complet.png`

La liste complète des artefacts attendus est dans `ARTIFACT_REGISTRY` (`services/data_service.py`).

---

## Dashboard Streamlit

### Lancement

```bash
pip install -r requirements.txt
python app.py
```

Équivalent : `streamlit run app.py`. Point d'entrée : **`app.py`** (configuration page, variables `.env`, puis `ui/dashboard.py`).

### Rôles et navigation

| Profil | Menu (7 / 6 entrées) | Périmètre |
|--------|------------------------|-----------|
| **Administrateur** | Accueil, Carte, Prédiction, Anomalies, Optimisation, Simulation, **Configuration** | Tout le parc ; KPI financiers ; détails ML (SHAP, détecteurs, agents RL) |
| **Ingénieur réseau** | Idem **sans** Configuration | **Stations assignées** uniquement (RLS) ; vues opérationnelles allégées (moins de détails modèles) |

L'écran **Configuration** (admin) regroupe trois onglets :

1. **Stations** — activer / désactiver des sites sur le jeu de données actif  
2. **Import** — publication d'un dataset (CSV / parquet) fusionné avec les colonnes NB  
3. **Utilisateurs** — comptes, mots de passe, affectation des stations aux ingénieurs  

### Pages et lien avec les notebooks

| Page | Fichier | NB | Contenu principal |
|------|---------|-----|-------------------|
| Accueil | `p0_accueil.py` | — | KPI (économies, CO₂, % ECO, alertes), camembert **répartition des modes** (dernier état / station), top 5 stations critiques, export PDF (admin) |
| Carte | `p1_vue_reseau.py` | — | Carte Folium (couleur = action NB3), filtres sidebar, comparaison gouvernorats |
| Prédiction | `p2_prediction.py` | NB1 | Courbes réel / prédit / Q10–Q90 ; R² et comparaison modèles (admin) ; SHAP (admin) |
| Anomalies | `p3_anomalies.py` | NB2 | Scatter score × heure, tableau stations, seuil d'ensemble résolu, stats détecteurs (admin) |
| Optimisation | `p4_optimisation_rl.py` | NB3 | KPI **économies retenues** max(règles, RL), actions par mode, top stations, gains expert / RL, profil horaire, agents RL (admin) |
| Simulation | `p5_simulation.py` | NB3 | Replay horaire (profils + pipeline ou repli offline), alertes, journal, cartes |
| Configuration | `p7_configuration.py` | — | Stations, import dataset, utilisateurs (`p6`, `p8` en panneaux) |

### Données côté application

- **Jeu actif :** `streamlit_data.parquet` ou dataset publié / `df_full_processed.parquet`
- **Enrichissement :** fusion `df_avec_anomalies.parquet` (NB2) + décisions NB3 + harmonisation des économies (`services/nb_metrics.py`)
- **Hub :** par défaut `USE_HF_HUB=True`, dépôt [`molkab/dashboard`](https://huggingface.co/molkab/dashboard) — repli local `VF/NB1/...`, `VF/NB2/output`, `VF/NB3/output`
- **Persistance :** SQLite (`dashboard_ops.sqlite3` par défaut) — utilisateurs, sessions, alertes ; exemple `data/alerts.sqlite`

Copier `.env.example` vers `.env` pour `SECRET_KEY`, `HF_TOKEN` (dépôt privé), SMTP, etc.

### Sécurité

- Authentification bcrypt, verrouillage après échecs de connexion, rate limiting (`security/middleware.py`)
- CSRF session, expiration de session, contrôle d'accès par page
- En production : `SECRET_KEY` obligatoire (`ENVIRONMENT=production`)

---

## Structure du projet

```
app.py                 # Entrée Streamlit
ui/dashboard.py        # Routeur et rôles
ui/display.py          # Libellés menu (7 pages admin)
views/                 # Pages p0–p8, simulation_*
services/
  data_service.py      # Artefacts, Hub, enrichissement, KPI
  nb_metrics.py        # harmonize_nb3_economies, écarts %
  decision_service.py  # MoteurDecisionEnergie (NB3)
  optimization_service.py
  nb_inference.py      # Pipeline simulation
  synthetic_bts.py     # Profils horaires simulation
security/middleware.py
config/settings.py     # Constantes métier (0,40 DT/kWh, QoS 0,60, …)
tests/                 # Suite pytest (voir ci-dessous)
```

---

## Installation

1. Python **3.11** recommandé (`runtime.txt` pour Streamlit Cloud).
2. Dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Artefacts : activer le Hub ou placer les fichiers NB sous `VF/` (voir `config/settings.py`).
4. Lancer :
   ```bash
   python app.py
   ```

### Tests automatisés

```bash
pip install -r requirements-dev.txt
pytest
```

Couverture optionnelle :

```bash
pytest --cov=services --cov=security --cov=ui --cov=utils --cov-report=term-missing
```

19 tests : métriques NB3, moteur de décision, mots de passe, rate limiting, smoke imports / menu. CI : `.github/workflows/tests.yml`.

---

## Données brutes et dossiers locaux

- Jeu source typique : `VF/tunisie_telecom_dataset.csv` (hors dépôt Git si volumineux).
- Sorties notebooks : `VF/NB1/NB1-P/output`, `VF/NB2/output`, `VF/NB3/output` (chemins par défaut dans `settings.py`).
- **`VF/`** = répertoire local **V**ersion **F**ichiers / livrables notebooks (copie de travail), utilisé quand le Hub Hugging Face n'est pas accessible.

---

## Notes importantes

- **Économies affichées :** par ligne, `economie_kwh = max(économie règles, économie RL)`, plafonnée à la consommation ; KPI réseau = somme sur la période filtrée × 0,40 DT/kWh.
- **Seuil anomalie :** lu depuis `resultats_anomalie.json` si présent, sinon dérivé du quantile des scores dans `df_avec_anomalies.parquet` (aligné sur `%` anomalies du KPI réseau).
- **Simulation :** scénario what-if sur profils historiques (Ramadan, fériés TN, week-end) — pas une télémétrie live du réseau commercial.
- **Déploiement :** application Streamlit (`app.py`, `runtime.txt`) ; pas de `Dockerfile` / `nginx.conf` dans ce dépôt (évolution possible en environnement opérateur).

---

## Licence / contexte

Projet de fin d'études — optimisation énergétique du réseau mobile Tunisie Telecom (GLSI).

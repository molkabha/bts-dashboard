# BTS Energy Monitor — Tunisie Telecom

Application **Streamlit** de supervision énergétique des stations BTS, alimentée par trois notebooks de data science (prédiction, anomalies, optimisation / RL) et leurs artefacts publiés en ligne.

**Application en ligne :** [https://bts-dashboard-tt.streamlit.app/](https://bts-dashboard-tt.streamlit.app/)

---

## Vue d'ensemble

| Composant | Rôle |
|-----------|------|
| **NB1** | Prédiction horaire de la consommation (LightGBM, bandes Q10–Q90, SHAP) |
| **NB2** | Détection d'anomalies non supervisée (7 détecteurs, vote d'ensemble) |
| **NB3** | Moteur de décision (ECO / NORMAL / ATTENTION / CRITIQUE), stratégies expertes, 7 agents RL |
| **Dashboard** | Visualisation, filtres réseau, rôles admin / ingénieur, simulation what-if |

**Chaîne de données (notebooks → interface en ligne) :**

```
Notebooks (nb1, nb2, nb3)
    → parquets / joblib / JSON
    → Hub Hugging Face molkab/dashboard
    → application Streamlit Cloud (chargement à la volée)
    → enrich_dashboard_data() + KPI
    → pages du tableau de bord
```

Sur la plupart des pages, le dashboard **lit et agrège** les exports notebook (pas de réentraînement à chaque filtre). La page **Simulation** recalcule un pas horaire via profils et pipeline NB3 hébergé sur le Hub.

---

## Notebooks

| Fichier | Thème |
|---------|--------|
| `nb1-prediction.ipynb` | Apprentissage supervisé — consommation horaire |
| `nb2-d.ipynb` | Détection d'anomalies non supervisée |
| `nb3-p.ipynb` | Décision, optimisation par règles et RL |

### NB1 — Prédiction supervisée

- Nettoyage, feature engineering (temps, météo, trafic, calendrier TN), comparaison de **7 modèles** supervisés, validation croisée temporelle, SHAP.
- **Sorties exposées au dashboard :** `best_model.joblib`, `encodeurs.joblib`, `quantile_models.joblib`, `df_full_processed.parquet`, `resultats_modeles.json`, visuels SHAP.

### NB2 — Anomalies

- Prérequis : sorties NB1.
- **7 détecteurs**, vote d'ensemble, profils K-Means.
- **Sorties :** `modeles_anomalie.joblib`, `df_avec_anomalies.parquet`, `resultats_anomalie.json`, `score_stations.parquet`.

### NB3 — Décision et optimisation

- Moteur **ECO / NORMAL / ATTENTION / CRITIQUE**, **5 stratégies** expertes, **7 agents RL**, pipeline d'inférence.
- **Sorties :** `streamlit_data.parquet`, `decisions_par_station.parquet`, `pipeline_inference.joblib`, `kpi_reseau.json`, `rapport_optimisation.json`, profils horaires et séries pré-calculées.

La liste complète est dans `ARTIFACT_REGISTRY` (`services/data_service.py`), servie depuis le Hub [`molkab/dashboard`](https://huggingface.co/molkab/dashboard).

---

## Dashboard Streamlit (déploiement en ligne)

L'application de démonstration et d'exploitation est hébergée sur **Streamlit Community Cloud** :

**[https://bts-dashboard-tt.streamlit.app/](https://bts-dashboard-tt.streamlit.app/)**

À l'ouverture, les artefacts NB1/NB2/NB3 sont téléchargés depuis le Hub Hugging Face (`USE_HF_HUB=True`, `HF_REPO_ID=molkab/dashboard`). Les comptes, sessions et alertes sont gérés par une base **SQLite** côté serveur Streamlit.

### Rôles et navigation

| Profil | Menu (7 / 6 entrées) | Périmètre |
|--------|------------------------|-----------|
| **Administrateur** | Accueil, Carte, Prédiction, Anomalies, Optimisation, Simulation, **Configuration** | Tout le parc ; KPI financiers ; détails ML |
| **Ingénieur réseau** | Idem **sans** Configuration | **Stations assignées** uniquement (RLS) |

**Configuration** (admin) — deux onglets : stations actives, gestion des utilisateurs.

### Pages et lien avec les notebooks

| Page | NB | Contenu principal |
|------|-----|-------------------|
| Accueil | — | KPI, répartition des modes, top 5 stations critiques |
| Carte | — | Folium, action NB3, gouvernorats |
| Prédiction | NB1 | Réel / prédit / Q10–Q90, SHAP (admin) |
| Anomalies | NB2 | Scores, seuil, alertes |
| Optimisation | NB3 | Économies retenues, actions, gains expert/RL |
| Simulation | NB3 | Replay horaire, alertes, journal |
| Configuration | — | Stations, utilisateurs (admin) |

### Sécurité

- Authentification bcrypt, verrouillage après échecs, rate limiting
- Sessions avec expiration, contrôle d'accès par rôle
- Secrets (`SECRET_KEY`, `HF_TOKEN`, SMTP) configurés dans l'espace Streamlit Cloud (non versionnés)

---

## Structure du code source

```
app.py
ui/dashboard.py
views/
services/data_service.py
services/nb_metrics.py
security/middleware.py
config/settings.py
tests/
```

---

## Tests automatisés (qualité logicielle)

```bash
pip install -r requirements-dev.txt
pytest
```

19 tests unitaires et smoke tests ; workflow CI sur les pushes du dépôt source.

---

## Notes importantes

- **Économies :** `economie_kwh = max(règles, RL)` par ligne, plafond 48 % de la conso ; KPI réseau en DT = somme × 0,40.
- **Seuil anomalie :** JSON NB2 ou dérivation via quantile aligné sur `pct_anomalies` du KPI réseau.
- **Simulation :** scénario what-if — pas une télémétrie live du réseau commercial.

---

## Contexte

Projet de fin d'études — optimisation énergétique du réseau mobile Tunisie Telecom (GLSI).

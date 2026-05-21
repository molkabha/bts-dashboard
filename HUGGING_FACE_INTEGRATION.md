# BTS Dashboard - Hugging Face Integration

Dashboard Streamlit intégrant les données stockées sur Hugging Face Hub.

## 📦 Structure

```
├── data_loader.py          # Module pour charger les données HF
├── streamlit_app.py        # Application Streamlit principale
├── example_usage.py        # Exemples d'utilisation
├── requirements.txt        # Dépendances Python
└── .streamlit/config.toml  # Configuration Streamlit
```

## 🚀 Installation & Lancement

### 1. Cloner le repository
```bash
git clone https://github.com/molkabha/bts-dashboard.git
cd bts-dashboard
```

### 2. Créer un environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Lancer l'application
```bash
streamlit run streamlit_app.py
```

L'application ouvrira automatiquement à l'adresse: **http://localhost:8501**

## 📊 Pages disponibles

### 1. 📊 Vue d'ensemble
- Résumé des fichiers disponibles
- Statistiques globales
- Liste complète des ressources

### 2. 📈 Données
- Aperçu des données principales
- Statistiques descriptives
- Types et qualité des données

### 3. 🤖 Modèle RL
- Chargement du modèle de pipeline
- Agents de Reinforcement Learning
- Visualisation de l'apprentissage

### 4. 📉 KPI
- Métriques du réseau
- Rapport d'optimisation
- Décisions par station

### 5. 🗺️ Stations
- Données géographiques
- Scores des stations
- Tableau de bord complet

## 📁 Fichiers Hugging Face

Tous les fichiers sont stockés dans le repository: `molkab/dashboard`

| Fichier | Taille | Type |
|---------|--------|------|
| streamlit_data.parquet | 86.7 MB | Données principales |
| pipeline_inference.joblib | 236 MB | Modèle ML |
| streamlit_carte_stations.parquet | 12.1 kB | Géo données |
| streamlit_score_stations.parquet | 13.9 kB | Scores |
| streamlit_timeseries.parquet | 294 kB | Séries temporelles |
| decisions_par_station.parquet | 63.5 kB | Décisions |
| agents_rl_7.pkl | 37.9 kB | Agents RL |
| kpi_reseau.json | 1.09 kB | KPI |
| rapport_optimisation.json | 4.83 kB | Rapport |
| rl_7agents_apprentissage.png | 366 kB | Image |
| tableau_de_bord_complet.png | 327 kB | Image |

## 🔧 Utilisation du Module data_loader

```python
from data_loader import load_parquet, load_json, load_joblib, load_pickle, load_image

# Charger des données parquet
df = load_parquet("data")

# Charger un modèle
model = load_joblib("model")

# Charger du JSON
kpi = load_json("kpi")

# Charger une image
img = load_image("image_rl")
```

## 🔑 Authentification Hugging Face (optionnel)

Si le repository est privé, configurez votre token:

```python
from huggingface_hub import login
login(token="your_hf_token")
```

Ou via variables d'environnement:
```bash
export HF_TOKEN="your_hf_token"
```

## 📋 Exigences

- Python 3.9+
- pip (ou conda)
- Connexion Internet pour télécharger les données
- ~500 MB d'espace disque (cache des fichiers)

## ⚙️ Configuration

Voir `.streamlit/config.toml` pour personnaliser:
- Thème
- Logging
- Comportement du client

## 🐛 Troubleshooting

### Erreur de téléchargement Hugging Face
```
Solution: Vérifier la connexion Internet et les droits d'accès
```

### Cache plein
```bash
# Vider le cache Hugging Face
rm -rf .cache/huggingface
```

### Port 8501 déjà utilisé
```bash
streamlit run streamlit_app.py --server.port 8502
```

## 📚 Ressources

- [Streamlit Documentation](https://docs.streamlit.io)
- [Hugging Face Hub API](https://huggingface.co/docs/hub/security)
- [Pandas Documentation](https://pandas.pydata.org/docs/)

## 📝 Notes

- Les fichiers sont mis en cache localement dans `.cache/huggingface`
- Chaque chargement utilise le cache si disponible
- La première utilisation télécharge les fichiers (~500 MB)

## 👤 Auteur

Created by molkabha

## 📄 License

MIT

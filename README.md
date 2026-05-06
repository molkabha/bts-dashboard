# BTS Energy Management System Dashboard

Dashboard Streamlit pour le monitoring energie, la detection d'anomalies et l'optimisation des stations BTS de Tunisie Telecom.

## Fonctionnalites

- Authentification admin et ingenieur avec reset de mot de passe par email.
- Administration des comptes: creation, desactivation, reactivation, suppression et renvoi de mot de passe temporaire.
- Dataset actif publie par l'admin: les pages admin et ingenieur utilisent le meme dataset courant.
- Generation temps reel de datasets station/reseau avec profils trafic, jours feries tunisiens, vendredi, week-end, Ramadan, meteo et anomalies.
- Pages NB1/NB2/NB3: monitoring, alertes, decisions automatiques, modifications humaines et historique.
- Centre operations: recherche globale, SLA, statuts, commentaires, tickets, notifications et rapports.
- Audit local SQLite des actions sensibles.

## Pipeline

Le dashboard consolide les sorties des notebooks:

1. `NB1` - prediction de consommation energetique.
2. `NB2` - detection d'anomalies.
3. `NB3` - decisions d'optimisation et recommandations RL.

Si un dataset est publie depuis l'interface admin, il devient la source active pour toutes les pages. Les scores stations et les decisions affichees sont alors recalcules depuis ce dataset actif.

## Installation

```bash
cd dashboard_project
pip install -r requirements.txt
streamlit run app.py
```

## Configuration

Creer un fichier `.env` dans `dashboard_project/`:

```env
ENVIRONMENT=development
DEBUG=false
SECRET_KEY=change-me
REDIS_ENABLED=false

BTS_SMTP_HOST=
BTS_SMTP_PORT=587
BTS_SMTP_USER=
BTS_SMTP_PASSWORD=
BTS_SMTP_FROM=
BTS_SMTP_STARTTLS=1
```

Le SMTP est necessaire pour envoyer les mots de passe temporaires.

## Securite

- `admin123` est invalide pour les admins.
- Le compte admin principal doit utiliser le flux de mot de passe oublie si aucun mot de passe valide n'est connu.
- En production, definir un `SECRET_KEY` fort et utiliser Redis pour le rate limiting multi-processus.
- Ne jamais commiter `.env`, base SQLite de production ou secrets SMTP.

## Tests

```bash
cd dashboard_project
$env:DEBUG='false'
pytest tests -q
```

## Structure

```text
config/       configuration et theme
services/     logique metier, donnees, auth, pipeline
ui/           pages Streamlit et composants
security/     middleware session/rate limiting
utils/        validation, formatage, logging
NB1/ NB2/ NB3 sorties notebooks et artefacts
```

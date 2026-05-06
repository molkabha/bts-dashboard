"""Home and overview pages."""
import streamlit as st
from ui.layout import header, section
from security.middleware import security_middleware

def home_page():
    security_middleware.enforce()
    header("Accueil", "Bienvenue sur le BTS Energy Management System")
    
    st.markdown(
        """
        Cette application permet de superviser et d'optimiser la consommation énergétique 
        du réseau de stations de base (BTS) de Tunisie Telecom.
        
        ### Modules principaux
        - **NB1 - Supervised Learning** : Prédiction de consommation.
        - **NB2 - Unsupervised Anomaly** : Détection de comportements anormaux.
        - **NB3 - Reinforcement Learning** : Optimisation et recommandations.
        """
    )
    
    with section("Résumé du système"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Statut", "Opérationnel")
        c2.metric("Dernière mise à jour", "Aujourd'hui")
        c3.metric("Version", "2.0.0")

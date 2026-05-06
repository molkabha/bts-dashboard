"""User preferences and settings."""
import streamlit as st
from ui.layout import header
from security.middleware import security_middleware

def settings_page():
    security_middleware.enforce()
    header("Paramètres", "Préférences utilisateur et configuration")
    
    st.subheader("Profil")
    st.write(f"**Utilisateur :** {st.session_state.get('display', 'Inconnu')}")
    st.write(f"**Rôle :** {st.session_state.get('role', 'Inconnu')}")
    
    st.divider()
    
    st.subheader("Préférences d'affichage")
    st.toggle("Mode sombre", value=True)
    st.selectbox("Langue", ["Français", "Anglais", "Arabe"])
    
    st.divider()
    
    if st.button("Se déconnecter", type="secondary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

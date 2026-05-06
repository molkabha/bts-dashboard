import streamlit as st
from datetime import datetime

from security.middleware import security_middleware
from services.auth_service import authenticate_user, update_user_password
from services.data_service import db_execute, log_event
from ui.layout import header, section
from utils.validators import UserInputValidator


def profile_page():
    security_middleware.enforce()
    header("Mon profil", "Informations personnelles, securite et preferences")

    username = st.session_state.get("user", "")
    current_display = st.session_state.get("display", "")
    current_email = st.session_state.get("email", "")

    with section("Informations"):
        with st.form("profile_form"):
            display = st.text_input("Nom affiche", value=current_display)
            email = st.text_input("Email", value=current_email)
            submitted = st.form_submit_button("Enregistrer", type="primary")

        if submitted:
            display = UserInputValidator.sanitize_string(display, 120)
            email = UserInputValidator.sanitize_string(email, 120).lower()
            if not display:
                st.error("Le nom affiche est obligatoire.")
            elif not UserInputValidator.validate_email(email):
                st.error("Email invalide.")
            else:
                before = {"display": current_display, "email": current_email}
                db_execute("update_user_profile", (display, email, username))
                st.session_state["display"] = display
                st.session_state["email"] = email
                log_event("profile_updated", {"before": before, "after": {"display": display, "email": email}})
                st.success("Profil mis a jour.")
                st.rerun()

    with section("Mot de passe"):
        with st.form("change_own_password"):
            current = st.text_input("Mot de passe actuel", type="password")
            new_password = st.text_input("Nouveau mot de passe", type="password")
            confirm = st.text_input("Confirmer", type="password")
            submitted = st.form_submit_button("Changer le mot de passe", type="primary")

        if submitted:
            success, _, _ = authenticate_user(username, current)
            ok_strength, errors = UserInputValidator.validate_password_strength(new_password)
            if not success:
                st.error("Mot de passe actuel incorrect.")
            elif not ok_strength:
                for error in errors:
                    st.error(error)
            elif new_password != confirm:
                st.error("La confirmation ne correspond pas.")
            elif new_password == current:
                st.error("Choisissez un mot de passe different.")
            else:
                update_user_password(username, new_password, 0)
                log_event("own_password_changed", {"user": username, "at": datetime.now().isoformat(timespec="seconds")})
                st.success("Mot de passe modifie.")

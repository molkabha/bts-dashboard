import streamlit as st
from pathlib import Path
from services.auth_service import authenticate_user, update_user_password, create_user_session, reset_user_password
from security.middleware import security_middleware
from ui.components import header, image_data_uri
from utils.validators import UserInputValidator


def login_page(logo_path: Path):
    # No CSRF needed for login usually, but we could add it.
    # Rate limiting is already handled in authenticate_user.
    logo = image_data_uri(logo_path)
    logo_html = f'<img class="login-logo" src="{logo}" alt="Tunisie Telecom">' if logo else ""

    left, center, right = st.columns([1, 1.05, 1])
    with center:
        st.markdown(
            f"""
<div class="login-panel brand-panel">
  {logo_html}
  <div class="login-kicker">Tunisie Telecom</div>
  <div class="login-heading">BTS Energy Management</div>
</div>
""",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown(
                """
<div class="form-title">Connexion</div>
<div class="form-subtitle">Accès sécurisé au tableau de bord.</div>
""",
                unsafe_allow_html=True,
            )

            with st.form("login_unique"):
                user = st.text_input("Identifiant", key="login_user", placeholder="Email ou nom utilisateur")
                pwd = st.text_input("Mot de passe", type="password", key="login_pwd", placeholder="Mot de passe")
                submitted = st.form_submit_button("Se connecter", type="primary", width="stretch")

            if submitted:
                success, user_record, message = authenticate_user(user, pwd)
                if success and user_record:
                    session_data = create_user_session(user_record)
                    st.session_state.update(session_data)
                    st.session_state["_goto_home"] = True
                    role = session_data.get("role", "")
                    role_label = "Administrateur" if role == "admin" else "Ingenieur reseau"
                    st.session_state["_login_role_hint"] = role_label
                    from services.data_service import log_event
                    log_event("login", {"role": session_data["role"]})
                    st.rerun()
                else:
                    st.error(message)

            with st.expander("Mot de passe oublié", expanded=False):
                with st.form("forgot_password"):
                    reset_login = st.text_input("Email ou identifiant", key="reset_login")
                    reset_submitted = st.form_submit_button("Recevoir un mot de passe temporaire", width="stretch")

                if reset_submitted:
                    reset_login = UserInputValidator.sanitize_string(reset_login, 120)
                    if not reset_login:
                        st.error("Saisissez votre email ou identifiant.")
                    else:
                        ok, message = reset_user_password(reset_login)
                        if ok:
                            st.success(message)
                        else:
                            st.error(message)

            role_hint = st.session_state.pop("_login_role_hint", None)
            if role_hint:
                st.success(f"Connexion reussie — acces {role_hint}. Redirection vers votre espace...")

            st.markdown(
                """
<div class="login-footer">
  <strong>Tunisie Telecom</strong> — BTS Energy Management System<br>
  Acces reserve : <span style="color:#059669;font-weight:800;">ADMIN</span> et
  <span style="color:#2563eb;font-weight:800;">INGENIEUR RESEAU</span>
</div>
""",
                unsafe_allow_html=True,
            )


def force_password_change_page():
    header("Modifier le mot de passe", "Creation d'un mot de passe personnel obligatoire")
    st.info("Votre mot de passe actuel est temporaire. Choisissez un nouveau mot de passe pour continuer.")

    # Generate CSRF token in session state (internal)
    security_middleware.generate_csrf_token()

    with st.form("force_password_change"):
        current = st.text_input("Mot de passe temporaire", type="password")
        new_password = st.text_input("Nouveau mot de passe", type="password")
        confirm = st.text_input("Confirmer le nouveau mot de passe", type="password")
        submitted = st.form_submit_button("Enregistrer le nouveau mot de passe", type="primary", width="stretch")

    if not submitted:
        return

    user = st.session_state.get("username") or st.session_state.get("user")
    # Re-authenticate to ensure current password is correct
    success, user_record, _ = authenticate_user(user, current)

    if not success:
        st.error("Mot de passe temporaire incorrect.")
        return

    # Validate password strength
    is_strong, errors = UserInputValidator.validate_password_strength(new_password)
    if not is_strong:
        for error in errors:
            st.error(error)
        return

    if new_password != confirm:
        st.error("La confirmation ne correspond pas.")
        return
    if new_password == current:
        st.error("Choisissez un mot de passe different du mot de passe temporaire.")
        return

    update_user_password(user, new_password, 0)
    st.session_state["must_change_password"] = False
    # log_event("password_changed", {"user": user})
    st.success("Mot de passe modifie. Acces au tableau de bord.")
    st.rerun()

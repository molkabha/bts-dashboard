import streamlit as st

from pathlib import Path

from services.auth_service import (
    authenticate_user,
    update_user_password,
    create_user_session,
    reset_user_password,
)

from security.middleware import security_middleware

from ui.components import header, image_data_uri

from utils.validators import UserInputValidator


def login_page(logo_path: Path):

    logo = image_data_uri(logo_path)

    logo_html = (
        f'<img class="login-logo" src="{logo}" alt="Tunisie Telecom">' if logo else ""
    )

    left, center, right = st.columns([1, 1.05, 1])

    with center:

        st.markdown(
            f'\n<div class="login-panel brand-panel">\n  {logo_html}\n  <div class="login-kicker">Tunisie Telecom</div>\n  <div class="login-heading">Gestion énergétique BTS</div>\n</div>\n',
            unsafe_allow_html=True,
        )

        with st.container(border=True):

            st.markdown(
                '\n<div class="form-title">Connexion</div>\n<div class="form-subtitle">Accès sécurisé au tableau de bord.</div>\n',
                unsafe_allow_html=True,
            )

            with st.form("login_form"):

                user = st.text_input(
                    "Identifiant",
                    key="login_user",
                    placeholder="Courriel ou nom d'utilisateur",
                )

                pwd = st.text_input(
                    "Mot de passe",
                    type="password",
                    key="login_pwd",
                    placeholder="Mot de passe",
                )

                submitted = st.form_submit_button(
                    "Se connecter", type="primary", use_container_width=True
                )

            if submitted:

                success, user_record, message = authenticate_user(user, pwd)

                if success and user_record:

                    session_data = create_user_session(user_record)

                    st.session_state.update(session_data)

                    st.session_state["_goto_home"] = True

                    role = session_data.get("role", "")

                    role_label = (
                        "Administrateur" if role == "admin" else "Ingénieur réseau"
                    )

                    st.session_state["_login_role_hint"] = role_label

                    from services.data_service import log_event

                    log_event("login", {"role": session_data["role"]})

                    st.rerun()

                else:

                    st.error(message)

            with st.expander("Mot de passe oublié", expanded=False):

                with st.form("forgot_password_form"):

                    reset_login = st.text_input(
                        "Courriel ou identifiant",
                        key="reset_login",
                        placeholder="Courriel ou identifiant",
                    )

                    reset_submitted = st.form_submit_button(
                        "Recevoir un mot de passe temporaire", use_container_width=True
                    )

                if reset_submitted:

                    reset_login = UserInputValidator.sanitize_string(reset_login, 120)

                    if not reset_login:

                        st.error("Saisissez votre courriel ou identifiant.")

                    else:

                        ok, message = reset_user_password(reset_login)

                        if ok:

                            st.success(message)

                        else:

                            st.error(message)

            role_hint = st.session_state.pop("_login_role_hint", None)

            if role_hint:

                st.success(
                    f"Connexion réussie — accès {role_hint}. Redirection vers votre espace…"
                )

            st.markdown(
                '\n<div class="login-footer">\n  <strong>Tunisie Telecom</strong> — Gestion énergétique BTS<br>\n  Accès réservé : <span style="color:#c8102e;font-weight:800;">ADMINISTRATEUR</span> et\n  <span style="color:#2563eb;font-weight:800;">INGÉNIEUR RÉSEAU</span>\n</div>\n',
                unsafe_allow_html=True,
            )


def force_password_change_page():

    header(
        "Modifier le mot de passe", "Création d'un mot de passe personnel obligatoire"
    )

    st.info(
        "Votre mot de passe actuel est temporaire. Choisissez un nouveau mot de passe pour continuer."
    )

    security_middleware.generate_csrf_token()

    with st.form("force_password_change_form"):

        current = st.text_input("Mot de passe temporaire", type="password")

        new_password = st.text_input("Nouveau mot de passe", type="password")

        confirm = st.text_input("Confirmer le nouveau mot de passe", type="password")

        submitted = st.form_submit_button(
            "Enregistrer le nouveau mot de passe",
            type="primary",
            use_container_width=True,
        )

    if not submitted:

        return

    user = st.session_state.get("username") or st.session_state.get("user")

    success, user_record, _ = authenticate_user(user, current)

    if not success:

        st.error("Mot de passe temporaire incorrect.")

        return

    is_strong, errors = UserInputValidator.validate_password_strength(new_password)

    if not is_strong:

        for error in errors:

            st.error(error)

        return

    if new_password != confirm:

        st.error("La confirmation ne correspond pas.")

        return

    if new_password == current:

        st.error("Choisissez un mot de passe différent du mot de passe temporaire.")

        return

    update_user_password(user, new_password, 0)

    st.session_state["must_change_password"] = False

    st.success("Mot de passe modifié. Accès au tableau de bord.")

    st.rerun()

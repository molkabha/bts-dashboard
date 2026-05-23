"""Page 8 - Gestion des Utilisateurs (Comptes, Acces, Securite)."""

from __future__ import annotations

import streamlit as st
from datetime import datetime

from security.middleware import security_middleware
from services.data_service import (
    db_read, db_execute, db_scalar,
    get_user_stations, set_user_stations,
    available_stations, log_event
)
from services.notification_service import (
    send_account_password_email,
    send_account_status_email,
    send_account_deletion_email
)
from ui.components import header, section
from utils.security import password_hash, generate_temp_password


def render_utilisateurs_panel():
    """Contenu gestion utilisateurs (sans en-tete de page)."""
    tab1, tab2, tab3 = st.tabs(["Annuaire", "Ajouter un compte", "Acces Stations"])

    with tab1:
        _render_user_list()

    with tab2:
        _render_add_user()

    with tab3:
        _render_station_access()


def page_utilisateurs():
    security_middleware.enforce(role="admin")
    header("Utilisateurs", "Comptes et acces stations")
    render_utilisateurs_panel()


def _render_user_list():
    with section("Comptes existants"):
        users_df = db_read("get_all_users")
        if users_df.empty:
            st.info("Aucun utilisateur trouve.")
            return

        # Search bar
        search = st.text_input("Rechercher un utilisateur", placeholder="Nom ou email...")
        if search:
            users_df = users_df[
                users_df["username"].str.contains(search, case=False, na=False) |
                users_df["display"].str.contains(search, case=False, na=False) |
                users_df["email"].str.contains(search, case=False, na=False)
            ]

        # Display table with formatting
        display_df = users_df.copy()
        display_df["Statut"] = display_df["is_active"].apply(lambda x: "Actif" if x else "Desactive")
        display_df["Role"] = display_df["role"].apply(lambda x: "Admin" if x == "admin" else "Ingenieur")

        st.dataframe(
            display_df[["username", "display", "email", "Role", "Statut", "created_at"]],
            width="stretch",
            hide_index=True
        )

        # Action dropdown
        st.write("---")
        st.subheader("Actions sur un compte")
        selected_user = st.selectbox("Choisir un utilisateur pour modification", [""] + users_df["username"].tolist())

        if selected_user:
            user_data = users_df[users_df["username"] == selected_user].iloc[0]
            col1, col2, col3 = st.columns(3)

            with col1:
                # Toggle Active status
                new_status = 0 if user_data["is_active"] else 1
                label = "Desactiver le compte" if user_data["is_active"] else "Activer le compte"
                if st.button(label, width="stretch"):
                    db_execute("set_user_active", (new_status, selected_user))
                    log_event("user_status_changed", {"user": selected_user, "active": new_status})

                    email = user_data.get("email")
                    if email:
                        ok, msg = send_account_status_email(email, user_data.get(
                            "display", ""), selected_user, bool(new_status))
                        if ok:
                            st.success(f"Statut mis a jour. Email envoye a {email}")
                        else:
                            st.warning(f"Statut mis a jour, mais echec email : {msg}")
                    else:
                        st.success(f"Statut mis a jour pour {selected_user}")

                    st.rerun()

            with col2:
                # Reset Password
                if st.button("Re-envoyer / Reset PWD", width="stretch"):
                    temp_pwd = generate_temp_password()
                    new_hash = password_hash(temp_pwd)
                    db_execute("update_password", (new_hash, 1, selected_user))
                    log_event("password_reset", {"user": selected_user})

                    email = user_data.get("email")
                    if email:
                        ok, msg = send_account_password_email(
                            email, user_data.get("display", ""), selected_user, temp_pwd)
                        if ok:
                            st.success(f"Nouveau mot de passe envoye a {email}")
                        else:
                            st.error(f"Echec de l'envoi email : {msg}")
                            st.warning(f"Mot de passe temporaire : **{temp_pwd}**")
                    else:
                        st.warning(f"Aucun email associe. Mot de passe temporaire : **{temp_pwd}**")

            with col3:
                # Delete account
                if st.button("Supprimer le compte", type="secondary", width="stretch"):
                    st.session_state["pending_delete"] = selected_user

                if st.session_state.get("pending_delete") == selected_user:
                    st.error(f"Etes-vous sur de vouloir supprimer {selected_user} ?")
                    col_del1, col_del2 = st.columns(2)
                    with col_del1:
                        if st.button("OUI, SUPPRIMER", type="primary", width="stretch"):
                            # Check if it's the last admin
                            if user_data["role"] == "admin":
                                active_admins = db_scalar("count_active_admins")
                                if active_admins <= 1 and user_data["is_active"]:
                                    st.error("Impossible de supprimer le dernier administrateur actif.")
                                else:
                                    _perform_delete(user_data)
                            else:
                                _perform_delete(user_data)
                    with col_del2:
                        if st.button("ANNULER", width="stretch"):
                            st.session_state["pending_delete"] = None
                            st.rerun()


def _perform_delete(user_data):
    username = user_data["username"]
    email = user_data.get("email")
    display = user_data.get("display", "")

    db_execute("delete_user", (username,))
    log_event("user_deleted", {"user": username})

    if email:
        send_account_deletion_email(email, display, username)

    st.session_state["pending_delete"] = None
    st.success(f"Compte {username} supprime.")
    st.rerun()


def _render_add_user():
    with section("Creer un nouvel utilisateur"):
        with st.form("add_user_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Identifiant (Username)", placeholder="ex: m.alaya")
                new_display = st.text_input("Nom Complet", placeholder="ex: Molka Alaya")
                new_email = st.text_input("Email", placeholder="ex: m.alaya@tt.tn")
            with col2:
                new_role = st.selectbox("Role", ["ingenieur", "admin"])
                st.info("Un mot de passe temporaire sera genere et envoye par email a l'utilisateur.")

            submit = st.form_submit_button("Creer le compte", type="primary", width="stretch")

            if submit:
                if not new_username or not new_display:
                    st.error("L'identifiant et le nom complet sont obligatoires.")
                    return

                # Check uniqueness
                existing = db_read("get_user_by_username_or_email", (new_username, new_username))
                if not existing.empty:
                    st.error("Cet identifiant ou cet email est deja utilise.")
                    return

                if not new_email:
                    st.error("L'email est obligatoire pour l'envoi du mot de passe temporaire.")
                    return

                temp_pwd = generate_temp_password()
                final_hash = password_hash(temp_pwd)

                db_execute("insert_user", (
                    new_username,
                    new_email,
                    final_hash,
                    new_role,
                    new_display,
                    1,  # must_change_password
                    1,  # is_active
                    datetime.now().isoformat(),
                    st.session_state.get("user")
                ))

                log_event("user_created", {"user": new_username, "role": new_role})

                # Send Email
                ok, msg = send_account_password_email(new_email, new_display, new_username, temp_pwd)
                if ok:
                    st.success(
                        f"Utilisateur {new_username} cree. Le mot de passe temporaire a ete envoye a {new_email}.")
                else:
                    st.success(f"Utilisateur {new_username} cree, mais l'envoi de l'email a echoue.")
                    st.warning(f"Mot de passe temporaire a communiquer manuellement : **{temp_pwd}**")
                    st.error(f"Raison de l'echec email : {msg}")


def _render_station_access():
    with section("Gestion des Acces par Station"):
        st.caption("Restreindre la visibilite des stations pour les comptes ingenieurs.")
        engineers_df = db_read("get_all_engineers")

        if engineers_df.empty:
            st.info("Aucun compte ingenieur trouve dans le systeme.")
        else:
            engineers = sorted(engineers_df["username"].tolist())
            selected_engineer = st.selectbox("Choisir un ingenieur", [""] + engineers, key="rls_user_sel")

            if selected_engineer:
                current_assigned = get_user_stations(selected_engineer)
                all_dataset_stations = available_stations()
                all_options = sorted(list(set(all_dataset_stations + current_assigned)))

                new_assigned = st.multiselect(
                    f"Stations affectees a {selected_engineer}",
                    options=all_options,
                    default=current_assigned,
                    help="Laissez vide pour retirer tout acces. L'ingenieur ne verra que les stations selectionnees."
                )

                if st.button(f"Enregistrer les acces pour {selected_engineer}", type="primary"):
                    set_user_stations(selected_engineer, new_assigned)
                    st.success(f"Acces mis a jour pour {selected_engineer}.")
                    log_event("rls_updated", {"user": selected_engineer, "stations": new_assigned})

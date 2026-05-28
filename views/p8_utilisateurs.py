from __future__ import annotations

import streamlit as st

from datetime import datetime

from security.middleware import security_middleware

from services.data_service import (
    db_read,
    db_execute,
    db_scalar,
    get_user_stations,
    set_user_stations,
    available_stations,
    log_event,
)

from services.notification_service import (
    send_account_password_email,
    send_account_status_email,
    send_account_deletion_email,
)

from ui.components import header, section

from utils.security import password_hash, generate_temp_password


def render_utilisateurs_panel():

    tab1, tab2, tab3 = st.tabs(["Annuaire", "Ajouter un compte", "Accès stations"])

    with tab1:

        _render_user_list()

    with tab2:

        _render_add_user()

    with tab3:

        _render_station_access()


def page_utilisateurs():

    security_middleware.enforce(role="admin")

    header("Utilisateurs", "Comptes et accès aux stations")

    render_utilisateurs_panel()


def _render_user_list():

    with section("Comptes existants"):

        users_df = db_read("get_all_users")

        if users_df.empty:

            st.info("Aucun utilisateur trouvé.")

            return

        search = st.text_input(
            "Rechercher un utilisateur", placeholder="Identifiant, nom ou courriel…"
        )

        if search:

            users_df = users_df[
                users_df["username"].str.contains(search, case=False, na=False)
                | users_df["display"].str.contains(search, case=False, na=False)
                | users_df["email"].str.contains(search, case=False, na=False)
            ]

        display_df = users_df.copy()

        display_df["Statut"] = display_df["is_active"].apply(
            lambda x: "Actif" if x else "Désactivé"
        )

        display_df["Rôle"] = display_df["role"].apply(
            lambda x: "Administrateur" if x == "admin" else "Ingénieur"
        )

        show_df = display_df.rename(
            columns={
                "username": "Identifiant",
                "display": "Nom affiché",
                "email": "Courriel",
                "created_at": "Créé le",
            }
        )

        st.dataframe(
            show_df[
                ["Identifiant", "Nom affiché", "Courriel", "Rôle", "Statut", "Créé le"]
            ],
            width="stretch",
            hide_index=True,
        )

        st.write("---")

        st.subheader("Actions sur un compte")

        selected_user = st.selectbox(
            "Choisir un utilisateur pour modification",
            [""] + users_df["username"].tolist(),
        )

        if selected_user:

            user_data = users_df[users_df["username"] == selected_user].iloc[0]

            col1, col2, col3 = st.columns(3)

            with col1:

                new_status = 0 if user_data["is_active"] else 1

                label = (
                    "Désactiver le compte"
                    if user_data["is_active"]
                    else "Activer le compte"
                )

                if st.button(label, width="stretch"):

                    db_execute("set_user_active", (new_status, selected_user))

                    log_event(
                        "user_status_changed",
                        {"user": selected_user, "active": new_status},
                    )

                    email = user_data.get("email")

                    if email:

                        ok, msg = send_account_status_email(
                            email,
                            user_data.get("display", ""),
                            selected_user,
                            bool(new_status),
                        )

                        if ok:

                            st.success(f"Statut mis à jour. Courriel envoyé à {email}")

                        else:

                            st.warning(
                                f"Statut mis a jour, mais échec courriel : {msg}"
                            )

                    else:

                        st.success(f"Statut mis a jour pour {selected_user}")

                    st.rerun()

            with col2:

                if st.button("Réinitialiser le mot de passe", width="stretch"):

                    temp_pwd = generate_temp_password()

                    new_hash = password_hash(temp_pwd)

                    db_execute("update_password", (new_hash, 1, selected_user))

                    log_event("password_reset", {"user": selected_user})

                    email = user_data.get("email")

                    if email:

                        ok, msg = send_account_password_email(
                            email, user_data.get("display", ""), selected_user, temp_pwd
                        )

                        if ok:

                            st.success(f"Nouveau mot de passe envoyé à {email}")

                        else:

                            st.error(f"Échec de l'envoi du courriel : {msg}")

                            st.warning(f"Mot de passe temporaire : **{temp_pwd}**")

                    else:

                        st.warning(
                            f"Aucun courriel associé. Mot de passe temporaire : **{temp_pwd}**"
                        )

            with col3:

                if st.button("Supprimer le compte", type="secondary", width="stretch"):

                    st.session_state["pending_delete"] = selected_user

                if st.session_state.get("pending_delete") == selected_user:

                    st.error(f"Êtes-vous sûr de vouloir supprimer {selected_user} ?")

                    col_del1, col_del2 = st.columns(2)

                    with col_del1:

                        if st.button("OUI, SUPPRIMER", type="primary", width="stretch"):

                            if user_data["role"] == "admin":

                                active_admins = db_scalar("count_active_admins")

                                if active_admins <= 1 and user_data["is_active"]:

                                    st.error(
                                        "Impossible de supprimer le dernier administrateur actif."
                                    )

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

    st.success(f"Compte {username} supprimé.")

    st.rerun()


def _render_add_user():

    with section("Créer un nouvel utilisateur"):

        st.caption(
            "Renseignez les informations du compte. Un mot de passe temporaire sera envoyé à l'adresse courriel indiquée."
        )

        with st.form("add_user_form", clear_on_submit=True):

            col1, col2 = st.columns(2)

            with col1:

                new_username = st.text_input(
                    "Identifiant",
                    placeholder="prenom.nom (connexion au tableau de bord)",
                    help="Lettres, chiffres et point — sans espaces.",
                )

                new_display = st.text_input(
                    "Nom complet", placeholder="Prénom Nom (affiché dans l'application)"
                )

                new_email = st.text_input(
                    "Courriel professionnel",
                    placeholder="prenom.nom@tunisietelecom.tn",
                    help="Adresse utilisée pour la connexion et l'envoi du mot de passe.",
                )

            with col2:

                new_role = st.selectbox(
                    "Rôle",
                    ["ingenieur", "admin"],
                    format_func=lambda r: (
                        "Ingénieur réseau" if r == "ingenieur" else "Administrateur"
                    ),
                    help="Les ingénieurs voient uniquement les stations qui leur sont affectées.",
                )

                st.info(
                    "Après création, l'utilisateur reçoit un courriel avec un mot de passe temporaire à changer à la première connexion."
                )

            submit = st.form_submit_button(
                "Créer le compte", type="primary", use_container_width=True
            )

            if submit:

                if not new_username or not new_display:

                    st.error("L'identifiant et le nom complet sont obligatoires.")

                    return

                existing = db_read(
                    "get_user_by_username_or_email", (new_username, new_username)
                )

                if not existing.empty:

                    st.error("Cet identifiant ou ce courriel est déjà utilisé.")

                    return

                if not new_email:

                    st.error(
                        "Le courriel est obligatoire pour l'envoi du mot de passe temporaire."
                    )

                    return

                temp_pwd = generate_temp_password()

                final_hash = password_hash(temp_pwd)

                db_execute(
                    "insert_user",
                    (
                        new_username,
                        new_email,
                        final_hash,
                        new_role,
                        new_display,
                        1,
                        1,
                        datetime.now().isoformat(),
                        st.session_state.get("user"),
                    ),
                )

                log_event("user_created", {"user": new_username, "role": new_role})

                ok, msg = send_account_password_email(
                    new_email, new_display, new_username, temp_pwd
                )

                if ok:

                    st.success(
                        f"Utilisateur {new_username} créé. Le mot de passe temporaire a été envoyé à {new_email}."
                    )

                else:

                    st.success(
                        f"Utilisateur {new_username} créé, mais l'envoi du courriel a échoué."
                    )

                    st.warning(
                        f"Mot de passe temporaire a communiquer manuellement : **{temp_pwd}**"
                    )

                    st.error(f"Raison de l'échec courriel : {msg}")


def _render_station_access():

    with section("Gestion des accès par station"):

        st.caption(
            "Restreindre la visibilité des stations pour les comptes ingénieurs."
        )

        engineers_df = db_read("get_all_engineers")

        if engineers_df.empty:

            st.info("Aucun compte ingénieur trouvé dans le systeme.")

        else:

            engineers = sorted(engineers_df["username"].tolist())

            selected_engineer = st.selectbox(
                "Choisir un ingénieur", [""] + engineers, key="rls_user_sel"
            )

            if selected_engineer:

                current_assigned = get_user_stations(selected_engineer)

                all_dataset_stations = available_stations()

                all_options = sorted(list(set(all_dataset_stations + current_assigned)))

                new_assigned = st.multiselect(
                    f"Stations affectées à {selected_engineer}",
                    options=all_options,
                    default=current_assigned,
                    help="Laissez vide pour retirer tout accès. L'ingénieur ne verra que les stations sélectionnées.",
                )

                if st.button(
                    f"Enregistrer les accès pour {selected_engineer}", type="primary"
                ):

                    set_user_stations(selected_engineer, new_assigned)

                    st.success(f"Accès mis à jour pour {selected_engineer}.")

                    log_event(
                        "rls_updated",
                        {"user": selected_engineer, "stations": new_assigned},
                    )

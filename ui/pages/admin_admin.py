import streamlit as st
from datetime import datetime
from security.middleware import security_middleware
from services.data_service import (
    db_read, db_execute, db_scalar, log_event, available_stations
)
from config.settings import settings
from services.auth_service import generate_temp_password, password_hash, reset_user_password
from services.notification_service import send_account_password_email
from ui.layout import header, section
from utils.validators import UserInputValidator


def save_engineer_assignments(stations: list[str], engineer_user: str = "ing.reseau") -> None:
    engineer_user = engineer_user.strip().lower()
    valid = set(available_stations())
    selected = sorted({str(station) for station in stations if str(station) in valid})
    assigned_by = st.session_state.get("user", "system")
    assigned_at = datetime.now().isoformat(timespec="seconds")
    from services.data_service import db_connect, ALLOWED_QUERIES
    with db_connect() as conn:
        conn.execute(ALLOWED_QUERIES["delete_engineer_assignments"], (engineer_user,))
        conn.executemany(
            ALLOWED_QUERIES["insert_engineer_assignment"],
            [(engineer_user, station_id, assigned_at, assigned_by) for station_id in selected],
        )
        conn.execute(
            ALLOWED_QUERIES["upsert_setting"],
            (f"engineer_assignments_configured:{engineer_user}", "1"),
        )
        conn.commit()


def create_account(email: str, display: str, role: str, temp_password: str | None = None) -> tuple[bool, str, str]:
    email = UserInputValidator.sanitize_string(email, 120).lower()
    display = UserInputValidator.sanitize_string(display, 120)
    if not UserInputValidator.validate_email(email):
        return False, "Email invalide.", ""
    if role not in {"admin", "engineer"}:
        return False, "Role invalide.", ""
    if not display:
        display = email
    if not db_read("get_user_by_username_or_email", (email, email)).empty:
        return False, "Un compte existe deja avec cet email.", ""

    temp_pwd = temp_password or generate_temp_password()
    ok, msg = send_account_password_email(email, display, email, temp_pwd)
    if not ok:
        return False, msg, ""

    try:
        db_execute(
            "insert_user",
            (
                email,
                email,
                password_hash(temp_pwd),
                role,
                display,
                1,
                1,
                datetime.now().isoformat(),
                st.session_state.get("user"),
            ),
        )
    except Exception as exc:
        return False, f"Compte non cree: {exc}", ""
    return True, "Compte cree et mot de passe temporaire envoye.", temp_pwd


def can_change_user(target_username: str) -> tuple[bool, str]:
    current_user = (st.session_state.get("user") or "").strip().lower()
    if not target_username:
        return False, "Selectionnez un compte."
    if target_username.strip().lower() == current_user:
        return False, "Vous ne pouvez pas modifier votre propre compte ici."
    return True, ""


def user_record(username: str) -> dict | None:
    df = db_read("get_user_by_username_or_email", (username, username))
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def can_disable_or_delete_user(username: str) -> tuple[bool, str]:
    ok, message = can_change_user(username)
    if not ok:
        return ok, message
    rec = user_record(username)
    if not rec:
        return False, "Compte introuvable."
    if rec.get("role") == "admin" and rec.get("is_active"):
        active_admins = int(db_scalar("count_active_admins", (), 0) or 0)
        if active_admins <= 1:
            return False, "Impossible de retirer le dernier admin actif."
    return True, ""


def set_account_active(username: str, active: bool) -> tuple[bool, str]:
    if active:
        ok, message = can_change_user(username)
    else:
        ok, message = can_disable_or_delete_user(username)
    if not ok:
        return False, message
    db_execute("set_user_active", (1 if active else 0, username))
    log_event("user_activated" if active else "user_deactivated", {"username": username})
    return True, "Compte reactive." if active else "Compte desactive."


def delete_account(username: str) -> tuple[bool, str]:
    ok, message = can_disable_or_delete_user(username)
    if not ok:
        return False, message
    db_execute("delete_engineer_assignments", (username,))
    db_execute("delete_user", (username,))
    log_event("user_deleted", {"username": username})
    return True, "Compte supprime."


def resend_temp_password(username: str) -> tuple[bool, str]:
    ok, message = can_change_user(username)
    if not ok:
        return False, message
    ok, message = reset_user_password(username)
    if ok:
        log_event("password_reset_resent_by_admin", {"username": username})
    return ok, message


def admin_user_lifecycle():
    section("Gestion des comptes")
    users = db_read("get_all_users")
    if users.empty:
        st.info("Aucun compte disponible.")
        return

    table_cols = ["display", "email", "role", "is_active", "must_change_password", "created_at", "created_by"]
    table_cols = [col for col in table_cols if col in users.columns]
    st.dataframe(users[table_cols], width="stretch", hide_index=True)

    options = {
        f"{row.display} - {row.email} ({row.role})": row.username
        for row in users.itertuples(index=False)
    }
    with st.form("admin_user_lifecycle_form"):
        selected_label = st.selectbox("Compte", list(options.keys()))
        action = st.radio(
            "Action",
            ["Renvoyer mot de passe temporaire", "Desactiver", "Reactiver", "Supprimer"],
            horizontal=True,
        )
        confirm_delete = True
        if action == "Supprimer":
            confirm_delete = st.checkbox("Je confirme la suppression definitive du compte")
        submitted = st.form_submit_button("Executer", type="primary")

    if not submitted:
        return

    username = options.get(selected_label, "")
    if not username and options:
        username = next(iter(options.values()))
    if action == "Renvoyer mot de passe temporaire":
        ok, message = resend_temp_password(username)
    elif action == "Desactiver":
        ok, message = set_account_active(username, False)
    elif action == "Reactiver":
        ok, message = set_account_active(username, True)
    elif confirm_delete:
        ok, message = delete_account(username)
    else:
        ok, message = False, "Confirmation obligatoire avant suppression."

    if ok:
        st.success(message)
        st.rerun()
    else:
        st.error(message)


def admin_admin_accounts():
    section("Gestion des administrateurs")

    with st.expander("Ajouter un admin", expanded=False):
        with st.form("create_admin_account"):
            display = st.text_input("Nom complet", placeholder="Ex: Molka Alaya", key="admin_display")
            email = st.text_input("Email admin", placeholder="prenom.nom@entreprise.tn", key="admin_email")
            created = st.form_submit_button("Creer le compte admin", type="primary")

        if created:
            ok, msg, _ = create_account(email, display, "admin")
            if ok:
                log_event("admin_created", {"email": email})
                st.success(msg)
            else:
                st.error(msg)

    admins = db_read("get_admins")
    if not admins.empty:
        st.dataframe(admins[["display", "email", "is_active", "created_at"]], width="stretch", hide_index=True)


def admin_engineer_accounts():
    stations = available_stations()
    section("Gestion des ingenieurs reseau")
    
    with st.expander("Ajouter un ingenieur", expanded=False):
        with st.form("create_engineer_account"):
            display = st.text_input("Nom complet", placeholder="Ex: Ahmed Ben Ali")
            email = st.text_input("Email professionnel", placeholder="prenom.nom@entreprise.tn")
            selected_stations = st.multiselect("Stations assignees", stations)
            created = st.form_submit_button("Creer le compte", type="primary")
            
        if created:
            ok, msg, _ = create_account(email, display, "engineer")
            if ok:
                save_engineer_assignments(selected_stations, email)
                log_event("engineer_created", {"email": email, "stations": selected_stations})
                st.success(f"Compte cree pour {display}")
            else:
                st.error(msg)
                
    engineers = db_read("get_engineers")
    if not engineers.empty:
        st.dataframe(engineers[["display", "email", "is_active", "created_at"]], width="stretch", hide_index=True)

def admin_config_section():
    section("Configuration des seuils")
    current = st.session_state.get("thresholds", {})
    with st.form("thresholds_config"):
        c1, c2 = st.columns(2)
        with c1:
            eco_score = st.slider("Seuil score ECO", 0.0, 1.0, float(current.get("eco_score", 0.25)), 0.01)
            qos = st.slider("Seuil QoS minimum", 0.0, 1.0, float(current.get("qos", settings.QOS_SEUIL_DEFAULT)), 0.01)
        with c2:
            critique_score = st.slider("Seuil score CRITIQUE", 0.0, 1.0, float(current.get("critique_score", 0.60)), 0.01)
            
        if st.form_submit_button("Enregistrer", type="primary"):
            st.session_state["thresholds"] = {"eco_score": eco_score, "critique_score": critique_score, "qos": qos}
            log_event("thresholds_updated", st.session_state["thresholds"])
            st.success("Seuils mis a jour.")

def admin_admin_page():
    security_middleware.enforce()
    header("Administration", "Gestion du systeme et des utilisateurs")
    
    tab_users, tab_config, tab_audit = st.tabs(["Utilisateurs", "Configuration", "Audit"])
    
    with tab_users:
        admin_user_lifecycle()
        admin_admin_accounts()
        admin_engineer_accounts()
        
    with tab_config:
        admin_config_section()
        
    with tab_audit:
        section("Journal d'audit")
        events = db_read("get_recent_audit_events")
        st.dataframe(events, width="stretch", hide_index=True)

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    db_execute,
    db_read,
    load_outputs,
    load_top_anomalies,
    log_event,
)
from ui.layout import header, section
from ui.utils import download_df_button
from utils.validators import UserInputValidator


STATUSES = ["Nouveau", "En cours", "En attente", "Resolu", "Faux positif", "Escalade"]
PRIORITIES = ["Basse", "Moyenne", "Haute", "Critique"]
TERMINAL_STATUSES = ["Resolu", "Faux positif"]
OPS_SEED_LIMIT = 80


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _future_iso(**delta_kwargs) -> str:
    return (datetime.now() + timedelta(**delta_kwargs)).isoformat(timespec="seconds")


def _safe_index(options: list[str], value: str, default: int = 0) -> int:
    return options.index(value) if value in options else default


def _selected_mapping_value(mapping: dict, selected_label: str):
    if selected_label in mapping:
        return mapping[selected_label]
    return next(iter(mapping.values()))


def _visible_users() -> list[str]:
    users = db_read("get_all_users")
    if users.empty:
        return []
    return users[users["is_active"].astype(int) == 1]["username"].astype(str).tolist()


def _notify(user: str, title: str, body: str = "") -> None:
    if user:
        db_execute("insert_notification", (_now(), user, title, body))


def _seed_ops_from_data() -> None:
    if st.session_state.get("ops_seeded"):
        return
    outputs = st.session_state.get("data", load_outputs())
    decisions = outputs.get("decisions", pd.DataFrame())
    if isinstance(decisions, pd.DataFrame) and not decisions.empty:
        for idx, row in decisions.head(OPS_SEED_LIMIT).iterrows():
            station = str(row.get("station_id", ""))
            action = str(row.get("action_rl", row.get("action_proposee", "Decision NB3")))
            db_execute(
                "upsert_ops_item",
                (
                    str(idx),
                    "decision",
                    station,
                    f"Decision NB3 {action}",
                    "Moyenne",
                    "Nouveau",
                    "",
                    _future_iso(hours=48),
                    _now(),
                    "system",
                ),
            )
    anomalies = load_top_anomalies(OPS_SEED_LIMIT)
    if isinstance(anomalies, pd.DataFrame) and not anomalies.empty:
        for idx, row in anomalies.iterrows():
            score = float(row.get("anomalie_score_ensemble", 0) or 0)
            priority = "Critique" if score >= 0.8 else "Haute" if score >= 0.5 else "Moyenne"
            sla_hours = 24 if priority == "Critique" else 72
            db_execute(
                "upsert_ops_item",
                (
                    str(idx),
                    "alerte",
                    str(row.get("station_id", "")),
                    f"Alerte NB2 score {score:.2f}",
                    priority,
                    "Nouveau",
                    "",
                    _future_iso(hours=sla_hours),
                    _now(),
                    "system",
                ),
            )
    st.session_state["ops_seeded"] = True


def _ops_items_for_role() -> pd.DataFrame:
    _seed_ops_from_data()
    items = db_read("get_ops_items")
    if items.empty:
        return items
    if st.session_state.get("role") == "engineer":
        assigned = set(st.session_state.get("engineer_visible_stations", []))
        if assigned:
            items = items[items["station_id"].astype(str).isin(assigned)]
    return items


def notifications_tab():
    user = st.session_state.get("user", "")
    notes = db_read("get_notifications", (user,))
    with section("Notifications"):
        if notes.empty:
            st.info("Aucune notification.")
            return
        st.dataframe(notes[["created_at", "title", "body", "is_read"]], width="stretch", hide_index=True)
        unread = notes[notes["is_read"].astype(int) == 0]
        if not unread.empty and st.button("Marquer tout comme lu"):
            for nid in unread["id"].tolist():
                db_execute("mark_notification_read", (int(nid), user))
            st.rerun()


def search_tab():
    items = _ops_items_for_role()
    with section("Recherche globale"):
        query = st.text_input("Recherche", placeholder="station, alerte, decision, statut...")
        if items.empty:
            st.info("Aucun element operationnel.")
            return
        out = items.copy()
        if query:
            q = query.lower()
            mask = out.astype(str).apply(lambda col: col.str.lower().str.contains(q, na=False)).any(axis=1)
            out = out[mask]
        st.dataframe(out, width="stretch", hide_index=True)
        download_df_button(out, "recherche_operations.csv", "Exporter resultats")


def workflow_tab():
    items = _ops_items_for_role()
    with section("Statuts, SLA et commentaires"):
        if items.empty:
            st.info("Aucun element operationnel.")
            return
        overdue = pd.to_datetime(items["sla_due_at"], errors="coerce") < pd.Timestamp.now()
        c1, c2, c3 = st.columns(3)
        c1.metric("Ouverts", int(items[~items["status"].isin(TERMINAL_STATUSES)].shape[0]))
        c2.metric("En retard SLA", int(overdue.fillna(False).sum()))
        c3.metric("Critiques", int((items["priority"] == "Critique").sum()))

        labels = {
            f"{row.item_type} #{row.item_ref} - {row.station_id} - {row.title}": (row.item_ref, row.item_type)
            for row in items.itertuples(index=False)
        }
        selected_label = st.selectbox("Element", list(labels.keys()))
        item_ref, item_type = _selected_mapping_value(labels, selected_label)
        current = db_read("get_ops_item", (item_ref, item_type))
        current_row = current.iloc[0].to_dict()

        with st.form("ops_item_update"):
            col1, col2 = st.columns(2)
            with col1:
                status = st.selectbox("Statut", STATUSES, index=_safe_index(STATUSES, current_row.get("status", "Nouveau")))
                priority = st.selectbox(
                    "Priorite",
                    PRIORITIES,
                    index=_safe_index(PRIORITIES, current_row.get("priority", "Moyenne"), 1),
                )
            with col2:
                owner = st.selectbox("Responsable", [""] + _visible_users(), index=0)
                sla_days = st.number_input("SLA restant / nouveau delai en jours", min_value=0, max_value=30, value=2)
            comment = st.text_area("Commentaire")
            notify = st.checkbox("Notifier le responsable", value=True)
            submitted = st.form_submit_button("Enregistrer", type="primary")

        if submitted:
            before = current_row.copy()
            due_at = _future_iso(days=int(sla_days))
            db_execute(
                "upsert_ops_item",
                (
                    item_ref,
                    item_type,
                    current_row.get("station_id", ""),
                    current_row.get("title", ""),
                    priority,
                    status,
                    owner,
                    due_at,
                    _now(),
                    st.session_state.get("user", ""),
                ),
            )
            if comment.strip():
                db_execute(
                    "insert_item_comment",
                    (_now(), st.session_state.get("user", ""), item_ref, item_type, UserInputValidator.sanitize_string(comment, 1000)),
                )
            if notify:
                _notify(owner, f"{item_type} {item_ref} mis a jour", f"Statut: {status} / Priorite: {priority}")
            log_event(
                "ops_item_updated",
                {"before": before, "after": {"status": status, "priority": priority, "owner": owner, "sla_due_at": due_at}},
            )
            st.success("Element mis a jour.")
            st.rerun()

        comments = db_read("get_item_comments", (item_ref, item_type))
        if not comments.empty:
            st.dataframe(comments, width="stretch", hide_index=True)


def tickets_tab():
    items = _ops_items_for_role()
    tickets = db_read("get_tickets")
    with section("Tickets d'intervention"):
        if not tickets.empty:
            st.dataframe(tickets, width="stretch", hide_index=True)
            download_df_button(tickets, "tickets_intervention.csv", "Exporter tickets")
        if items.empty:
            return

        labels = {
            f"{row.item_type} #{row.item_ref} - {row.station_id} - {row.title}": (row.item_ref, row.item_type, row.station_id, row.title)
            for row in items.itertuples(index=False)
        }
        with st.form("create_ticket"):
            selected_label = st.selectbox("Element source", list(labels.keys()), key="ticket_item")
            assignee = st.selectbox("Assigne a", [""] + _visible_users())
            planned_at = st.date_input("Date planifiee")
            checklist = st.text_area("Checklist", placeholder="Verification alimentation\nControle QoS\nRetour NOC")
            submitted = st.form_submit_button("Creer ticket", type="primary")
        if submitted:
            item_ref, item_type, station, title = _selected_mapping_value(labels, selected_label)
            db_execute(
                "insert_ticket",
                (
                    _now(),
                    st.session_state.get("user", ""),
                    item_ref,
                    item_type,
                    station,
                    title,
                    assignee,
                    str(planned_at),
                    "Planifie",
                    checklist,
                    "",
                ),
            )
            _notify(assignee, "Nouveau ticket d'intervention", title)
            log_event("ticket_created", {"item_ref": item_ref, "item_type": item_type, "assignee": assignee})
            st.success("Ticket cree.")
            st.rerun()


def reports_sessions_tab():
    items = _ops_items_for_role()
    tickets = db_read("get_tickets")
    with section("Rapports"):
        statuses = items.get("status", pd.Series(dtype=str)) if not items.empty else pd.Series(dtype=str)
        sla_values = items.get("sla_due_at", pd.Series(dtype=str)) if not items.empty else pd.Series(dtype=str)
        report = {
            "generated_at": _now(),
            "open_items": int((~statuses.isin(TERMINAL_STATUSES)).sum()) if not items.empty else 0,
            "tickets": int(len(tickets)),
            "sla_late": int((pd.to_datetime(sla_values, errors="coerce") < pd.Timestamp.now()).sum()) if not items.empty else 0,
        }
        st.json(report)
        st.download_button(
            "Exporter rapport JSON",
            data=json.dumps(report, ensure_ascii=False, indent=2),
            file_name="rapport_operations.json",
            mime="application/json",
        )
        if not items.empty:
            download_df_button(items, "items_operations.csv", "Exporter operations CSV")
    if st.session_state.get("role") == "admin":
        with section("Sessions actives"):
            sessions = db_read("get_user_sessions")
            st.dataframe(sessions, width="stretch", hide_index=True)


def operations_page():
    security_middleware.enforce()
    role = st.session_state.get("role")
    # Only admin can access operations center
    if role != "admin":
        st.error("Acces refuse. Le Centre operations est reserve aux administrateurs.")
        return
    
    header("Centre operations", "Recherche, SLA, tickets, notifications et rapports")
    tabs = st.tabs(["Recherche", "Workflow", "Tickets", "Notifications", "Rapports"])
    with tabs[0]:
        search_tab()
    with tabs[1]:
        workflow_tab()
    with tabs[2]:
        tickets_tab()
    with tabs[3]:
        notifications_tab()
    with tabs[4]:
        reports_sessions_tab()

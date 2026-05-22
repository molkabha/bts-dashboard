"""Page 7 - Configuration (Admin uniquement)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    artifact_inventory,
    available_stations, db_execute, db_scalar, log_event,
    load_filtered_main_data,
)
from ui.components import header, section


DEFAULT_THRESHOLDS = {
    "qos_min_eco": 0.60,
    "anomalie_critique": 0.60,
    "cpu_max_eco": 50,
    "heure_nuit_debut": 22,
    "heure_nuit_fin": 6,
    "seuil_charge_voix_sleep": 0.15,
    "rl_episodes": 500,
    "rl_alpha": 0.10,
    "rl_gamma": 0.95,
    "rl_epsilon": 0.50,
}


def _load_config() -> dict:
    stored = db_scalar("get_setting", ("dashboard_config",), None)
    if stored:
        try:
            return json.loads(stored)
        except Exception:
            pass
    return dict(DEFAULT_THRESHOLDS)


def _save_config(config: dict):
    db_execute("upsert_setting", ("dashboard_config", json.dumps(config)))
    st.session_state["dashboard_config"] = config
    log_event("config_updated", config)


def page_configuration():
    security_middleware.enforce()
    role = st.session_state.get("role")
    if role != "admin":
        st.error("Acces refuse. Cette page est reservee aux administrateurs.")
        return

    header("Configuration", "Parametres du systeme et seuils de decision")
    config = _load_config()

    # Section 1 - Decision thresholds
    with section("Seuils du Moteur de Decision"):
        st.caption("Ces seuils controlent les modes operationnels ECO / NORMAL / ATTENTION / CRITIQUE.")

        c1, c2 = st.columns(2)
        with c1:
            qos_min = st.slider("Seuil QoS minimum pour mode ECO", 0.0, 1.0,
                                float(config.get("qos_min_eco", 0.60)), 0.01, key="cfg_qos")
            st.caption("En dessous de ce score, la station ne peut pas passer en ECO pour proteger la qualite reseau.")
        with c2:
            anom_crit = st.slider("Seuil score anomalie CRITIQUE", 0.0, 1.0,
                                  float(config.get("anomalie_critique", 0.60)), 0.01, key="cfg_anom")

        cpu_eco = st.slider("Seuil CPU maximum pour mode ECO", 0, 100,
                            int(config.get("cpu_max_eco", 50)), key="cfg_cpu")

        # Preview impact
        cols = ["consommation_kwh", "score_qos", "anomalie_score_ensemble", "charge_cpu_pct", "heure"]
        df = load_filtered_main_data(cols)
        if not df.empty and "score_qos" in df.columns:
            qos_vals = pd.to_numeric(df["score_qos"], errors="coerce").fillna(1)
            cpu_vals = pd.to_numeric(
                df.get(
                    "charge_cpu_pct",
                    pd.Series(
                        50,
                        index=df.index)),
                errors="coerce").fillna(50)
            anom_vals = pd.to_numeric(
                df.get(
                    "anomalie_score_ensemble",
                    pd.Series(
                        0,
                        index=df.index)),
                errors="coerce").fillna(0)
            pct_eco = ((qos_vals >= qos_min) & (cpu_vals < cpu_eco) & (anom_vals < 0.25)).mean() * 100
            st.info(f"Avec ces seuils, {pct_eco:.1f}% des observations seraient eligibles au mode ECO.")

    # Section 2 - Optimization strategies
    with section("Parametres des Strategies d'Optimisation"):
        c1, c2 = st.columns(2)
        with c1:
            nuit_debut = st.slider("Heure debut fenetre nocturne", 20, 23,
                                   int(config.get("heure_nuit_debut", 22)), key="cfg_nuit_deb")
            seuil_voix = st.slider("Seuil charge voix pour sleep mode", 0.10, 0.40,
                                   float(config.get("seuil_charge_voix_sleep", 0.15)), 0.01, key="cfg_voix")
        with c2:
            nuit_fin = st.slider("Heure fin fenetre nocturne", 4, 8,
                                 int(config.get("heure_nuit_fin", 6)), key="cfg_nuit_fin")

        st.markdown("**Strategies actives**")
        sc1, sc2, sc3, sc4 = st.columns(4)
        with sc1:
            strat_sleep = st.toggle("Sleep mode", value=config.get("strat_sleep", True), key="cfg_strat_sleep")
        with sc2:
            strat_puissance = st.toggle(
                "Reduction puissance", value=config.get(
                    "strat_puissance", True), key="cfg_strat_puiss")
        with sc3:
            strat_cooling = st.toggle("Free cooling", value=config.get("strat_cooling", True), key="cfg_strat_cool")
        with sc4:
            strat_calendaire = st.toggle(
                "Mode calendaire", value=config.get(
                    "strat_calendaire", True), key="cfg_strat_cal")

    # Section 3 - RL parameters
    with st.expander("Parametres RL avances", expanded=False):
        st.caption("Ces parametres s'appliquent au prochain relancement du pipeline.")
        c1, c2 = st.columns(2)
        with c1:
            rl_episodes = st.slider("Nombre d'episodes", 100, 2000,
                                    int(config.get("rl_episodes", 500)), key="cfg_rl_ep")
            rl_alpha = st.slider("Taux d'apprentissage (alpha)", 0.01, 0.50,
                                 float(config.get("rl_alpha", 0.10)), 0.01, key="cfg_rl_alpha")
        with c2:
            rl_gamma = st.slider("Facteur de decompte (gamma)", 0.80, 0.99,
                                 float(config.get("rl_gamma", 0.95)), 0.01, key="cfg_rl_gamma")
            rl_epsilon = st.slider("Epsilon initial (exploration)", 0.10, 1.00,
                                   float(config.get("rl_epsilon", 0.50)), 0.01, key="cfg_rl_eps")

    # Section 4 - Station management
    with section("Gestion des Stations"):
        all_stations = available_stations()
        if all_stations:
            inactive = set(config.get("inactive_stations", []))
            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("Tout activer", width="stretch"):
                    inactive = set()
            with bc2:
                if st.button("Tout desactiver", width="stretch"):
                    inactive = set(all_stations)

            station_statuses = []
            for s in all_stations:
                station_statuses.append({"Station": s, "Actif": s not in inactive})
            sdf = pd.DataFrame(station_statuses)
            edited = st.data_editor(sdf, width="stretch", hide_index=True,
                                    column_config={"Actif": st.column_config.CheckboxColumn()},
                                    key="station_editor")
            if edited is not None:
                inactive = set(edited[~edited["Actif"]]["Station"].tolist())
        else:
            inactive = set()
            st.info("Aucune station disponible.")

    # Section 4.5 - RLS Access Management
    # (Moved to 'Gestion Utilisateurs' page for better centralized admin)

    # Section 5 - Save & Export/Import
    with section("Enregistrer la Configuration"):
        if st.button("Enregistrer tous les parametres", type="primary", width="stretch"):
            new_config = {
                "qos_min_eco": qos_min,
                "anomalie_critique": anom_crit,
                "cpu_max_eco": cpu_eco,
                "heure_nuit_debut": nuit_debut,
                "heure_nuit_fin": nuit_fin,
                "seuil_charge_voix_sleep": seuil_voix,
                "strat_sleep": strat_sleep,
                "strat_puissance": strat_puissance,
                "strat_cooling": strat_cooling,
                "strat_calendaire": strat_calendaire,
                "rl_episodes": rl_episodes,
                "rl_alpha": rl_alpha,
                "rl_gamma": rl_gamma,
                "rl_epsilon": rl_epsilon,
                "inactive_stations": sorted(inactive),
            }
            _save_config(new_config)
            st.success("Configuration enregistree.")
            st.toast("Configuration sauvegardee avec succes.")

    with section("Export / Import Configuration"):
        c1, c2, c3 = st.columns(3)
        with c1:
            config_json = json.dumps(config, indent=2, ensure_ascii=False)
            st.download_button("Exporter config JSON", data=config_json,
                               file_name="config_bts.json", mime="application/json",
                               width="stretch")
        with c2:
            uploaded_cfg = st.file_uploader("Importer config JSON", type=["json"], key="import_cfg")
            if uploaded_cfg is not None:
                try:
                    imported = json.loads(uploaded_cfg.read().decode("utf-8"))
                    _save_config(imported)
                    st.success("Configuration importee.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur d'import : {e}")
        with c3:
            if st.button("Restaurer les valeurs par defaut", width="stretch"):
                _save_config(dict(DEFAULT_THRESHOLDS))
                st.success("Valeurs par defaut restaurees.")
                st.rerun()

    with st.expander("Inventaire artefacts Hugging Face", expanded=False):
        inv = artifact_inventory()
        st.dataframe(inv, width="stretch", hide_index=True,
                     column_config={"lien_hf": st.column_config.LinkColumn("Lien HF")})

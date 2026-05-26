"""Page 12 - Configuration (stations et utilisateurs)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from security.middleware import security_middleware
from services.data_service import (
    all_dataset_station_ids,
    dataset_cache_key,
    load_enriched_base_dataset,
    load_inactive_stations,
    log_event,
    save_inactive_stations,
    station_summary_from_df,
)
from ui.components import header, kpi_card, section
from views.p8_utilisateurs import render_utilisateurs_panel


def _station_inventory() -> pd.DataFrame:
    """Build station list with metadata from the active dataset."""
    all_ids = all_dataset_station_ids()
    if not all_ids:
        return pd.DataFrame()

    inactive = load_inactive_stations()
    base = pd.DataFrame({"Station": all_ids})
    base["Actif"] = ~base["Station"].isin(inactive)

    df = load_enriched_base_dataset(dataset_cache_key())
    if not df.empty:
        use_cols = [c for c in [
            "station_id", "gouvernorat", "technologie", "type_zone", "mode_operation", "consommation_kwh",
        ] if c in df.columns]
        df = df[use_cols] if use_cols else df
    if df.empty or "station_id" not in df.columns:
        return base.sort_values("Station").reset_index(drop=True)

    summary = station_summary_from_df(df)
    if summary.empty or "station_id" not in summary.columns:
        return base.sort_values("Station").reset_index(drop=True)

    meta = summary.copy()
    meta["Station"] = meta["station_id"].astype(str)
    keep = ["Station"]
    rename = {}
    if "gouvernorat" in meta.columns:
        keep.append("gouvernorat")
        rename["gouvernorat"] = "Gouvernorat"
    if "technologie" in meta.columns:
        keep.append("technologie")
        rename["technologie"] = "Technologie"
    if "type_zone" in meta.columns:
        keep.append("type_zone")
        rename["type_zone"] = "Zone"
    if "mode_operation" in meta.columns:
        keep.append("mode_operation")
        rename["mode_operation"] = "Mode"
    if "conso_moy" in meta.columns:
        keep.append("conso_moy")
        rename["conso_moy"] = "Conso moy. (kWh)"

    meta = meta[keep].rename(columns=rename)
    if "Conso moy. (kWh)" in meta.columns:
        meta["Conso moy. (kWh)"] = pd.to_numeric(meta["Conso moy. (kWh)"], errors="coerce").round(2)

    merged = base.merge(meta.drop_duplicates("Station"), on="Station", how="left")
    return merged.sort_values("Station").reset_index(drop=True)


def _render_stations_tab():
    inventory = _station_inventory()
    if inventory.empty:
        st.warning(
            "Aucune station dans le jeu de données actif. "
            "Vérifiez les artefacts NB publiés sur Hugging Face."
        )
        return

    inactive = load_inactive_stations()
    total = len(inventory)
    active_count = int(inventory["Actif"].sum()) if "Actif" in inventory.columns else total
    inactive_count = total - active_count

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card("Stations (jeu de données)", str(total), "Parc de référence", "blue")
    with k2:
        kpi_card("Actives", str(active_count), "Visibles dans le tableau de bord", "green")
    with k3:
        kpi_card("Désactivées", str(inactive_count), "Exclues des filtres et cartes", "orange")

    st.caption(
        "Les stations désactivées sont masquées pour tous les utilisateurs. "
        "Les accès par ingénieur se gèrent dans l'onglet Utilisateurs."
    )

    with section("Parc stations"):
        search = st.text_input("Rechercher", placeholder="ID station, gouvernorat, technologie…", key="cfg_station_search")

        filtered = inventory.copy()
        if search.strip():
            mask = False
            for col in filtered.columns:
                if col == "Actif":
                    continue
                mask = mask | filtered[col].astype(str).str.contains(search.strip(), case=False, na=False)
            filtered = filtered[mask]

        bc1, bc2, bc3 = st.columns(3)
        with bc1:
            if st.button("Tout activer", use_container_width=True):
                st.session_state["cfg_station_table"] = inventory.assign(Actif=True)
                st.rerun()
        with bc2:
            if st.button("Tout désactiver", use_container_width=True):
                st.session_state["cfg_station_table"] = inventory.assign(Actif=False)
                st.rerun()
        with bc3:
            show_inactive_only = st.checkbox("Voir seulement désactivées", value=False, key="cfg_inactive_only")

        table_data = st.session_state.get("cfg_station_table", filtered)
        if not isinstance(table_data, pd.DataFrame) or table_data.empty:
            table_data = filtered
        if show_inactive_only and "Actif" in table_data.columns:
            table_data = table_data[~table_data["Actif"]]

        column_config = {
            "Actif": st.column_config.CheckboxColumn("Activée", help="Décochez pour masquer la station"),
            "Station": st.column_config.TextColumn("Station", disabled=True),
        }
        for col in ("Gouvernorat", "Technologie", "Zone", "Mode"):
            if col in table_data.columns:
                column_config[col] = st.column_config.TextColumn(col, disabled=True)
        if "Conso moy. (kWh)" in table_data.columns:
            column_config["Conso moy. (kWh)"] = st.column_config.NumberColumn(
                "Conso moy. (kWh)", format="%.2f", disabled=True,
            )

        edited = st.data_editor(
            table_data,
            column_config=column_config,
            hide_index=True,
            use_container_width=True,
            key="cfg_station_editor",
        )

        if st.button("Enregistrer", type="primary", use_container_width=False):
            if edited is None or edited.empty:
                save_inactive_stations([])
            else:
                new_inactive = edited.loc[~edited["Actif"].astype(bool), "Station"].astype(str).tolist()
                save_inactive_stations(new_inactive)
            st.session_state.pop("cfg_station_table", None)
            st.cache_data.clear()
            st.session_state.pop("_df_session_key", None)
            st.session_state.pop("_df_session_val", None)
            log_event("station_parc_saved", {"inactive": len(load_inactive_stations())})
            st.success("Parc stations enregistré. Les vues du tableau de bord sont à jour.")
            st.rerun()


def page_configuration():
    security_middleware.enforce(role="admin")
    header("Configuration", "Stations et utilisateurs")

    tab_stations, tab_users = st.tabs(["Stations", "Utilisateurs"])

    with tab_stations:
        _render_stations_tab()

    with tab_users:
        render_utilisateurs_panel()

"""Repository for station data access."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from models.station import Station, StationSummary
from utils.error_handler import AppError, ErrorCode
from utils.validators import UserInputValidator
from config.settings import settings


class StationRepository:
    """
    Repository for station data operations.
    Handles persistence and retrieval of station records from SQLite.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize repository with database path.
        
        Args:
            db_path: Optional override for the database file path.
        """
        self.db_path = db_path or settings.DB_PATH
        self._ensure_tables()
    
    def _ensure_tables(self) -> None:
        """
        Ensure required tables exist in the database.
        
        Raises:
            AppError: If table creation fails.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS stations (
                        station_id TEXT PRIMARY KEY,
                        technologie TEXT NOT NULL,
                        gouvernorat TEXT NOT NULL,
                        type_zone TEXT NOT NULL,
                        latitude REAL,
                        longitude REAL,
                        consommation_kwh REAL,
                        conso_predite REAL,
                        score_qos REAL,
                        anomalie_score_ensemble REAL,
                        heure INTEGER,
                        mois INTEGER,
                        jour_semaine INTEGER,
                        est_weekend INTEGER,
                        est_ramadan INTEGER,
                        est_ferie INTEGER,
                        charge_cpu_pct REAL,
                        taux_charge_voix REAL,
                        taux_charge_data REAL,
                        nb_utilisateurs_actifs INTEGER,
                        nb_secteurs_actifs INTEGER,
                        puissance_emission_dbm REAL,
                        temperature_ambiante REAL,
                        humidite_relative_pct REAL,
                        vitesse_vent_ms REAL,
                        rayonnement_solaire_wm2 REAL,
                        precipitation_mmh REAL,
                        pression_atmospherique_hpa REAL,
                        indice_uv REAL,
                        efficacite_free_cooling REAL,
                        mode_operation TEXT,
                        priorite INTEGER,
                        action_principale TEXT,
                        action_proposee TEXT,
                        action_rl TEXT,
                        economie_estimee_kwh REAL,
                        economie_rl_kwh REAL,
                        risque_qos TEXT,
                        violation_rl INTEGER,
                        timestamp TEXT,
                        created_at TEXT,
                        updated_at TEXT
                    )
                """)
                conn.commit()
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_CONNECTION_ERROR,
                message=f"Échec de la création des tables: {e}",
                original_exception=e,
            )
    
    def _row_to_station(self, row: sqlite3.Row) -> Station:
        """
        Convert database row to Station object.
        
        Args:
            row: SQLite Row object.
            
        Returns:
            Station instance.
        """
        return Station(
            station_id=row["station_id"],
            technologie=row["technologie"],
            gouvernorat=row["gouvernorat"],
            type_zone=row["type_zone"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            consommation_kwh=row["consommation_kwh"],
            conso_predite=row["conso_predite"],
            score_qos=row["score_qos"],
            anomalie_score_ensemble=row["anomalie_score_ensemble"],
            heure=row["heure"],
            mois=row["mois"],
            jour_semaine=row["jour_semaine"],
            est_weekend=row["est_weekend"],
            est_ramadan=row["est_ramadan"],
            est_ferie=row["est_ferie"],
            charge_cpu_pct=row["charge_cpu_pct"],
            taux_charge_voix=row["taux_charge_voix"],
            taux_charge_data=row["taux_charge_data"],
            nb_utilisateurs_actifs=row["nb_utilisateurs_actifs"],
            nb_secteurs_actifs=row["nb_secteurs_actifs"],
            puissance_emission_dbm=row["puissance_emission_dbm"],
            temperature_ambiante=row["temperature_ambiante"],
            humidite_relative_pct=row["humidite_relative_pct"],
            vitesse_vent_ms=row["vitesse_vent_ms"],
            rayonnement_solaire_wm2=row["rayonnement_solaire_wm2"],
            precipitation_mmh=row["precipitation_mmh"],
            pression_atmospherique_hpa=row["pression_atmospherique_hpa"],
            indice_uv=row["indice_uv"],
            efficacite_free_cooling=row["efficacite_free_cooling"],
            mode_operation=row["mode_operation"],
            priorite=row["priorite"],
            action_principale=row["action_principale"],
            action_proposee=row["action_proposee"],
            action_rl=row["action_rl"],
            economie_estimee_kwh=row["economie_estimee_kwh"],
            economie_rl_kwh=row["economie_rl_kwh"],
            risque_qos=row["risque_qos"],
            violation_rl=bool(row["violation_rl"]),
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )
    
    def create(self, station: Station) -> Station:
        """
        Create a new station record.
        
        Args:
            station: Station object to persist.
            
        Returns:
            The created Station object.
            
        Raises:
            AppError: If creation fails or station already exists.
        """
        try:
            UserInputValidator.validate_no_sql_injection(station.station_id)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO stations (
                        station_id, technologie, gouvernorat, type_zone,
                        latitude, longitude, consommation_kwh, conso_predite,
                        score_qos, anomalie_score_ensemble, heure, mois,
                        jour_semaine, est_weekend, est_ramadan, est_ferie,
                        charge_cpu_pct, taux_charge_voix, taux_charge_data,
                        nb_utilisateurs_actifs, nb_secteurs_actifs,
                        puissance_emission_dbm, temperature_ambiante,
                        humidite_relative_pct, vitesse_vent_ms,
                        rayonnement_solaire_wm2, precipitation_mmh,
                        pression_atmospherique_hpa, indice_uv,
                        efficacite_free_cooling, mode_operation, priorite,
                        action_principale, action_proposee, action_rl,
                        economie_estimee_kwh, economie_rl_kwh, risque_qos,
                        violation_rl, timestamp, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    station.station_id, station.technologie, station.gouvernorat,
                    station.type_zone, station.latitude, station.longitude,
                    station.consommation_kwh, station.conso_predite,
                    station.score_qos, station.anomalie_score_ensemble,
                    station.heure, station.mois, station.jour_semaine,
                    station.est_weekend, station.est_ramadan, station.est_ferie,
                    station.charge_cpu_pct, station.taux_charge_voix,
                    station.taux_charge_data, station.nb_utilisateurs_actifs,
                    station.nb_secteurs_actifs, station.puissance_emission_dbm,
                    station.temperature_ambiante, station.humidite_relative_pct,
                    station.vitesse_vent_ms, station.rayonnement_solaire_wm2,
                    station.precipitation_mmh, station.pression_atmospherique_hpa,
                    station.indice_uv, station.efficacite_free_cooling,
                    station.mode_operation, station.priorite,
                    station.action_principale, station.action_proposee,
                    station.action_rl, station.economie_estimee_kwh,
                    station.economie_rl_kwh, station.risque_qos,
                    int(station.violation_rl) if station.violation_rl else 0,
                    station.timestamp.isoformat() if station.timestamp else None,
                    station.created_at.isoformat() if station.created_at else datetime.utcnow().isoformat(),
                    station.updated_at.isoformat() if station.updated_at else datetime.utcnow().isoformat(),
                ))
                conn.commit()
            
            return station
            
        except sqlite3.IntegrityError as e:
            raise AppError(
                code=ErrorCode.DB_INTEGRITY_ERROR,
                message=f"La station existe déjà: {station.station_id}",
                original_exception=e,
            )
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la création de la station: {e}",
                original_exception=e,
            )
    
    def get_by_id(self, station_id: str) -> Optional[Station]:
        """
        Get station by ID.
        
        Args:
            station_id: Unique identifier of the station.
            
        Returns:
            Station instance or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM stations WHERE station_id = ?",
                    (station_id,)
                )
                row = cursor.fetchone()
                return self._row_to_station(row) if row else None
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération de la station: {e}",
                original_exception=e,
            )
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[Station]:
        """
        Get all stations with pagination.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            
        Returns:
            List of Station instances.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM stations LIMIT ? OFFSET ?",
                    (limit, offset)
                )
                return [self._row_to_station(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération des stations: {e}",
                original_exception=e,
            )
    
    def update(self, station_id: str, station_data: dict) -> Optional[Station]:
        """
        Update station by ID.
        
        Args:
            station_id: ID of the station to update.
            station_data: Dictionary of fields to update.
            
        Returns:
            The updated Station object or None if not found.
        """
        try:
            # Validate input
            UserInputValidator.validate_no_sql_injection(station_id)
            
            # Build update query dynamically
            valid_fields = {f.name for f in Station.__dataclass_fields__.values()}
            updates = []
            params = []
            
            for key, value in station_data.items():
                if key in valid_fields and key != "station_id":
                    updates.append(f"{key} = ?")
                    params.append(value)
            
            if not updates:
                raise AppError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Aucun champ valide à mettre à jour",
                )
            
            params.append(station_id)
            query = f"UPDATE stations SET {', '.join(updates)}, updated_at = ? WHERE station_id = ?"
            params.append(datetime.utcnow().isoformat())
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                conn.commit()
                
                if cursor.rowcount == 0:
                    return None
                
                return self.get_by_id(station_id)
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la mise à jour de la station: {e}",
                original_exception=e,
            )
    
    def delete(self, station_id: str) -> bool:
        """
        Delete station by ID.
        
        Args:
            station_id: ID of the station to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        try:
            UserInputValidator.validate_no_sql_injection(station_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM stations WHERE station_id = ?",
                    (station_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la suppression de la station: {e}",
                original_exception=e,
            )
    
    def get_critical_stations(self, threshold: float = 0.6) -> List[Station]:
        """
        Get stations with high anomaly scores.
        
        Args:
            threshold: Minimum anomaly score to consider a station critical.
            
        Returns:
            List of Station instances.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM stations WHERE anomalie_score_ensemble >= ?",
                    (threshold,)
                )
                return [self._row_to_station(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération des stations critiques: {e}",
                original_exception=e,
            )
    
    def get_summary(self, station_id: str) -> Optional[StationSummary]:
        """
        Get station summary statistics.
        
        Args:
            station_id: ID of the station.
            
        Returns:
            StationSummary instance or None if not found.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                    SELECT 
                        station_id, gouvernorat, technologie, type_zone,
                        AVG(consommation_kwh) as conso_moy,
                        AVG(score_qos) as score_qos_moy,
                        AVG(anomalie_score_ensemble) as score_anom_moy,
                        MAX(anomalie_score_ensemble) as score_criticite,
                        CASE 
                            WHEN MAX(anomalie_score_ensemble) >= 0.6 THEN 'Critique'
                            WHEN MAX(anomalie_score_ensemble) >= 0.25 THEN 'Moyenne'
                            ELSE 'Faible'
                        END as categorie,
                        AVG(latitude) as latitude,
                        AVG(longitude) as longitude,
                        SUM(economie_estimee_kwh) as economie_estimee_kwh,
                        SUM(economie_rl_kwh) as economie_rl_kwh
                    FROM stations
                    WHERE station_id = ?
                    GROUP BY station_id, gouvernorat, technologie, type_zone
                """, (station_id,))
                
                row = cursor.fetchone()
                if row:
                    return StationSummary(
                        station_id=row["station_id"],
                        gouvernorat=row["gouvernorat"],
                        technologie=row["technologie"],
                        type_zone=row["type_zone"],
                        conso_moy=row["conso_moy"] or 0,
                        score_qos_moy=row["score_qos_moy"] or 0,
                        score_anom_moy=row["score_anom_moy"] or 0,
                        score_criticite=row["score_criticite"] or 0,
                        categorie=row["categorie"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        economie_estimee_kwh=row["economie_estimee_kwh"],
                        economie_rl_kwh=row["economie_rl_kwh"],
                    )
                return None
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération du résumé de la station: {e}",
                original_exception=e,
            )
    
    def bulk_insert(self, stations: List[Station]) -> Tuple[int, int]:
        """
        Bulk insert stations. 
        
        Args:
            stations: List of Station objects.
            
        Returns:
            Tuple of (success_count, error_count).
        """
        success_count = 0
        error_count = 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                for station in stations:
                    try:
                        self.create(station)
                        success_count += 1
                    except AppError:
                        error_count += 1
                
                conn.commit()
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de l'insertion en masse: {e}",
                original_exception=e,
            )
        
        return success_count, error_count
    
    def search(self, query: str, limit: int = 50) -> List[Station]:
        """
        Search stations by ID or gouvernorat.
        
        Args:
            query: Search string.
            limit: Maximum records to return.
            
        Returns:
            List of Station instances.
        """
        try:
            UserInputValidator.validate_no_sql_injection(query)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM stations 
                    WHERE station_id LIKE ? OR gouvernorat LIKE ?
                    LIMIT ?
                    """,
                    (f"%{query}%", f"%{query}%", limit)
                )
                return [self._row_to_station(row) for row in cursor.fetchall()]
                
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la recherche de stations: {e}",
                original_exception=e,
            )

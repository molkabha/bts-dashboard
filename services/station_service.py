"""Service layer for station business logic."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from models.station import Station, StationSummary
from repositories.station_repository import StationRepository
from utils.error_handler import AppError, ErrorCode
from utils.validators import StationDataValidator, UserInputValidator
from config.settings import settings


class StationService:
    """Service for station business logic operations."""
    
    def __init__(self, repository: Optional[StationRepository] = None):
        """Initialize service with repository."""
        self.repository = repository or StationRepository()
    
    def create_station(self, station_data: dict) -> Station:
        """
        Create a new station with validation.
        """
        try:
            # Validate input data
            validated_data = self._validate_station_data(station_data)
            
            # Check for duplicate
            existing = self.repository.get_by_id(validated_data["station_id"])
            if existing:
                raise AppError(
                    code=ErrorCode.VALIDATION_DUPLICATE,
                    message=f"La station existe déjà: {validated_data['station_id']}",
                )
            
            # Create station object
            station = Station.from_dict(validated_data)
            station.created_at = datetime.utcnow()
            station.updated_at = datetime.utcnow()
            
            # Save to repository
            return self.repository.create(station)
            
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=f"Échec de la création de la station: {e}",
                original_exception=e,
            )
    
    def get_station(self, station_id: str) -> Optional[Station]:
        """
        Get station by ID.
        """
        try:
            UserInputValidator.validate_no_sql_injection(station_id)
            return self.repository.get_by_id(station_id)
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération de la station: {e}",
                original_exception=e,
            )
    
    def update_station(self, station_id: str, update_data: dict) -> Optional[Station]:
        """
        Update station with validation.
        """
        try:
            # Validate station ID
            UserInputValidator.validate_no_sql_injection(station_id)
            
            # Validate update data
            validated_data = self._validate_station_data(update_data, partial=True)
            
            # Check if station exists
            existing = self.repository.get_by_id(station_id)
            if not existing:
                return None
            
            # Update station
            updated = self.repository.update(station_id, validated_data)
            if not updated:
                raise AppError(
                    code=ErrorCode.DB_QUERY_ERROR,
                    message=f"Échec de la mise à jour de la station: {station_id}",
                )
            
            return updated
            
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=f"Échec de la mise à jour de la station: {e}",
                original_exception=e,
            )
    
    def delete_station(self, station_id: str) -> bool:
        """
        Delete station by ID.
        """
        try:
            UserInputValidator.validate_no_sql_injection(station_id)
            return self.repository.delete(station_id)
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la suppression de la station: {e}",
                original_exception=e,
            )
    
    def list_stations(
        self,
        limit: int = 100,
        offset: int = 0,
        technologie: Optional[str] = None,
        gouvernorat: Optional[str] = None,
        type_zone: Optional[str] = None,
        is_critical: Optional[bool] = None,
    ) -> List[Station]:
        """
        List stations with optional filters.
        """
        try:
            # Get all stations
            stations = self.repository.get_all(limit=limit, offset=offset)
            
            # Apply filters
            if technologie:
                stations = [s for s in stations if s.technologie == technologie]
            if gouvernorat:
                stations = [s for s in stations if s.gouvernorat == gouvernorat]
            if type_zone:
                stations = [s for s in stations if s.type_zone == type_zone]
            if is_critical is not None:
                stations = [s for s in stations if s.is_critical == is_critical]
            
            return stations
            
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération des stations: {e}",
                original_exception=e,
            )
    
    def get_critical_stations(self, threshold: float = 0.6) -> List[Station]:
        """
        Get stations with high anomaly scores.
        """
        try:
            return self.repository.get_critical_stations(threshold)
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération des stations critiques: {e}",
                original_exception=e,
            )
    
    def get_station_summary(self, station_id: str) -> Optional[StationSummary]:
        """
        Get station summary statistics.
        """
        try:
            UserInputValidator.validate_no_sql_injection(station_id)
            return self.repository.get_summary(station_id)
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la récupération du résumé de la station: {e}",
                original_exception=e,
            )
    
    def bulk_create_stations(self, stations_data: List[dict]) -> tuple[int, int]:
        """
        Bulk create stations.
        """
        try:
            stations = []
            for data in stations_data:
                try:
                    validated_data = self._validate_station_data(data)
                    station = Station.from_dict(validated_data)
                    station.created_at = datetime.utcnow()
                    station.updated_at = datetime.utcnow()
                    stations.append(station)
                except (AppError, ValueError):
                    continue
            
            return self.repository.bulk_insert(stations)
            
        except Exception as e:
            raise AppError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=f"Échec de l'insertion en masse: {e}",
                original_exception=e,
            )
    
    def search_stations(self, query: str, limit: int = 50) -> List[Station]:
        """
        Search stations by ID or gouvernorat.
        """
        try:
            UserInputValidator.validate_no_sql_injection(query)
            return self.repository.search(query, limit)
        except sqlite3.Error as e:
            raise AppError(
                code=ErrorCode.DB_QUERY_ERROR,
                message=f"Échec de la recherche de stations: {e}",
                original_exception=e,
            )
    
    def _validate_station_data(
        self,
        data: dict,
        partial: bool = False,
    ) -> dict:
        """
        Validate station data.
        """
        try:
            if partial:
                validated = {}
                for key, value in data.items():
                    if value is not None:
                        # Simple check for now, can be improved with Pydantic
                        validated[key] = value
                return validated
            else:
                validator = StationDataValidator(**data)
                return validator.dict(exclude_unset=True)
                
        except ValueError as e:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Échec de la validation: {e}",
            )
        except Exception as e:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Données de station invalides: {e}",
            )
    
    def calculate_energy_savings(self, station_id: str) -> dict:
        """
        Calculate potential energy savings for a station.
        """
        station = self.get_station(station_id)
        if not station:
            raise AppError(
                code=ErrorCode.DB_RECORD_NOT_FOUND,
                message=f"Station non trouvée: {station_id}",
            )
        
        savings = {
            "station_id": station_id,
            "current_consumption": station.consommation_kwh or 0,
            "predicted_consumption": station.conso_predite or 0,
            "potential_savings": station.eco_potentiel,
            "estimated_savings_kwh": station.economie_estimee_kwh or 0,
            "estimated_savings_rl_kwh": station.economie_rl_kwh or 0,
            "cost_savings_dt": (station.economie_rl_kwh or 0) * settings.PRIX_KWH_TN,
            "co2_savings_tonnes": (station.economie_rl_kwh or 0) * settings.FACTEUR_CO2_TN / 1000,
        }
        
        return savings
    
    def get_stations_by_criticite(self, criticite: str) -> List[Station]:
        """
        Get stations by criticite level.
        """
        all_stations = self.repository.get_all()
        return [s for s in all_stations if s.criticite == criticite]
    
    def update_station_metrics(
        self,
        station_id: str,
        consommation_kwh: Optional[float] = None,
        score_qos: Optional[float] = None,
        anomalie_score: Optional[float] = None,
    ) -> Optional[Station]:
        """
        Update station operational metrics.
        """
        update_data = {}
        
        if consommation_kwh is not None:
            if not UserInputValidator.validate_numeric_range(consommation_kwh, 0, 10000):
                raise AppError(
                    code=ErrorCode.VALIDATION_OUT_OF_RANGE,
                    message="La consommation doit être entre 0 et 10000",
                )
            update_data["consommation_kwh"] = consommation_kwh
        
        if score_qos is not None:
            if not UserInputValidator.validate_numeric_range(score_qos, 0, 1):
                raise AppError(
                    code=ErrorCode.VALIDATION_OUT_OF_RANGE,
                    message="Le score QoS doit être entre 0 et 1",
                )
            update_data["score_qos"] = score_qos
        
        if anomalie_score is not None:
            if not UserInputValidator.validate_numeric_range(anomalie_score, 0, 1):
                raise AppError(
                    code=ErrorCode.VALIDATION_OUT_OF_RANGE,
                    message="Le score d'anomalie doit être entre 0 et 1",
                )
            update_data["anomalie_score_ensemble"] = anomalie_score
        
        if not update_data:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Aucune métrique à mettre à jour",
            )
        
        return self.update_station(station_id, update_data)

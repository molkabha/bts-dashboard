"""Station domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Station:
    """Domain model for a station."""
    
    station_id: str
    technologie: str
    gouvernorat: str
    type_zone: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Operational metrics
    consommation_kwh: Optional[float] = None
    conso_predite: Optional[float] = None
    score_qos: Optional[float] = None
    anomalie_score_ensemble: Optional[float] = None
    
    # Time-series data
    heure: Optional[int] = None
    mois: Optional[int] = None
    jour_semaine: Optional[int] = None
    est_weekend: Optional[int] = None
    est_ramadan: Optional[int] = None
    est_ferie: Optional[int] = None
    
    # System metrics
    charge_cpu_pct: Optional[float] = None
    taux_charge_voix: Optional[float] = None
    taux_charge_data: Optional[float] = None
    nb_utilisateurs_actifs: Optional[int] = None
    nb_secteurs_actifs: Optional[int] = None
    puissance_emission_dbm: Optional[float] = None
    
    # Environmental data
    temperature_ambiante: Optional[float] = None
    humidite_relative_pct: Optional[float] = None
    vitesse_vent_ms: Optional[float] = None
    rayonnement_solaire_wm2: Optional[float] = None
    precipitation_mmh: Optional[float] = None
    pression_atmospherique_hpa: Optional[float] = None
    indice_uv: Optional[float] = None
    efficacite_free_cooling: Optional[float] = None
    
    # Decision/optimization outputs
    mode_operation: Optional[str] = None
    priorite: Optional[int] = None
    action_principale: Optional[str] = None
    action_proposee: Optional[str] = None
    action_rl: Optional[str] = None
    economie_estimee_kwh: Optional[float] = None
    economie_rl_kwh: Optional[float] = None
    risque_qos: Optional[str] = None
    violation_rl: Optional[bool] = None
    
    # Metadata
    timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert station to dictionary."""
        return {k: v for k, v in self.__dict__.items() if v is not None}
    
    @classmethod
    def from_dict(cls, data: dict) -> "Station":
        """Create station from dictionary."""
        # Filter out None values and extra fields
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields and v is not None}
        return cls(**filtered_data)
    
    def update_from_dict(self, data: dict) -> None:
        """Update station fields from dictionary."""
        valid_fields = {f.name for f in self.__dataclass_fields__.values()}
        for key, value in data.items():
            if key in valid_fields and value is not None:
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
    
    @property
    def criticite(self) -> str:
        """Calculate station criticite level."""
        if self.anomalie_score_ensemble is None:
            return "Inconnue"
        
        if self.anomalie_score_ensemble >= 0.6:
            return "Critique"
        elif self.anomalie_score_ensemble >= 0.25:
            return "Moyenne"
        else:
            return "Faible"
    
    @property
    def is_critical(self) -> bool:
        """Check if station is in critical state."""
        return self.criticite == "Critique"
    
    @property
    def eco_potentiel(self) -> float:
        """Calculate potential energy savings."""
        if self.economie_estimee_kwh:
            return self.economie_estimee_kwh
        if self.consommation_kwh and self.conso_predite:
            return max(0, self.consommation_kwh - self.conso_predite)
        return 0.0
    
    def __str__(self) -> str:
        return f"Station({self.station_id}, {self.gouvernorat}, {self.criticite})"
    
    def __repr__(self) -> str:
        return self.__str__()


@dataclass
class StationSummary:
    """Summary statistics for a station."""
    
    station_id: str
    gouvernorat: str
    technologie: str
    type_zone: str
    conso_moy: float
    score_qos_moy: float
    score_anom_moy: float
    score_criticite: float
    categorie: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    economie_estimee_kwh: Optional[float] = None
    economie_rl_kwh: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert summary to dictionary."""
        return {k: v for k, v in self.__dict__.items() if v is not None}
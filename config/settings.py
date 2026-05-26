"""Application settings and configuration management."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

# Base directory
ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings using Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: str = Field(default="temporary-secret-key-for-dev")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "n", "off", "release", "prod", "production"}:
                return False
        return value

    @model_validator(mode="after")
    def validate_production_config(self) -> Self:
        """Validate that production configuration is secure."""
        if self.ENVIRONMENT == "production":
            if not self.SECRET_KEY or self.SECRET_KEY == "temporary-secret-key-for-dev":
                raise ValueError(
                    "SECRET_KEY must be set to a secure value in production environment"
                )
        return self

    # Security
    TRUSTED_PROXIES: List[str] = Field(default=["127.0.0.1"])
    CSRF_ROTATE_TOKEN: bool = Field(default=True)

    # Database
    DB_PATH: Path = Field(default=ROOT / "dashboard_ops.sqlite3")

    # Assets & Outputs
    LOGO_PATH: Path = Field(default=ROOT / "static" / "logo.png")
    OUTPUTS_DIR: Path = Field(default=ROOT / "VF" / "NB3" / "output")
    ANOMALY_DATASET: str = Field(default="df_avec_anomalies.parquet")

    # Notebook Outputs
    NB1_OUTPUT: Path = Field(default=ROOT / "VF" / "NB1" / "NB1-P" / "output")
    NB2_OUTPUT: Path = Field(default=ROOT / "VF" / "NB2" / "output")
    NB3_OUTPUT: Path = Field(default=ROOT / "VF" / "NB3" / "output")

    # Hugging Face Hub
    USE_HF_HUB: bool = Field(default=True)
    HF_REPO_ID: str = Field(default="molkab/dashboard")
    HF_CACHE_DIR: Path = Field(default=ROOT / ".cache" / "huggingface")
    HF_TOKEN: str | None = Field(default=None)

    # Domain Constants
    FACTEUR_CO2_TN: float = Field(default=0.53)
    PRIX_KWH_TN: float = Field(default=0.40)
    QOS_SEUIL_DEFAULT: float = Field(default=0.60)
    NB3_MAX_ECO_FRAC: float = Field(default=0.48)
    SIM_SCHEMA_VERSION: int = Field(default=3)

    # Column Definitions
    TEMPORAL_COLUMNS: List[str] = Field(
        default=["timestamp", "mois", "heure", "jour_semaine", "est_weekend"]
    )
    MAP_COLUMNS: List[str] = Field(
        default=["station_id", "latitude", "longitude", "gouvernorat", "type_zone", "technologie"]
    )
    NB1_COLUMNS: List[str] = Field(
        default=["timestamp", "station_id", "consommation_kwh", "conso_predite"]
    )
    ANOMALY_COLUMNS: List[str] = Field(
        default=["timestamp", "station_id", "anomalie_score_ensemble", "nb_votes_anomalie"]
    )
    NB3_COLUMNS: List[str] = Field(
        default=["timestamp", "station_id", "action_rl", "economie_rl_kwh", "mode_operation", "score_qos"]
    )
    SIMULATION_COLUMNS: List[str] = Field(
        default=[
            "timestamp", "station_id", "consommation_kwh", "heure", "conso_predite",
            "anomalie_score_ensemble", "mode_operation", "action_rl", "action_proposee",
            "economie_estimee_kwh", "economie_rl_kwh", "economie_kwh", "score_qos",
        ]
    )

    # Dataset Selection
    MAIN_DATASET_CANDIDATES: List[str] = Field(
        default=["streamlit_data.parquet", "df_full_processed.parquet"]
    )

    # Artifacts Mapping
    ARTEFACTS: Dict[str, str] = Field(
        default={
            "NB1_results": "resultats_modeles.json",
            "NB2_results": "resultats_anomalie.json",
            "NB3_results": "rapport_optimisation.json",
            "KPI_network": "kpi_reseau.json",
        }
    )

    # UI Labels
    MONTH_LABELS: Dict[int, str] = Field(
        default={
            1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
            5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
            9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
        }
    )
    DAY_LABELS: Dict[int, str] = Field(
        default={
            0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
            4: "Vendredi", 5: "Samedi", 6: "Dimanche"
        }
    )


# Singleton instance
settings = Settings()

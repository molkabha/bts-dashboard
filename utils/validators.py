from __future__ import annotations

import re

from typing import Optional, Union

import pandas as pd

from pydantic import BaseModel, Field, ValidationError, field_validator


class StationDataValidator(BaseModel):

    station_id: str = Field(..., min_length=1, max_length=50)

    technologie: str = Field(default="4G", pattern="^(2G|3G|4G|4G\\+|5G)$")

    gouvernorat: str = Field(..., min_length=1, max_length=100)

    type_zone: str = Field(default="Urbain", pattern="^(Urbain|Periurbain|Rural)$")

    latitude: Optional[float] = Field(None, ge=-90, le=90)

    longitude: Optional[float] = Field(None, ge=-180, le=180)

    consommation_kwh: float = Field(..., ge=0, le=10000)

    conso_predite: Optional[float] = Field(None, ge=0, le=10000)

    score_qos: float = Field(default=0.8, ge=0, le=1)

    anomalie_score_ensemble: float = Field(default=0, ge=0, le=1)

    heure: int = Field(default=12, ge=0, le=23)

    mois: int = Field(default=1, ge=1, le=12)

    jour_semaine: int = Field(default=0, ge=0, le=6)

    est_weekend: int = Field(default=0, ge=0, le=1)

    @field_validator("station_id")
    @classmethod
    def validate_station_id(cls, v: str) -> str:

        if not re.match("^[A-Za-z0-9_-]+$", v):

            raise ValueError(
                "Station ID must be alphanumeric with underscores or hyphens"
            )

        return v.upper()

    @field_validator("gouvernorat")
    @classmethod
    def validate_gouvernorat(cls, v: str) -> str:

        valid_gouvernorats = [
            "Ariana",
            "Beja",
            "Ben Arous",
            "Bizerte",
            "Gabes",
            "Gafsa",
            "Jendouba",
            "Kairouan",
            "Kasserine",
            "Kebili",
            "Kef",
            "Mahdia",
            "Manouba",
            "Medenine",
            "Monastir",
            "Nabeul",
            "Sfax",
            "Sidi Bouzid",
            "Siliana",
            "Sousse",
            "Tataouine",
            "Tozeur",
            "Tunis",
            "Zaghouan",
        ]

        if v not in valid_gouvernorats:

            raise ValueError(
                f"Invalid gouvernorat. Must be one of: {', '.join(valid_gouvernorats)}"
            )

        return v


class UserInputValidator:

    SQL_INJECTION_PATTERNS = [
        "(?i)(union\\s+select|select\\s+.*\\s+from|insert\\s+into|delete\\s+from|drop\\s+table|update\\s+.*\\s+set)",
        "(?i)(--|\\#|\\/\\*|\\*\\/)",
        "(?i)(;|\\b(ALTER|CREATE|EXEC|EXECUTE|TRUNCATE)\\b)",
        "(\\b(OR|AND)\\b\\s+\\d+\\s*=\\s*\\d+)",
    ]

    XSS_PATTERNS = [
        "<script[^>]*>.*?</script>",
        "javascript\\s*:",
        "on\\w+\\s*=",
        "<[^>]+>",
    ]

    @staticmethod
    def sanitize_string(value: str, max_length: int = 500) -> str:

        if not isinstance(value, str):

            value = str(value)

        value = value[:max_length]

        value = value.replace("\x00", "")

        value = value.strip()

        return value

    @classmethod
    def validate_no_sql_injection(cls, value: str) -> bool:

        if not isinstance(value, str):

            return True

        for pattern in cls.SQL_INJECTION_PATTERNS:

            if re.search(pattern, value, re.IGNORECASE):

                return False

        return True

    @classmethod
    def validate_no_xss(cls, value: str) -> bool:

        if not isinstance(value, str):

            return True

        for pattern in cls.XSS_PATTERNS:

            if re.search(pattern, value, re.IGNORECASE):

                return False

        return True

    @classmethod
    def validate_email(cls, email: str) -> bool:

        if not isinstance(email, str):

            return False

        pattern = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"

        return bool(re.match(pattern, email))

    @classmethod
    def validate_password_strength(cls, password: str) -> tuple[bool, list[str]]:

        errors = []

        if len(password) < 8:

            errors.append("Le mot de passe doit contenir au moins 8 caractères.")

        if not re.search("[a-z]", password):

            errors.append("Le mot de passe doit contenir au moins une minuscule.")

        if not re.search("[A-Z]", password):

            errors.append("Le mot de passe doit contenir au moins une majuscule.")

        if not re.search("\\d", password):

            errors.append("Le mot de passe doit contenir au moins un chiffre.")

        if not re.search('[!@#$%^&*(),.?":{}|<>]', password):

            errors.append(
                "Le mot de passe doit contenir au moins un caractère spécial."
            )

        return (len(errors) == 0, errors)

    @classmethod
    def validate_dataframe_columns(
        cls, df: pd.DataFrame, required_columns: list[str]
    ) -> tuple[bool, list[str]]:

        missing = [col for col in required_columns if col not in df.columns]

        return (len(missing) == 0, missing)

    @classmethod
    def sanitize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:

        df = df.copy()

        for col in df.select_dtypes(include=["object"]).columns:

            df[col] = df[col].apply(
                lambda x: cls.sanitize_string(str(x)) if pd.notna(x) else x
            )

        return df

    @classmethod
    def validate_numeric_range(
        cls, value: Union[int, float], min_val: float, max_val: float
    ) -> bool:

        try:

            num = float(value)

            return min_val <= num <= max_val

        except (ValueError, TypeError):

            return False

    @classmethod
    def validate_date_range(cls, start_date, end_date) -> bool:

        try:

            return start_date <= end_date

        except TypeError:

            return False


def validate_api_input(
    data: dict, schema: type[BaseModel]
) -> tuple[bool, Optional[BaseModel], Optional[str]]:

    try:

        validated = schema(**data)

        return (True, validated, None)

    except ValidationError as e:

        error_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])

        return (False, None, error_msg)


VALIDATION_PATTERNS = {
    "station_id": "^[A-Z0-9_-]+$",
    "email": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
    "phone": "^\\+?[\\d\\s\\-\\(\\)]{10,}$",
    "username": "^[a-zA-Z0-9._-]{3,50}$",
}


def pattern_match(value: str, pattern_name: str) -> bool:

    if pattern_name not in VALIDATION_PATTERNS:

        raise ValueError(f"Unknown pattern: {pattern_name}")

    pattern = VALIDATION_PATTERNS[pattern_name]

    return bool(re.match(pattern, value))

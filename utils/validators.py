"""Validation helpers for input sanitization and security."""

from __future__ import annotations

import re
from typing import Any, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing_extensions import Self


class StationDataValidator(BaseModel):
    """Validator for station data inputs."""
    station_id: str = Field(..., min_length=1, max_length=50)
    technologie: str = Field(default="4G", pattern=r"^(2G|3G|4G|4G\+|5G)$")
    gouvernorat: str = Field(..., min_length=1, max_length=100)
    type_zone: str = Field(default="Urbain", pattern=r"^(Urbain|Periurbain|Rural)$")
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
    
    @field_validator('station_id')
    @classmethod
    def validate_station_id(cls, v: str) -> str:
        """Validate station ID format."""
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError('Station ID must be alphanumeric with underscores or hyphens')
        return v.upper()
    
    @field_validator('gouvernorat')
    @classmethod
    def validate_gouvernorat(cls, v: str) -> str:
        """Validate gouvernorat name."""
        valid_gouvernorats = [
            'Ariana', 'Beja', 'Ben Arous', 'Bizerte', 'Gabes', 'Gafsa', 'Jendouba',
            'Kairouan', 'Kasserine', 'Kebili', 'Kef', 'Mahdia', 'Manouba', 'Medenine',
            'Monastir', 'Nabeul', 'Sfax', 'Sidi Bouzid', 'Siliana', 'Sousse', 'Tataouine',
            'Tozeur', 'Tunis', 'Zaghouan'
        ]
        if v not in valid_gouvernorats:
            raise ValueError(f'Invalid gouvernorat. Must be one of: {", ".join(valid_gouvernorats)}')
        return v


class UserInputValidator:
    """Validator for user inputs to prevent injection and ensure data quality."""
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'(?i)(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table|update\s+.*\s+set)',
        r'(?i)(--|\#|\/\*|\*\/)',  # SQL comments
        r'(?i)(;|\b(ALTER|CREATE|EXEC|EXECUTE|TRUNCATE)\b)',  # Dangerous SQL keywords
        r'(\b(OR|AND)\b\s+\d+\s*=\s*\d+)',  # SQL tautologies
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript\s*:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers
        r'<[^>]+>',  # Any HTML tags
    ]
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = 500) -> str:
        """Sanitize string input by removing dangerous characters and limiting length."""
        if not isinstance(value, str):
            value = str(value)
        
        # Limit length
        value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Strip leading/trailing whitespace
        value = value.strip()
        
        return value
    
    @classmethod
    def validate_no_sql_injection(cls, value: str) -> bool:
        """Check if string contains SQL injection patterns."""
        if not isinstance(value, str):
            return True
        
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True
    
    @classmethod
    def validate_no_xss(cls, value: str) -> bool:
        """Check if string contains XSS patterns."""
        if not isinstance(value, str):
            return True
        
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format."""
        if not isinstance(email, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @classmethod
    def validate_password_strength(cls, password: str) -> tuple[bool, list[str]]:
        """Validate password strength."""
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_dataframe_columns(cls, df: pd.DataFrame, required_columns: list[str]) -> tuple[bool, list[str]]:
        """Validate that DataFrame contains all required columns."""
        missing = [col for col in required_columns if col not in df.columns]
        return len(missing) == 0, missing
    
    @classmethod
    def sanitize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Sanitize DataFrame by removing potentially dangerous content."""
        df = df.copy()
        
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(lambda x: cls.sanitize_string(str(x)) if pd.notna(x) else x)
        
        return df
    
    @classmethod
    def validate_numeric_range(cls, value: Union[int, float], min_val: float, max_val: float) -> bool:
        """Validate that a numeric value is within a specified range."""
        try:
            num = float(value)
            return min_val <= num <= max_val
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_date_range(cls, start_date, end_date) -> bool:
        """Validate that start_date is before end_date."""
        try:
            return start_date <= end_date
        except TypeError:
            return False


def validate_api_input(data: dict, schema: type[BaseModel]) -> tuple[bool, Optional[BaseModel], Optional[str]]:
    """
    Validate API input against a Pydantic schema.
    
    Returns:
        tuple: (is_valid, validated_data, error_message)
    """
    try:
        validated = schema(**data)
        return True, validated, None
    except ValidationError as e:
        error_msg = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
        return False, None, error_msg


# Common validation patterns
VALIDATION_PATTERNS = {
    'station_id': r'^[A-Z0-9_-]+$',
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone': r'^\+?[\d\s\-\(\)]{10,}$',
    'username': r'^[a-zA-Z0-9._-]{3,50}$',
}


def pattern_match(value: str, pattern_name: str) -> bool:
    """Check if value matches a named pattern."""
    if pattern_name not in VALIDATION_PATTERNS:
        raise ValueError(f"Unknown pattern: {pattern_name}")
    
    pattern = VALIDATION_PATTERNS[pattern_name]
    return bool(re.match(pattern, value))
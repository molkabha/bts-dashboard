"""Comprehensive error handling for the dashboard application."""

from __future__ import annotations

import logging
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union


class ErrorCode(Enum):
    """Application error codes."""
    # Authentication errors (1000-1999)
    AUTH_FAILED = 1000
    AUTH_INVALID_CREDENTIALS = 1001
    AUTH_ACCOUNT_LOCKED = 1002
    AUTH_SESSION_EXPIRED = 1003
    AUTH_RATE_LIMITED = 1004
    AUTH_TOKEN_INVALID = 1005

    # Validation errors (2000-2999)
    VALIDATION_ERROR = 2000
    VALIDATION_MISSING_FIELD = 2001
    VALIDATION_INVALID_FORMAT = 2002
    VALIDATION_OUT_OF_RANGE = 2003
    VALIDATION_DUPLICATE = 2004

    # Database errors (3000-3999)
    DB_CONNECTION_ERROR = 3000
    DB_QUERY_ERROR = 3001
    DB_INTEGRITY_ERROR = 3002
    DB_RECORD_NOT_FOUND = 3003
    # Backward-compatible alias used by tests/code expecting HTTP-ish naming
    NOT_FOUND = 3003
    DB_TRANSACTION_ERROR = 3004

    # Business logic errors (4000-4999)
    BUSINESS_RULE_VIOLATION = 4000
    INSUFFICIENT_PERMISSIONS = 4001
    RESOURCE_NOT_AVAILABLE = 4002
    OPERATION_NOT_ALLOWED = 4003

    # Security errors (5000-5999)
    SECURITY_VIOLATION = 5000
    SQL_INJECTION_ATTEMPT = 5001
    XSS_ATTEMPT = 5002
    CSRF_VIOLATION = 5003

    # System errors (6000-6999)
    INTERNAL_SERVER_ERROR = 6000
    SERVICE_UNAVAILABLE = 6001
    TIMEOUT_ERROR = 6002
    CONFIGURATION_ERROR = 6003


class AppError(Exception):
    """Base application error with structured error information."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow().isoformat()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "timestamp": self.timestamp,
            }
        }

    def log_error(self, logger: logging.Logger) -> None:
        """Log error with appropriate level."""
        log_message = f"[{self.code.value}] {self.message}"
        if self.details:
            log_message += f" | Détails: {self.details}"
        if self.original_exception:
            log_message += f" | Original: {str(self.original_exception)}"

        if self.code.value >= 6000:
            logger.error(log_message, exc_info=self.original_exception)
        elif self.code.value >= 5000:
            logger.warning(log_message)
        else:
            logger.info(log_message)


class ErrorHandler:
    """Centralized error handling for the application."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.error_handlers = {}

    def register_handler(self, error_code: ErrorCode, handler):
        """Register a custom error handler for a specific error code."""
        self.error_handlers[error_code] = handler

    def handle_error(self, error: Union[AppError, Exception],
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Handle an error and return appropriate response."""
        context = context or {}

        # Convert generic exceptions to AppError
        if not isinstance(error, AppError):
            error = AppError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message="Une erreur inattendue est survenue",
                details={"original_error": str(error)},
                original_exception=error,
            )

        # Log the error
        error.log_error(self.logger)

        # Check for custom handler
        if error.code in self.error_handlers:
            try:
                return self.error_handlers[error.code](error, context)
            except Exception as handler_error:
                self.logger.error(f"Échec du gestionnaire d'erreurs: {handler_error}")

        # Return default error response
        response = error.to_dict()

        # Add context information in development
        if context.get("debug", False):
            response["error"]["stack_trace"] = traceback.format_exc()
            response["error"]["context"] = context

        return response

    def handle_validation_error(self, errors: Dict[str, str], field: Optional[str] = None) -> AppError:
        """Create a validation error."""
        details = {"errors": errors}
        if field:
            details["field"] = field

        return AppError(
            code=ErrorCode.VALIDATION_ERROR,
            message="Échec de la validation",
            details=details,
        )

    def handle_authentication_error(self, message: str = "Échec de l'authentification") -> AppError:
        """Create an authentication error."""
        return AppError(
            code=ErrorCode.AUTH_FAILED,
            message=message,
        )

    def handle_database_error(self, operation: str, original_exception: Exception) -> AppError:
        """Create a database error."""
        return AppError(
            code=ErrorCode.DB_QUERY_ERROR,
            message=f"Échec de l'opération en base de données: {operation}",
            original_exception=original_exception,
            details={"operation": operation},
        )

    def handle_security_violation(self, violation_type: str, details: Optional[Dict[str, Any]] = None) -> AppError:
        """Create a security violation error."""
        return AppError(
            code=ErrorCode.SECURITY_VIOLATION,
            message=f"Violation de sécurité: {violation_type}",
            details=details,
        )


# Global error handler instance
error_handler = ErrorHandler()


def safe_execute(func, default_value=None, error_message: str = "L'opération a échoué"):
    """
    Safely execute a function and handle exceptions.
    """
    try:
        return func()
    except Exception as e:
        error_handler.handle_error(
            AppError(
                code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=error_message,
                original_exception=e,
            )
        )
        return default_value


def create_error_response(
    code: ErrorCode,
    message: str,
    status_code: int = 400,
    details: Optional[Dict[str, Any]] = None,
) -> tuple[Dict[str, Any], int]:
    """Create a standardized error response for APIs."""
    error = AppError(code=code, message=message, details=details)
    return error.to_dict(), status_code


# Convenience functions for common error types
def validation_error(errors: Dict[str, str], field: Optional[str] = None) -> tuple[Dict[str, Any], int]:
    """Create a validation error response."""
    error = error_handler.handle_validation_error(errors, field)
    return error.to_dict(), 400


def authentication_error(message: str = "Authentification requise") -> tuple[Dict[str, Any], int]:
    """Create an authentication error response."""
    error = error_handler.handle_authentication_error(message)
    return error.to_dict(), 401


def forbidden_error(message: str = "Accès refusé") -> tuple[Dict[str, Any], int]:
    """Create a forbidden error response."""
    error = AppError(
        code=ErrorCode.INSUFFICIENT_PERMISSIONS,
        message=message,
    )
    return error.to_dict(), 403


def not_found_error(message: str = "Ressource non trouvée") -> tuple[Dict[str, Any], int]:
    """Create a not found error response."""
    error = AppError(
        code=ErrorCode.DB_RECORD_NOT_FOUND,
        message=message,
    )
    return error.to_dict(), 404


def server_error(message: str = "Erreur interne du serveur") -> tuple[Dict[str, Any], int]:
    """Create a server error response."""
    error = AppError(
        code=ErrorCode.INTERNAL_SERVER_ERROR,
        message=message,
    )
    return error.to_dict(), 500

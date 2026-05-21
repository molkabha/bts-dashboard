"""Logging configuration for the dashboard application."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog
from pythonjsonlogger import jsonlogger


def setup_structlog() -> None:
    """Configure structlog for structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    enable_json: bool = False,
    enable_console: bool = True,
) -> logging.Logger:
    """
    Configure comprehensive logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file
        enable_json: Enable JSON format for logs
        enable_console: Enable console logging

    Returns:
        Configured logger instance
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatters
    if enable_json:
        # JSON formatter for structured logging
        json_formatter = jsonlogger.JsonFormatter(
            fmt='%(asctime)s %(name)s %(levelname)s %(message)s %(filename)s %(lineno)d %(funcName)s',
            datefmt='%Y-%m-%dT%H:%M:%S%z',
        )
        console_formatter = json_formatter
        file_formatter = json_formatter
    else:
        # Human-readable formatter
        console_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        file_formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(_ConsoleFilter())
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        try:
            # Ensure log directory exists
            log_file.parent.mkdir(parents=True, exist_ok=True)

            # Create rotating file handler (10MB per file, keep 5 files)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding='utf-8',
            )
            file_handler.setLevel(logging.DEBUG)  # Log everything to file
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

        except (OSError, IOError) as e:
            print(f"Warning: Could not create log file {log_file}: {e}")

    # Error file handler (separate file for errors only)
    if log_file:
        try:
            error_log_file = log_file.parent / f"{log_file.stem}_errors{log_file.suffix}"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(file_formatter)
            root_logger.addHandler(error_handler)

        except (OSError, IOError) as e:
            print(f"Warning: Could not create error log file {error_log_file}: {e}")

    # Setup structlog for structured logging
    setup_structlog()

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": log_level,
            "log_file": str(log_file) if log_file else None,
            "json_format": enable_json,
            "console_output": enable_console,
        },
    )

    return logger


class _ConsoleFilter(logging.Filter):
    """Filter for console output to exclude sensitive information."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Don't log sensitive information to console
        sensitive_patterns = [
            'password', 'secret', 'token', 'key', 'credential',
            'hash', 'auth', 'login', 'pwd',
        ]

        message_lower = record.getMessage().lower()
        for pattern in sensitive_patterns:
            if pattern in message_lower:
                # Replace sensitive data with [REDACTED]
                record.msg = record.getMessage().replace(
                    pattern, '[REDACTED]'
                )
                break

        return True


class AuditLogger:
    """Specialized logger for security audit events."""

    def __init__(self, log_file: Optional[Path] = None):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        if log_file:
            try:
                audit_log_file = log_file.parent / "audit.log"
                handler = logging.handlers.RotatingFileHandler(
                    audit_log_file,
                    maxBytes=10 * 1024 * 1024,
                    backupCount=10,
                    encoding='utf-8',
                )
                formatter = logging.Formatter(
                    fmt='%(asctime)s - AUDIT - %(message)s',
                    datefmt='%Y-%m-%dT%H:%M:%S%z',
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            except (OSError, IOError) as e:
                print(f"Warning: Could not create audit log file: {e}")

    def log_event(
        self,
        event_type: str,
        user: str,
        action: str,
        resource: str,
        status: str = "SUCCESS",
        details: Optional[dict] = None,
    ) -> None:
        """Log an audit event."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user": user,
            "action": action,
            "resource": resource,
            "status": status,
            "details": details or {},
        }

        # Use structlog for structured audit logging
        structlog.get_logger("audit").info(
            "audit_event",
            **log_data,
        )

        # Also log to standard audit logger
        self.logger.info(
            f"event_type={event_type} user={user} action={action} "
            f"resource={resource} status={status} details={details or {}}"
        )


# Global logging configuration
def configure_application_logging(
    environment: str = "development",
    log_dir: Optional[Path] = None,
) -> tuple[logging.Logger, Optional[AuditLogger]]:
    """
    Configure logging based on environment.

    Args:
        environment: Environment name (development, staging, production)
        log_dir: Directory for log files

    Returns:
        Tuple of (main_logger, audit_logger)
    """
    # Default log directory
    if log_dir is None:
        log_dir = Path("logs")

    # Environment-specific configuration
    config = {
        "development": {
            "log_level": "DEBUG",
            "enable_json": False,
            "enable_console": True,
            "log_file": log_dir / "dashboard_dev.log",
        },
        "staging": {
            "log_level": "INFO",
            "enable_json": True,
            "enable_console": True,
            "log_file": log_dir / "dashboard_staging.log",
        },
        "production": {
            "log_level": "WARNING",
            "enable_json": True,
            "enable_console": False,
            "log_file": log_dir / "dashboard_prod.log",
        },
    }

    env_config = config.get(environment, config["development"])

    # Setup logging
    logger = setup_logging(
        log_level=env_config["log_level"],
        log_file=env_config["log_file"],
        enable_json=env_config["enable_json"],
        enable_console=env_config["enable_console"],
    )

    # Setup audit logger
    audit_logger = None
    if environment in ["staging", "production"]:
        audit_logger = AuditLogger(env_config["log_file"])

    return logger, audit_logger


# Convenience function for quick setup
def init_logging(level: str = "INFO") -> logging.Logger:
    """Initialize logging with default configuration."""
    return setup_logging(log_level=level, enable_console=True, enable_json=False)

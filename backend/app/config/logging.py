"""
Logging konfigürasyonu
Strukturel logging ve farklı output formatları
"""

import logging
import logging.config
import sys
from typing import Any, Dict
import structlog
from pathlib import Path

from .settings import settings


def setup_logging() -> None:
    """
    Logging sistemini konfigüre eder
    Structlog ve standart Python logging entegrasyonu
    """
    
    # Log dizinini oluştur
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Logging konfigürasyonu
    logging_config: Dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": settings.log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "()": "structlog.stdlib.ProcessorFormatter",
                "processor": structlog.dev.ConsoleRenderer(colors=False),
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": sys.stdout,
                "level": settings.log_level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": "logs/verisnap.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "level": "INFO",
                "encoding": "utf-8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "level": "ERROR",
                "encoding": "utf-8",
            },
            "scraping_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": "logs/scraping.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 10,
                "level": "INFO",
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "verisnap": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "verisnap.scraper": {
                "level": "INFO",
                "handlers": ["console", "scraping_file"],
                "propagate": False,
            },
            "verisnap.error": {
                "level": "ERROR",
                "handlers": ["console", "error_file"],
                "propagate": False,
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }
    
    # Standard logging'i konfigüre et
    logging.config.dictConfig(logging_config)
    
    # Structlog'u konfigüre et
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Named logger döndürür
    
    Args:
        name: Logger adı
        
    Returns:
        structlog.BoundLogger: Konfigüre edilmiş logger
    """
    return structlog.get_logger(name)


def log_scraping_event(
    event_type: str,
    site: str,
    status: str,
    details: Dict[str, Any] = None
) -> None:
    """
    Scraping olaylarını loglar
    
    Args:
        event_type: Olay tipi (start, complete, error, etc.)
        site: Hedef site
        status: Durum (success, error, warning)
        details: Ek detaylar
    """
    logger = get_logger("verisnap.scraper")
    
    log_data = {
        "event_type": event_type,
        "site": site,
        "status": status,
        "timestamp": None,  # structlog otomatik ekler
    }
    
    if details:
        log_data.update(details)
    
    if status == "error":
        logger.error("Scraping event", **log_data)
    elif status == "warning":
        logger.warning("Scraping event", **log_data)
    else:
        logger.info("Scraping event", **log_data)


def log_security_event(
    event_type: str,
    user_info: Dict[str, Any],
    details: Dict[str, Any] = None
) -> None:
    """
    Güvenlik olaylarını loglar
    
    Args:
        event_type: Olay tipi (auth_attempt, rate_limit, etc.)
        user_info: Kullanıcı bilgileri
        details: Ek detaylar
    """
    logger = get_logger("verisnap.security")
    
    log_data = {
        "event_type": event_type,
        "user_info": user_info,
        "timestamp": None,  # structlog otomatik ekler
    }
    
    if details:
        log_data.update(details)
    
    logger.warning("Security event", **log_data)


# Logger'ları başlat
setup_logging()

# Yaygın kullanım için logger'ları export et
main_logger = get_logger("verisnap")
scraper_logger = get_logger("verisnap.scraper")
security_logger = get_logger("verisnap.security")
error_logger = get_logger("verisnap.error")
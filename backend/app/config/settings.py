"""
Konfigürasyon ayarları modülü
Bu modül environment variables, database settings, SMTP settings ve security settings'i yönetir
"""

import os
from typing import List
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

class Settings:
    """Uygulama ayarları sınıfı"""
    
    # Temel uygulama ayarları
    APP_NAME: str = "VeriSnap Scraping API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server ayarları
    HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # CORS ayarları
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    
    # Güvenlik ayarları
    API_KEY: str = os.getenv("API_KEY", "your-secure-api-key-here")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
    
    # Rate limiting ayarları
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_PERIOD: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))  # saniye
    
    # Scraping ayarları
    MAX_CONCURRENT_SCRAPES: int = int(os.getenv("MAX_CONCURRENT_SCRAPES", "3"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    SELENIUM_HEADLESS: bool = os.getenv("SELENIUM_HEADLESS", "True").lower() == "true"
    SELENIUM_IMPLICIT_WAIT: int = int(os.getenv("SELENIUM_IMPLICIT_WAIT", "10"))
    
    # Database ayarları (SQLite varsayılan)
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./verisnap.db")
    
    # SMTP ayarları
    SMTP_HOST: str = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@verisnap.com")
    
    # Sağlık dizinleri URL'leri
    HEALTH_DIRECTORIES: List[str] = [
        "https://www.gelbeseiten.de",
        "https://www.das-oertliche.de",
        "https://www.arztauskunft.de"
    ]
    
    # Log ayarları
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "verisnap.log")

# Global settings instance
settings = Settings()
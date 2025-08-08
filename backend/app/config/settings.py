"""
Uygulama konfigürasyon ayarları
Environment variables üzerinden configuration management
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Ana uygulama ayarları"""
    
    # Backend Ayarları
    app_name: str = Field(default="VeriSnap", description="Uygulama adı")
    app_version: str = Field(default="1.0.0", description="Uygulama versiyonu")
    debug: bool = Field(default=False, description="Debug modu")
    host: str = Field(default="0.0.0.0", description="Host adresi")
    port: int = Field(default=8000, description="Port numarası")
    
    # Güvenlik Ayarları
    secret_key: str = Field(description="JWT secret key")
    api_key: str = Field(description="API anahtarı")
    algorithm: str = Field(default="HS256", description="JWT algoritması")
    access_token_expire_minutes: int = Field(default=30, description="Token geçerlilik süresi")
    
    # CORS Ayarları
    cors_origins: List[str] = Field(default=["http://localhost:3000"], description="İzin verilen origin'ler")
    
    # Veritabanı Ayarları
    database_url: str = Field(default="sqlite:///./verisnap.db", description="Veritabanı URL'si")
    database_echo: bool = Field(default=False, description="SQL query logları")
    
    # Scraping Ayarları
    playwright_headless: bool = Field(default=True, description="Playwright headless modu")
    max_concurrent_scrapes: int = Field(default=3, description="Maksimum eşzamanlı scraping sayısı")
    request_timeout: int = Field(default=30, description="Request timeout süresi")
    retry_attempts: int = Field(default=3, description="Retry deneme sayısı")
    retry_delay: int = Field(default=5, description="Retry bekleme süresi")
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        description="User agent string"
    )
    
    # Proxy Ayarları
    use_proxy: bool = Field(default=False, description="Proxy kullanım durumu")
    proxy_rotation_enabled: bool = Field(default=True, description="Proxy rotation aktif mi")
    proxy_health_check_interval: int = Field(default=300, description="Proxy health check aralığı")
    proxy_timeout: int = Field(default=10, description="Proxy timeout süresi")
    
    # E-posta Ayarları
    smtp_server: Optional[str] = Field(default=None, description="SMTP sunucu adresi")
    smtp_port: int = Field(default=587, description="SMTP port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP kullanıcı adı")
    smtp_password: Optional[str] = Field(default=None, description="SMTP şifre")
    smtp_use_tls: bool = Field(default=True, description="SMTP TLS kullanım")
    email_from: Optional[str] = Field(default=None, description="Gönderen e-posta adresi")
    
    # Rate Limiting Ayarları
    rate_limit_requests: int = Field(default=100, description="Rate limit - request sayısı")
    rate_limit_window: int = Field(default=3600, description="Rate limit - zaman penceresi")
    
    # Log Ayarları
    log_level: str = Field(default="INFO", description="Log seviyesi")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log formatı"
    )
    
    # Cache Ayarları
    cache_ttl: int = Field(default=3600, description="Cache TTL süresi")
    
    # Almanya Sağlık Dizinleri Ayarları
    target_sites: List[str] = Field(
        default=[
            "arztauskunft.de",
            "jameda.de", 
            "doctolib.de",
            "deutsche-aerzte.info"
        ],
        description="Hedef scraping siteleri"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


class DevelopmentSettings(Settings):
    """Development ortamı ayarları"""
    debug: bool = True
    log_level: str = "DEBUG"
    database_echo: bool = True


class ProductionSettings(Settings):
    """Production ortamı ayarları"""
    debug: bool = False
    log_level: str = "WARNING"
    playwright_headless: bool = True


class TestSettings(Settings):
    """Test ortamı ayarları"""
    database_url: str = "sqlite:///./test_verisnap.db"
    debug: bool = True
    log_level: str = "DEBUG"


def get_settings() -> Settings:
    """
    Environment'a göre settings döndürür
    
    Returns:
        Settings: Uygun settings objesi
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    if environment == "production":
        return ProductionSettings()
    elif environment == "test":
        return TestSettings()
    else:
        return DevelopmentSettings()


# Global settings instance
settings = get_settings()
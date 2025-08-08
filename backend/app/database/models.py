"""
Veritabanı modelleri
SQLAlchemy ORM modelleri ve ilişkiler
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    """Timestamp alanları için mixin"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(Base, TimestampMixin):
    """Kullanıcı modeli"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    scopes = Column(JSON, default=[], nullable=False)
    
    # İlişkiler
    scraping_sessions = relationship("ScrapingSession", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base, TimestampMixin):
    """API anahtarları modeli"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    rate_limit_override = Column(Integer, nullable=True)
    
    # İlişkiler
    user = relationship("User", back_populates="api_keys")


class ScrapingSession(Base, TimestampMixin):
    """Scraping oturumu modeli"""
    __tablename__ = "scraping_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_site = Column(String(100), nullable=False, index=True)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, running, completed, failed
    start_url = Column(Text, nullable=False)
    max_pages = Column(Integer, default=10, nullable=False)
    delay_between_requests = Column(Integer, default=5, nullable=False)
    use_proxy = Column(Boolean, default=False, nullable=False)
    
    # Sonuç bilgileri
    pages_scraped = Column(Integer, default=0, nullable=False)
    total_records = Column(Integer, default=0, nullable=False)
    success_rate = Column(Float, default=0.0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    
    # Zaman bilgileri
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Meta veriler
    config = Column(JSON, default={}, nullable=False)
    error_log = Column(Text, nullable=True)
    
    # İlişkiler
    user = relationship("User", back_populates="scraping_sessions")
    scraped_data = relationship("ScrapedData", back_populates="session", cascade="all, delete-orphan")
    session_logs = relationship("ScrapingLog", back_populates="session", cascade="all, delete-orphan")


class ScrapedData(Base, TimestampMixin):
    """Toplanan veri modeli"""
    __tablename__ = "scraped_data"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scraping_sessions.id"), nullable=False)
    source_url = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=False)
    
    # Sağlık hizmeti sağlayıcı bilgileri
    provider_name = Column(String(200), nullable=True, index=True)
    specialty = Column(String(100), nullable=True, index=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True, index=True)
    postal_code = Column(String(20), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(100), nullable=True)
    website = Column(String(200), nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    
    # Ham veri
    raw_data = Column(JSON, nullable=False)
    
    # Veri kalite bilgileri
    is_validated = Column(Boolean, default=False, nullable=False)
    confidence_score = Column(Float, default=0.0, nullable=False)
    
    # İlişkiler
    session = relationship("ScrapingSession", back_populates="scraped_data")


class ScrapingLog(Base, TimestampMixin):
    """Scraping log modeli"""
    __tablename__ = "scraping_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("scraping_sessions.id"), nullable=False)
    level = Column(String(20), nullable=False, index=True)  # INFO, WARNING, ERROR
    message = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    response_time = Column(Float, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # İlişkiler
    session = relationship("ScrapingSession", back_populates="session_logs")


class ProxyServer(Base, TimestampMixin):
    """Proxy sunucu modeli"""
    __tablename__ = "proxy_servers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    host = Column(String(100), nullable=False)
    port = Column(Integer, nullable=False)
    username = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    proxy_type = Column(String(20), default="http", nullable=False)  # http, https, socks4, socks5
    
    # Status bilgileri
    is_active = Column(Boolean, default=True, nullable=False)
    is_healthy = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    response_time = Column(Float, nullable=True)
    success_rate = Column(Float, default=100.0, nullable=False)
    
    # Kullanım istatistikleri
    usage_count = Column(Integer, default=0, nullable=False)
    error_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Meta veriler
    country = Column(String(50), nullable=True)
    provider = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)


class EmailTemplate(Base, TimestampMixin):
    """E-posta şablon modeli"""
    __tablename__ = "email_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    subject = Column(String(200), nullable=False)
    html_content = Column(Text, nullable=False)
    text_content = Column(Text, nullable=True)
    template_variables = Column(JSON, default=[], nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # İlişkiler
    sent_emails = relationship("SentEmail", back_populates="template")


class SentEmail(Base, TimestampMixin):
    """Gönderilen e-posta modeli"""
    __tablename__ = "sent_emails"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("email_templates.id"), nullable=True)
    to_email = Column(String(100), nullable=False, index=True)
    from_email = Column(String(100), nullable=False)
    subject = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, sent, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Meta veriler
    metadata = Column(JSON, default={}, nullable=False)
    
    # İlişkiler
    template = relationship("EmailTemplate", back_populates="sent_emails")


class SystemSetting(Base, TimestampMixin):
    """Sistem ayarları modeli"""
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    data_type = Column(String(20), default="string", nullable=False)  # string, integer, float, boolean, json
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    category = Column(String(50), nullable=True, index=True)


class ActivityLog(Base, TimestampMixin):
    """Aktivite log modeli"""
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, default={}, nullable=False)
    status = Column(String(20), default="success", nullable=False, index=True)  # success, failed, warning
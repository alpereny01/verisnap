"""
API endpoint modeli ve şemaları
Pydantic modelleri ile request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class StatusEnum(str, Enum):
    """Durum enum'ı"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ProxyTypeEnum(str, Enum):
    """Proxy tipi enum'ı"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


# Auth Schemas
class Token(BaseModel):
    """Token response modeli"""
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data modeli"""
    username: Optional[str] = None


class UserCreate(BaseModel):
    """Kullanıcı oluşturma modeli"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=100)
    scopes: List[str] = Field(default=[])


class UserResponse(BaseModel):
    """Kullanıcı response modeli"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    scopes: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Login request modeli"""
    username: str
    password: str


# Scraping Schemas
class ScrapingRequest(BaseModel):
    """Scraping request modeli"""
    target_site: str = Field(..., description="Hedef site (jameda.de, doctolib.de)")
    specialty: Optional[str] = Field("", description="Uzmanlık alanı")
    city: Optional[str] = Field("", description="Şehir")
    max_pages: int = Field(10, ge=1, le=100, description="Maksimum sayfa sayısı")
    delay: int = Field(5, ge=1, le=60, description="Request arası bekleme süresi (saniye)")
    use_proxy: bool = Field(False, description="Proxy kullanılsın mı")
    headless: bool = Field(True, description="Headless mode")
    notify_email: Optional[str] = Field(None, description="Bildirim e-posta adresi")
    
    @validator('target_site')
    def validate_target_site(cls, v):
        """Hedef site validation"""
        allowed_sites = ["jameda.de", "doctolib.de", "arztauskunft.de", "deutsche-aerzte.info"]
        if v not in allowed_sites:
            raise ValueError(f'target_site must be one of: {allowed_sites}')
        return v
    
    @validator('specialty')
    def validate_specialty(cls, v):
        """Uzmanlık alanı validation"""
        if v and len(v.strip()) < 2:
            raise ValueError('specialty must be at least 2 characters')
        return v.strip() if v else ""
    
    @validator('city')
    def validate_city(cls, v):
        """Şehir validation"""
        if v and len(v.strip()) < 2:
            raise ValueError('city must be at least 2 characters')
        return v.strip() if v else ""


class ScrapingResponse(BaseModel):
    """Scraping response modeli"""
    session_id: str
    status: StatusEnum
    message: str
    estimated_duration: Optional[int] = Field(None, description="Tahmini süre (saniye)")


class ScrapingSessionResponse(BaseModel):
    """Scraping session response modeli"""
    id: int
    session_id: str
    user_id: int
    target_site: str
    status: StatusEnum
    start_url: str
    max_pages: int
    delay_between_requests: int
    use_proxy: bool
    pages_scraped: int
    total_records: int
    success_rate: float
    error_count: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    config: Dict[str, Any]
    error_log: Optional[str]
    
    class Config:
        from_attributes = True


class HealthcareProviderResponse(BaseModel):
    """Sağlık hizmeti sağlayıcı response modeli"""
    id: int
    session_id: int
    source_url: str
    page_number: int
    provider_name: Optional[str]
    specialty: Optional[str]
    address: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    raw_data: Dict[str, Any]
    is_validated: bool
    confidence_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True


# Proxy Schemas
class ProxyCreate(BaseModel):
    """Proxy oluşturma modeli"""
    name: str = Field(..., min_length=1, max_length=100)
    host: str = Field(..., min_length=1, max_length=100)
    port: int = Field(..., ge=1, le=65535)
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, max_length=100)
    proxy_type: ProxyTypeEnum = ProxyTypeEnum.HTTP
    country: Optional[str] = Field(None, max_length=50)
    provider: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class ProxyResponse(BaseModel):
    """Proxy response modeli"""
    id: int
    name: str
    host: str
    port: int
    proxy_type: str
    is_active: bool
    is_healthy: bool
    last_checked_at: Optional[datetime]
    response_time: Optional[float]
    success_rate: float
    usage_count: int
    error_count: int
    last_used_at: Optional[datetime]
    country: Optional[str]
    provider: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ProxyHealthCheck(BaseModel):
    """Proxy sağlık kontrol response modeli"""
    proxy_id: int
    is_healthy: bool
    response_time: Optional[float]
    error: Optional[str]
    checked_at: datetime


# Email Schemas
class EmailSendRequest(BaseModel):
    """E-posta gönderme request modeli"""
    to_emails: Union[str, List[str]]
    subject: str = Field(..., min_length=1, max_length=200)
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    template_name: Optional[str] = None
    template_variables: Optional[Dict[str, Any]] = None
    cc_emails: Optional[List[str]] = None
    bcc_emails: Optional[List[str]] = None
    
    @validator('to_emails')
    def validate_to_emails(cls, v):
        """E-posta adresleri validation"""
        if isinstance(v, str):
            v = [v]
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        import re
        
        for email in v:
            if not re.match(email_pattern, email):
                raise ValueError(f'Invalid email address: {email}')
        
        return v
    
    @validator('html_content', 'text_content')
    def validate_content(cls, v, values):
        """İçerik validation"""
        # Template kullanılmıyorsa en az bir içerik gerekli
        if not values.get('template_name') and not v and not values.get('html_content') and not values.get('text_content'):
            raise ValueError('Either template_name or content must be provided')
        return v


class EmailResponse(BaseModel):
    """E-posta response modeli"""
    success: bool
    message: str
    to_emails: List[str]
    sent_at: Optional[datetime] = None
    error: Optional[str] = None


class EmailTemplateCreate(BaseModel):
    """E-posta şablon oluşturma modeli"""
    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=200)
    html_content: str = Field(..., min_length=1)
    text_content: Optional[str] = None
    template_variables: List[str] = Field(default=[])
    is_active: bool = Field(True)


class EmailTemplateResponse(BaseModel):
    """E-posta şablon response modeli"""
    id: int
    name: str
    subject: str
    template_variables: List[str]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Statistics Schemas
class SystemStats(BaseModel):
    """Sistem istatistikleri modeli"""
    total_users: int
    total_sessions: int
    total_scraped_records: int
    active_sessions: int
    failed_sessions: int
    success_rate: float
    avg_session_duration: float
    most_popular_sites: List[Dict[str, Any]]
    proxy_stats: Dict[str, Any]


class SessionStats(BaseModel):
    """Session istatistikleri modeli"""
    session_id: str
    duration: float
    pages_per_minute: float
    records_per_page: float
    error_rate: float
    proxy_used: bool
    proxy_performance: Optional[Dict[str, Any]]


# Error Response Schemas
class ErrorResponse(BaseModel):
    """Hata response modeli"""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class ValidationErrorResponse(BaseModel):
    """Validation hata response modeli"""
    detail: str
    errors: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.now)


# Pagination Schemas
class PaginationParams(BaseModel):
    """Pagination parametreleri"""
    skip: int = Field(0, ge=0, description="Atlanacak kayıt sayısı")
    limit: int = Field(50, ge=1, le=1000, description="Maksimum kayıt sayısı")


class PaginatedResponse(BaseModel):
    """Paginated response modeli"""
    items: List[Any]
    total: int
    skip: int
    limit: int
    has_next: bool
    has_previous: bool


# Health Check Schemas
class HealthResponse(BaseModel):
    """Health check response modeli"""
    status: str
    timestamp: datetime
    version: str
    database: Dict[str, Any]
    proxy: Dict[str, Any]
    email: Dict[str, Any]
    uptime: float


# Configuration Schemas
class ConfigUpdate(BaseModel):
    """Konfigürasyon güncelleme modeli"""
    key: str
    value: Any
    description: Optional[str] = None


class ConfigResponse(BaseModel):
    """Konfigürasyon response modeli"""
    key: str
    value: Any
    data_type: str
    description: Optional[str]
    is_public: bool
    category: Optional[str]
    updated_at: datetime
"""
Güvenlik modülü - Authentication, authorization ve input validation
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, validator
import re

from ..config.settings import settings
from ..config.logging import security_logger


# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token
security = HTTPBearer()


class TokenData(BaseModel):
    """Token verisi modeli"""
    username: Optional[str] = None
    scopes: list[str] = []


class User(BaseModel):
    """Kullanıcı modeli"""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    scopes: list[str] = []


class UserInDB(User):
    """Veritabanındaki kullanıcı modeli"""
    hashed_password: str


# Fake users database (production'da gerçek veritabanından gelecek)
fake_users_db = {
    "admin": {
        "username": "admin",
        "full_name": "Admin User",
        "email": "admin@verisnap.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # secret
        "disabled": False,
        "scopes": ["read", "write", "admin"],
    },
    "scraper": {
        "username": "scraper",
        "full_name": "Scraper User",
        "email": "scraper@verisnap.com",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # secret
        "disabled": False,
        "scopes": ["read", "scrape"],
    }
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Şifreyi doğrular
    
    Args:
        plain_password: Plain text şifre
        hashed_password: Hash'lenmiş şifre
        
    Returns:
        bool: Şifre doğru mu
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Şifreyi hash'ler
    
    Args:
        password: Plain text şifre
        
    Returns:
        str: Hash'lenmiş şifre
    """
    return pwd_context.hash(password)


def get_user(db: Dict[str, Any], username: str) -> Optional[UserInDB]:
    """
    Kullanıcıyı getirir
    
    Args:
        db: Kullanıcı veritabanı
        username: Kullanıcı adı
        
    Returns:
        Optional[UserInDB]: Kullanıcı objesi
    """
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None


def authenticate_user(db: Dict[str, Any], username: str, password: str) -> Optional[UserInDB]:
    """
    Kullanıcıyı doğrular
    
    Args:
        db: Kullanıcı veritabanı
        username: Kullanıcı adı
        password: Şifre
        
    Returns:
        Optional[UserInDB]: Doğrulanmış kullanıcı
    """
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    JWT access token oluşturur
    
    Args:
        data: Token verisi
        expires_delta: Geçerlilik süresi
        
    Returns:
        str: JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Mevcut kullanıcıyı getirir (JWT token'dan)
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        User: Mevcut kullanıcı
        
    Raises:
        HTTPException: Token geçersizse
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Aktif kullanıcıyı getirir
    
    Args:
        current_user: Mevcut kullanıcı
        
    Returns:
        User: Aktif kullanıcı
        
    Raises:
        HTTPException: Kullanıcı inaktifse
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def verify_api_key(request: Request) -> bool:
    """
    API key'i doğrular
    
    Args:
        request: FastAPI request objesi
        
    Returns:
        bool: API key geçerli mi
    """
    api_key = request.headers.get("X-API-Key")
    
    if not api_key:
        security_logger.warning(
            "API key missing",
            client_ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        return False
    
    if api_key != settings.api_key:
        security_logger.warning(
            "Invalid API key",
            client_ip=request.client.host,
            user_agent=request.headers.get("user-agent"),
            provided_key=api_key[:8] + "***"  # Sadece ilk 8 karakter
        )
        return False
    
    return True


class InputValidator:
    """Input validation sınıfı"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """
        E-posta adresini doğrular
        
        Args:
            email: E-posta adresi
            
        Returns:
            bool: Geçerli mi
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        URL'yi doğrular
        
        Args:
            url: URL
            
        Returns:
            bool: Geçerli mi
        """
        pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?$'
        return re.match(pattern, url) is not None
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """
        Domain'i doğrular
        
        Args:
            domain: Domain adı
            
        Returns:
            bool: Geçerli mi
        """
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
        return re.match(pattern, domain) is not None
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """
        Input'u temizler
        
        Args:
            text: Temizlenecek metin
            
        Returns:
            str: Temizlenmiş metin
        """
        # HTML tag'lerini kaldır
        text = re.sub(r'<[^>]+>', '', text)
        # Script tag'lerini kaldır
        text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Zararlı karakterleri kaldır
        text = re.sub(r'[<>&"\']', '', text)
        return text.strip()


class ScrapingRequestValidator(BaseModel):
    """Scraping request validation modeli"""
    
    url: str
    max_pages: Optional[int] = 10
    delay: Optional[int] = 5
    use_proxy: Optional[bool] = False
    
    @validator('url')
    def validate_url(cls, v):
        """URL validation"""
        if not InputValidator.validate_url(v):
            raise ValueError('Geçersiz URL formatı')
        
        # Sadece izin verilen domain'lere scraping
        allowed_domains = settings.target_sites
        domain = v.split('/')[2].lower()
        
        if not any(allowed_domain in domain for allowed_domain in allowed_domains):
            raise ValueError(f'Bu domain\'e scraping yapılmasına izin verilmiyor: {domain}')
        
        return v
    
    @validator('max_pages')
    def validate_max_pages(cls, v):
        """Max pages validation"""
        if v is not None and (v < 1 or v > 100):
            raise ValueError('max_pages 1-100 arasında olmalı')
        return v
    
    @validator('delay')
    def validate_delay(cls, v):
        """Delay validation"""
        if v is not None and (v < 1 or v > 60):
            raise ValueError('delay 1-60 saniye arasında olmalı')
        return v


def require_scope(required_scope: str):
    """
    Belirli bir scope gereksinimi decorator'ı
    
    Args:
        required_scope: Gerekli scope
        
    Returns:
        Decorator function
    """
    def scope_checker(current_user: User = Depends(get_current_active_user)):
        if required_scope not in current_user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    
    return scope_checker
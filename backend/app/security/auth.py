"""
Güvenlik ve yetkilendirme modülü
Bu modül API key authentication ve rate limiting işlevlerini sağlar
"""

import time
from typing import Dict, Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from config.settings import settings

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

# HTTP Bearer token scheme
security = HTTPBearer()

class APIKeyAuth:
    """API Key doğrulama sınıfı"""
    
    def __init__(self):
        self.valid_api_keys = {
            settings.API_KEY: {
                "name": "main_api_key",
                "permissions": ["read", "write", "scrape"],
                "created_at": time.time()
            }
        }
    
    def verify_api_key(self, api_key: str) -> bool:
        """API key'in geçerli olup olmadığını kontrol eder"""
        return api_key in self.valid_api_keys
    
    def get_api_key_info(self, api_key: str) -> Optional[Dict]:
        """API key bilgilerini döner"""
        return self.valid_api_keys.get(api_key)

# Global API key auth instance
api_key_auth = APIKeyAuth()

async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    API key'i Authorization header'dan alır ve doğrular
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        str: Geçerli API key
        
    Raises:
        HTTPException: API key geçersiz ise
    """
    api_key = credentials.credentials
    
    if not api_key_auth.verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return api_key

async def verify_permissions(
    api_key: str = Depends(get_api_key),
    required_permission: str = "read"
) -> bool:
    """
    API key'in belirli bir permission'a sahip olup olmadığını kontrol eder
    
    Args:
        api_key: Doğrulanmış API key
        required_permission: Gerekli izin türü
        
    Returns:
        bool: İzin var ise True
        
    Raises:
        HTTPException: İzin yok ise
    """
    api_key_info = api_key_auth.get_api_key_info(api_key)
    
    if not api_key_info or required_permission not in api_key_info.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Bu işlem için '{required_permission}' iznine sahip değilsiniz"
        )
    
    return True

class RateLimitMiddleware:
    """Rate limiting middleware sınıfı"""
    
    def __init__(self):
        self.request_counts: Dict[str, Dict] = {}
        self.window_size = settings.RATE_LIMIT_PERIOD
        self.max_requests = settings.RATE_LIMIT_REQUESTS
    
    def is_rate_limited(self, client_ip: str) -> bool:
        """
        İstemcinin rate limit'e takılıp takılmadığını kontrol eder
        
        Args:
            client_ip: İstemci IP adresi
            
        Returns:
            bool: Rate limit aşıldı ise True
        """
        current_time = time.time()
        
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = {
                "count": 1,
                "window_start": current_time
            }
            return False
        
        client_data = self.request_counts[client_ip]
        
        # Yeni window başladı mı kontrol et
        if current_time - client_data["window_start"] > self.window_size:
            client_data["count"] = 1
            client_data["window_start"] = current_time
            return False
        
        # Request count'u artır
        client_data["count"] += 1
        
        return client_data["count"] > self.max_requests
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """
        İstemci için kalan request sayısını döner
        
        Args:
            client_ip: İstemci IP adresi
            
        Returns:
            int: Kalan request sayısı
        """
        if client_ip not in self.request_counts:
            return self.max_requests
        
        current_count = self.request_counts[client_ip]["count"]
        return max(0, self.max_requests - current_count)

# Global rate limit middleware instance
rate_limit_middleware = RateLimitMiddleware()

def create_rate_limit_dependency(requests_per_minute: int = None):
    """
    Özelleştirilebilir rate limit dependency oluşturur
    
    Args:
        requests_per_minute: Dakika başına maksimum request sayısı
        
    Returns:
        function: Rate limit dependency function
    """
    if requests_per_minute is None:
        requests_per_minute = settings.RATE_LIMIT_REQUESTS
    
    async def rate_limit_check(request: Request):
        client_ip = get_remote_address(request)
        
        if rate_limit_middleware.is_rate_limited(client_ip):
            remaining = rate_limit_middleware.get_remaining_requests(client_ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit aşıldı. Kalan request: {remaining}",
                headers={"Retry-After": str(settings.RATE_LIMIT_PERIOD)}
            )
        
        return True
    
    return rate_limit_check

# Varsayılan rate limit dependency
default_rate_limit = create_rate_limit_dependency()
"""
Rate limiting modülü
API endpoint'lerine rate limiting uygular
"""

import time
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from collections import defaultdict, deque
import asyncio
from datetime import datetime, timedelta

from ..config.settings import settings
from ..config.logging import security_logger


class RateLimiter:
    """Rate limiting sınıfı"""
    
    def __init__(self):
        # IP bazlı rate limiting için deque kullan
        self.requests: Dict[str, deque] = defaultdict(deque)
        # API key bazlı rate limiting
        self.api_requests: Dict[str, deque] = defaultdict(deque)
        # Geçici ban listesi
        self.banned_ips: Dict[str, datetime] = {}
        # Ban süresi (dakika)
        self.ban_duration = 60
    
    def _clean_old_requests(self, request_queue: deque, window_size: int) -> None:
        """
        Eski request'leri temizler
        
        Args:
            request_queue: Request kuyruğu
            window_size: Zaman penceresi (saniye)
        """
        current_time = time.time()
        while request_queue and current_time - request_queue[0] > window_size:
            request_queue.popleft()
    
    def _is_banned(self, ip: str) -> bool:
        """
        IP'nin ban durumunu kontrol eder
        
        Args:
            ip: IP adresi
            
        Returns:
            bool: Banli mi
        """
        if ip in self.banned_ips:
            ban_time = self.banned_ips[ip]
            if datetime.now() - ban_time < timedelta(minutes=self.ban_duration):
                return True
            else:
                # Ban süresi dolmuş, listeden çıkar
                del self.banned_ips[ip]
        return False
    
    def _ban_ip(self, ip: str, reason: str) -> None:
        """
        IP'yi yasaklar
        
        Args:
            ip: IP adresi
            reason: Yasaklama nedeni
        """
        self.banned_ips[ip] = datetime.now()
        security_logger.warning(
            "IP banned",
            ip=ip,
            reason=reason,
            ban_duration=self.ban_duration
        )
    
    async def check_rate_limit(
        self,
        request: Request,
        max_requests: Optional[int] = None,
        window_size: Optional[int] = None,
        identifier_type: str = "ip"
    ) -> bool:
        """
        Rate limit kontrolü yapar
        
        Args:
            request: FastAPI request objesi
            max_requests: Maksimum request sayısı
            window_size: Zaman penceresi (saniye)
            identifier_type: Tanımlayıcı türü ("ip" veya "api_key")
            
        Returns:
            bool: Rate limit aşılmış mı
            
        Raises:
            HTTPException: Rate limit aşıldığında
        """
        # Default değerler
        if max_requests is None:
            max_requests = settings.rate_limit_requests
        if window_size is None:
            window_size = settings.rate_limit_window
        
        # Identifier belirle
        if identifier_type == "ip":
            identifier = request.client.host
            request_queue = self.requests[identifier]
        else:  # api_key
            api_key = request.headers.get("X-API-Key", "")
            identifier = f"api_{api_key}"
            request_queue = self.api_requests[identifier]
        
        # IP ban kontrolü
        if identifier_type == "ip" and self._is_banned(request.client.host):
            security_logger.warning(
                "Banned IP attempted access",
                ip=request.client.host,
                user_agent=request.headers.get("user-agent"),
                path=request.url.path
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"IP address banned for {self.ban_duration} minutes due to rate limit violations"
            )
        
        current_time = time.time()
        
        # Eski request'leri temizle
        self._clean_old_requests(request_queue, window_size)
        
        # Rate limit kontrolü
        if len(request_queue) >= max_requests:
            # Rate limit aşıldı
            security_logger.warning(
                "Rate limit exceeded",
                identifier=identifier,
                identifier_type=identifier_type,
                current_requests=len(request_queue),
                max_requests=max_requests,
                window_size=window_size,
                ip=request.client.host,
                user_agent=request.headers.get("user-agent"),
                path=request.url.path
            )
            
            # IP bazlı ise ve çok fazla ihlal varsa ban et
            if identifier_type == "ip" and len(request_queue) > max_requests * 2:
                self._ban_ip(request.client.host, "Excessive rate limit violations")
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {max_requests} requests per {window_size} seconds.",
                headers={"Retry-After": str(window_size)}
            )
        
        # Request'i kaydet
        request_queue.append(current_time)
        
        return True
    
    async def get_rate_limit_info(self, identifier: str, identifier_type: str = "ip") -> Dict[str, any]:
        """
        Rate limit bilgilerini döndürür
        
        Args:
            identifier: Tanımlayıcı
            identifier_type: Tanımlayıcı türü
            
        Returns:
            Dict: Rate limit bilgileri
        """
        if identifier_type == "ip":
            request_queue = self.requests[identifier]
        else:
            request_queue = self.api_requests[f"api_{identifier}"]
        
        # Eski request'leri temizle
        self._clean_old_requests(request_queue, settings.rate_limit_window)
        
        remaining = max(0, settings.rate_limit_requests - len(request_queue))
        reset_time = int(time.time() + settings.rate_limit_window)
        
        return {
            "requests_made": len(request_queue),
            "requests_remaining": remaining,
            "requests_limit": settings.rate_limit_requests,
            "window_size": settings.rate_limit_window,
            "reset_time": reset_time,
            "is_banned": self._is_banned(identifier) if identifier_type == "ip" else False
        }


# Global rate limiter instance
rate_limiter = RateLimiter()


async def apply_rate_limit(
    request: Request,
    max_requests: Optional[int] = None,
    window_size: Optional[int] = None,
    identifier_type: str = "ip"
) -> None:
    """
    Rate limit middleware fonksiyonu
    
    Args:
        request: FastAPI request objesi
        max_requests: Maksimum request sayısı
        window_size: Zaman penceresi
        identifier_type: Tanımlayıcı türü
    """
    await rate_limiter.check_rate_limit(
        request=request,
        max_requests=max_requests,
        window_size=window_size,
        identifier_type=identifier_type
    )


class ScrapeRateLimiter:
    """Scraping işlemleri için özel rate limiter"""
    
    def __init__(self):
        # Site bazlı request takibi
        self.site_requests: Dict[str, deque] = defaultdict(deque)
        # Aktif scraping işlemleri
        self.active_scrapes: Dict[str, int] = defaultdict(int)
    
    async def check_scraping_limit(self, site: str, max_concurrent: int = None) -> bool:
        """
        Scraping limit kontrolü
        
        Args:
            site: Hedef site
            max_concurrent: Maksimum eşzamanlı scraping sayısı
            
        Returns:
            bool: Scraping yapılabilir mi
            
        Raises:
            HTTPException: Limit aşıldığında
        """
        if max_concurrent is None:
            max_concurrent = settings.max_concurrent_scrapes
        
        # Eşzamanlı scraping kontrolü
        if self.active_scrapes[site] >= max_concurrent:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many concurrent scrapes for {site}. Max: {max_concurrent}"
            )
        
        return True
    
    async def start_scraping(self, site: str) -> None:
        """
        Scraping başlatma
        
        Args:
            site: Hedef site
        """
        self.active_scrapes[site] += 1
    
    async def finish_scraping(self, site: str) -> None:
        """
        Scraping bitirme
        
        Args:
            site: Hedef site
        """
        if self.active_scrapes[site] > 0:
            self.active_scrapes[site] -= 1


# Global scrape rate limiter instance
scrape_rate_limiter = ScrapeRateLimiter()
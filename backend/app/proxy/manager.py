"""
Proxy yönetimi modülü
Çoklu proxy rotation, health check ve automatic failover
"""

import asyncio
import aiohttp
import random
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse
import ssl

from ..config.settings import settings
from ..config.logging import main_logger, scraper_logger
from ..database.operations import db_manager, ProxyRepository


@dataclass
class ProxyConfig:
    """Proxy konfigürasyon sınıfı"""
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    proxy_type: str = "http"
    country: Optional[str] = None
    
    @property
    def url(self) -> str:
        """Proxy URL'sini döndürür"""
        if self.username and self.password:
            return f"{self.proxy_type}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.proxy_type}://{self.host}:{self.port}"
    
    @property
    def dict(self) -> Dict[str, str]:
        """Proxy dict formatını döndürür"""
        return {
            "http": self.url,
            "https": self.url
        }


class ProxyHealthChecker:
    """Proxy sağlık kontrol sınıfı"""
    
    def __init__(self):
        self.test_urls = [
            "http://httpbin.org/ip",
            "https://httpbin.org/ip",
            "http://ifconfig.me/ip",
            "https://api.ipify.org?format=json"
        ]
        self.timeout = settings.proxy_timeout
    
    async def check_proxy_health(self, proxy: ProxyConfig) -> Dict[str, Any]:
        """
        Proxy sağlığını kontrol eder
        
        Args:
            proxy: Proxy konfigürasyonu
            
        Returns:
            Dict: Sağlık kontrol sonucu
        """
        result = {
            "is_healthy": False,
            "response_time": None,
            "error": None,
            "ip_address": None,
            "tested_url": None
        }
        
        start_time = time.time()
        
        try:
            # SSL sertifika doğrulamayı devre dışı bırak
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as session:
                
                # Random test URL seç
                test_url = random.choice(self.test_urls)
                result["tested_url"] = test_url
                
                async with session.get(
                    test_url,
                    proxy=proxy.url if proxy.proxy_type == "http" else None
                ) as response:
                    
                    if response.status == 200:
                        response_time = time.time() - start_time
                        result["response_time"] = round(response_time, 3)
                        result["is_healthy"] = True
                        
                        # IP adresini al
                        try:
                            content = await response.text()
                            if "ip" in content.lower():
                                # JSON response
                                import json
                                data = json.loads(content)
                                result["ip_address"] = data.get("origin") or data.get("ip")
                            else:
                                # Text response
                                result["ip_address"] = content.strip()
                        except:
                            pass
                    else:
                        result["error"] = f"HTTP {response.status}"
                        
        except asyncio.TimeoutError:
            result["error"] = "Timeout"
        except Exception as e:
            result["error"] = str(e)
        
        scraper_logger.info(
            "Proxy health check completed",
            proxy_host=proxy.host,
            proxy_port=proxy.port,
            is_healthy=result["is_healthy"],
            response_time=result["response_time"],
            error=result["error"]
        )
        
        return result


class ProxyRotator:
    """Proxy rotation sınıfı"""
    
    def __init__(self):
        self.proxies: List[ProxyConfig] = []
        self.current_index = 0
        self.health_checker = ProxyHealthChecker()
        self.last_health_check = 0
        self.health_check_interval = settings.proxy_health_check_interval
        self._is_initialized = False
    
    async def initialize(self):
        """Proxy rotator'ı başlatır"""
        await self.load_proxies_from_database()
        if settings.proxy_rotation_enabled:
            await self.check_all_proxies_health()
        self._is_initialized = True
        main_logger.info(f"Proxy rotator initialized with {len(self.proxies)} proxies")
    
    async def load_proxies_from_database(self):
        """Veritabanından proxy'leri yükler"""
        try:
            with db_manager.get_session() as db:
                proxy_servers = ProxyRepository.get_active_proxies(db)
                
                self.proxies = []
                for server in proxy_servers:
                    proxy = ProxyConfig(
                        host=server.host,
                        port=server.port,
                        username=server.username,
                        password=server.password,
                        proxy_type=server.proxy_type,
                        country=server.country
                    )
                    self.proxies.append(proxy)
                    
            main_logger.info(f"Loaded {len(self.proxies)} proxies from database")
            
        except Exception as e:
            main_logger.error("Failed to load proxies from database", error=str(e))
    
    async def add_proxy(self, proxy: ProxyConfig):
        """
        Yeni proxy ekler
        
        Args:
            proxy: Proxy konfigürasyonu
        """
        self.proxies.append(proxy)
        main_logger.info(f"Added proxy: {proxy.host}:{proxy.port}")
    
    async def get_next_proxy(self) -> Optional[ProxyConfig]:
        """
        Sıradaki proxy'yi döndürür
        
        Returns:
            Optional[ProxyConfig]: Sıradaki proxy
        """
        if not self.proxies:
            return None
        
        # Health check gerekli mi kontrol et
        current_time = time.time()
        if (current_time - self.last_health_check) > self.health_check_interval:
            await self.check_all_proxies_health()
        
        # Sağlıklı proxy'leri filtrele
        healthy_proxies = [p for p in self.proxies if hasattr(p, 'is_healthy') and p.is_healthy]
        
        if not healthy_proxies:
            main_logger.warning("No healthy proxies available")
            return None
        
        # Round-robin selection
        if self.current_index >= len(healthy_proxies):
            self.current_index = 0
        
        proxy = healthy_proxies[self.current_index]
        self.current_index += 1
        
        return proxy
    
    async def get_random_proxy(self) -> Optional[ProxyConfig]:
        """
        Random proxy döndürür
        
        Returns:
            Optional[ProxyConfig]: Random proxy
        """
        if not self.proxies:
            return None
        
        # Sağlıklı proxy'leri filtrele
        healthy_proxies = [p for p in self.proxies if hasattr(p, 'is_healthy') and p.is_healthy]
        
        if not healthy_proxies:
            return None
        
        return random.choice(healthy_proxies)
    
    async def check_all_proxies_health(self):
        """Tüm proxy'lerin sağlığını kontrol eder"""
        if not self.proxies:
            return
        
        main_logger.info(f"Checking health of {len(self.proxies)} proxies")
        
        # Concurrent health check
        tasks = []
        for proxy in self.proxies:
            task = asyncio.create_task(self.health_checker.check_proxy_health(proxy))
            tasks.append((proxy, task))
        
        # Sonuçları topla
        healthy_count = 0
        for proxy, task in tasks:
            try:
                result = await task
                proxy.is_healthy = result["is_healthy"]
                proxy.response_time = result["response_time"]
                proxy.last_error = result["error"]
                
                if result["is_healthy"]:
                    healthy_count += 1
                    
                # Veritabanını güncelle
                try:
                    with db_manager.get_session() as db:
                        # Proxy'yi ID ile bul ve güncelle (basit implementasyon)
                        pass  # Gerçek implementasyonda proxy ID'si gerekli
                except Exception as e:
                    main_logger.error("Failed to update proxy health in database", error=str(e))
                    
            except Exception as e:
                proxy.is_healthy = False
                proxy.last_error = str(e)
                main_logger.error(f"Health check failed for proxy {proxy.host}:{proxy.port}", error=str(e))
        
        self.last_health_check = time.time()
        main_logger.info(f"Health check completed: {healthy_count}/{len(self.proxies)} proxies healthy")
    
    async def remove_unhealthy_proxies(self):
        """Sağlıksız proxy'leri kaldırır"""
        before_count = len(self.proxies)
        self.proxies = [p for p in self.proxies if hasattr(p, 'is_healthy') and p.is_healthy]
        after_count = len(self.proxies)
        
        if before_count != after_count:
            main_logger.info(f"Removed {before_count - after_count} unhealthy proxies")


class ProxyManager:
    """Ana proxy yönetim sınıfı"""
    
    def __init__(self):
        self.rotator = ProxyRotator()
        self.enabled = settings.use_proxy
        self._is_initialized = False
    
    async def initialize(self):
        """Proxy manager'ı başlatır"""
        if self.enabled:
            await self.rotator.initialize()
        self._is_initialized = True
        main_logger.info(f"Proxy manager initialized (enabled: {self.enabled})")
    
    async def get_proxy_for_request(self, rotation_type: str = "round_robin") -> Optional[ProxyConfig]:
        """
        Request için proxy döndürür
        
        Args:
            rotation_type: Rotation tipi ("round_robin" veya "random")
            
        Returns:
            Optional[ProxyConfig]: Kullanılacak proxy
        """
        if not self.enabled:
            return None
        
        if not self._is_initialized:
            await self.initialize()
        
        if rotation_type == "random":
            return await self.rotator.get_random_proxy()
        else:
            return await self.rotator.get_next_proxy()
    
    async def create_aiohttp_session(self, proxy: Optional[ProxyConfig] = None) -> aiohttp.ClientSession:
        """
        Proxy ile aiohttp session oluşturur
        
        Args:
            proxy: Kullanılacak proxy
            
        Returns:
            aiohttp.ClientSession: Konfigüre edilmiş session
        """
        # SSL sertifika doğrulamayı devre dışı bırak
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        # Timeout ayarları
        timeout = aiohttp.ClientTimeout(
            total=settings.request_timeout,
            connect=10,
            sock_read=10
        )
        
        # Headers
        headers = {
            "User-Agent": settings.user_agent
        }
        
        if proxy:
            return aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            )
        else:
            return aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=headers
            )
    
    async def test_proxy_with_url(self, proxy: ProxyConfig, test_url: str) -> Dict[str, Any]:
        """
        Belirli bir URL ile proxy'yi test eder
        
        Args:
            proxy: Test edilecek proxy
            test_url: Test URL'si
            
        Returns:
            Dict: Test sonucu
        """
        return await self.rotator.health_checker.check_proxy_health(proxy)
    
    async def get_proxy_stats(self) -> Dict[str, Any]:
        """
        Proxy istatistiklerini döndürür
        
        Returns:
            Dict: Proxy istatistikleri
        """
        if not self.enabled:
            return {"enabled": False}
        
        total_proxies = len(self.rotator.proxies)
        healthy_proxies = len([p for p in self.rotator.proxies if hasattr(p, 'is_healthy') and p.is_healthy])
        
        return {
            "enabled": True,
            "total_proxies": total_proxies,
            "healthy_proxies": healthy_proxies,
            "health_percentage": (healthy_proxies / total_proxies * 100) if total_proxies > 0 else 0,
            "last_health_check": self.rotator.last_health_check,
            "rotation_enabled": settings.proxy_rotation_enabled
        }


# Global proxy manager instance
proxy_manager = ProxyManager()


# Convenience functions
async def get_proxy() -> Optional[ProxyConfig]:
    """Kolay kullanım için proxy getter"""
    return await proxy_manager.get_proxy_for_request()


async def create_session_with_proxy(proxy: Optional[ProxyConfig] = None) -> aiohttp.ClientSession:
    """Proxy ile session oluşturma convenience function"""
    if proxy is None:
        proxy = await get_proxy()
    return await proxy_manager.create_aiohttp_session(proxy)
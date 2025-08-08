"""
VeriSnap - Profesyonel Web Scraping API
Almanya sağlık dizinlerinden veri toplama uygulaması
"""

from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from typing import List, Dict, Any, Optional
import logging
import asyncio

# Yerel modüller
from config.settings import settings
from security.auth import (
    get_api_key, 
    verify_permissions, 
    default_rate_limit,
    limiter
)
from scraper.health_scraper import health_scraper, HealthProviderData

# Logging setup
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# FastAPI app oluştur
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Almanya sağlık dizinlerinden profesyonel veri toplama API'si",
    debug=settings.DEBUG
)

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Startup ve shutdown event handlers
@app.on_event("startup")
async def startup_event():
    """Uygulama başlatılırken çalışır"""
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} başlatılıyor...")
    logger.info(f"Debug modu: {settings.DEBUG}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS}")

@app.on_event("shutdown")
async def shutdown_event():
    """Uygulama kapatılırken çalışır"""
    logger.info("Uygulama kapatılıyor...")
    health_scraper.close()

# Ana endpoints
@app.get("/")
async def root():
    """Ana endpoint - API bilgilerini döner"""
    return {
        "message": "VeriSnap API'ye hoş geldiniz",
        "version": settings.APP_VERSION,
        "status": "active",
        "docs_url": "/docs"
    }

@app.get("/health")
async def health_check():
    """Sağlık kontrolü endpoint'i"""
    return {
        "status": "healthy",
        "timestamp": int(asyncio.get_event_loop().time()),
        "version": settings.APP_VERSION
    }

# Scraping endpoints
@app.post("/scrape/health-providers")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def scrape_health_providers(
    request,
    search_term: str = "arzt",
    location: str = "berlin", 
    sources: Optional[List[str]] = None,
    api_key: str = Depends(get_api_key),
    has_permission: bool = Depends(lambda api_key=Depends(get_api_key): verify_permissions(api_key, "scrape"))
):
    """
    Sağlık sağlayıcıları verilerini çeker
    
    Args:
        search_term: Arama terimi (örn: "arzt", "zahnarzt", "kardiologe")
        location: Şehir adı (örn: "berlin", "münchen", "hamburg")
        sources: Kullanılacak kaynaklar ("gelbeseiten", "das_oertliche")
        
    Returns:
        Dict: Çekilen veriler ve istatistikler
    """
    logger.info(f"Scraping başlatıldı: {search_term} in {location}")
    
    try:
        # Varsayılan kaynaklar
        if sources is None:
            sources = ["gelbeseiten", "das_oertliche"]
        
        # Veri çekme işlemini başlat
        results = await health_scraper.scrape_multiple_sources(
            search_term=search_term,
            location=location,
            sources=sources
        )
        
        # Sonuçları dictionary formatına çevir
        results_data = [result.to_dict() for result in results]
        
        response = {
            "success": True,
            "message": f"{len(results)} adet sağlık sağlayıcısı verisi çekildi",
            "data": {
                "search_term": search_term,
                "location": location,
                "sources_used": sources,
                "total_results": len(results),
                "results": results_data
            },
            "timestamp": asyncio.get_event_loop().time()
        }
        
        logger.info(f"Scraping tamamlandı: {len(results)} sonuç")
        return response
        
    except Exception as e:
        logger.error(f"Scraping hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping işlemi sırasında hata oluştu: {str(e)}"
        )

@app.post("/scrape/gelbeseiten")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def scrape_gelbeseiten_only(
    request,
    search_term: str = "arzt",
    location: str = "berlin",
    api_key: str = Depends(get_api_key),
    has_permission: bool = Depends(lambda api_key=Depends(get_api_key): verify_permissions(api_key, "scrape"))
):
    """Sadece Gelbe Seiten'den veri çeker"""
    logger.info(f"Gelbe Seiten scraping: {search_term} in {location}")
    
    try:
        results = await health_scraper.scrape_gelbeseiten(search_term, location)
        results_data = [result.to_dict() for result in results]
        
        return {
            "success": True,
            "message": f"Gelbe Seiten'den {len(results)} sonuç çekildi",
            "data": {
                "search_term": search_term,
                "location": location,
                "source": "gelbeseiten",
                "total_results": len(results),
                "results": results_data
            }
        }
        
    except Exception as e:
        logger.error(f"Gelbe Seiten scraping hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gelbe Seiten scraping hatası: {str(e)}"
        )

@app.post("/scrape/das-oertliche")
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/minute")
async def scrape_das_oertliche_only(
    request,
    search_term: str = "arzt",
    location: str = "berlin",
    api_key: str = Depends(get_api_key),
    has_permission: bool = Depends(lambda api_key=Depends(get_api_key): verify_permissions(api_key, "scrape"))
):
    """Sadece Das Örtliche'den veri çeker"""
    logger.info(f"Das Örtliche scraping: {search_term} in {location}")
    
    try:
        results = await health_scraper.scrape_das_oertliche(search_term, location)
        results_data = [result.to_dict() for result in results]
        
        return {
            "success": True,
            "message": f"Das Örtliche'den {len(results)} sonuç çekildi",
            "data": {
                "search_term": search_term,
                "location": location,
                "source": "das_oertliche",
                "total_results": len(results),
                "results": results_data
            }
        }
        
    except Exception as e:
        logger.error(f"Das Örtliche scraping hatası: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Das Örtliche scraping hatası: {str(e)}"
        )

# API bilgi endpoints
@app.get("/api/info")
async def api_info(api_key: str = Depends(get_api_key)):
    """API kullanım bilgilerini döner"""
    return {
        "api_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "rate_limits": {
            "requests_per_minute": settings.RATE_LIMIT_REQUESTS,
            "window_size_seconds": settings.RATE_LIMIT_PERIOD
        },
        "available_sources": ["gelbeseiten", "das_oertliche"],
        "supported_search_terms": [
            "arzt", "zahnarzt", "frauenarzt", "kardiologe", 
            "dermatologe", "orthopäde", "neurologie", "psychiater"
        ],
        "major_cities": [
            "berlin", "münchen", "hamburg", "köln", "frankfurt",
            "stuttgart", "düsseldorf", "dortmund", "essen", "leipzig"
        ]
    }

@app.get("/api/stats")
async def api_stats(api_key: str = Depends(get_api_key)):
    """API kullanım istatistiklerini döner"""
    return {
        "message": "İstatistik toplama özelliği gelecek sürümde eklenecek",
        "current_session": {
            "scraped_providers": len(health_scraper.scraped_data),
            "active_driver": health_scraper.driver is not None
        }
    }

# Test endpoints (sadece debug modunda)
if settings.DEBUG:
    @app.get("/debug/test-scraper")
    async def test_scraper():
        """Scraper test endpoint'i (sadece debug modunda)"""
        try:
            # Basit bir test scraping yap
            results = await health_scraper.scrape_gelbeseiten("zahnarzt", "münchen")
            return {
                "test_result": "success",
                "results_count": len(results),
                "sample_data": results[:2] if results else []
            }
        except Exception as e:
            return {
                "test_result": "failed",
                "error": str(e)
            }
"""
VeriSnap - Almanya Sağlık Hizmeti Sağlayıcı Dizinleri Web Scraping Aracı
Professional web scraping tool for German healthcare provider directories

Ana uygulama dosyası - FastAPI application setup ve configuration
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import asyncio
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime

# Local imports
from .config.settings import settings
from .config.logging import setup_logging, main_logger
from .database.operations import init_database
from .proxy.manager import proxy_manager
from .email.manager import email_manager
from .api.routes import router
from .security.rate_limiting import rate_limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management
    Startup ve shutdown olaylarını yönetir
    """
    # Startup
    main_logger.info("Starting VeriSnap application...")
    
    try:
        # Logging'i konfigüre et
        setup_logging()
        main_logger.info("Logging configured")
        
        # Veritabanını başlat
        await init_database()
        main_logger.info("Database initialized")
        
        # Proxy manager'ı başlat
        if settings.use_proxy:
            await proxy_manager.initialize()
            main_logger.info("Proxy manager initialized")
        
        # Email manager test et
        email_test = await email_manager.test_email_configuration()
        if email_test["success"]:
            main_logger.info("Email configuration verified")
        else:
            main_logger.warning(f"Email configuration issue: {email_test.get('error', 'Unknown error')}")
        
        main_logger.info("VeriSnap application started successfully")
        
    except Exception as e:
        main_logger.error(f"Failed to start application: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    main_logger.info("Shutting down VeriSnap application...")
    
    try:
        # Cleanup işlemleri burada yapılabilir
        main_logger.info("Application shutdown completed")
    except Exception as e:
        main_logger.error(f"Error during shutdown: {str(e)}")


def create_application() -> FastAPI:
    """
    FastAPI application factory
    
    Returns:
        FastAPI: Konfigüre edilmiş FastAPI instance
    """
    
    # FastAPI instance oluştur
    app = FastAPI(
        title="VeriSnap API",
        description="Almanya Sağlık Hizmeti Sağlayıcı Dizinleri Web Scraping Aracı",
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Trusted host middleware (production'da)
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Production'da specific hostlar belirtilmeli
        )
    
    # API routes'ları dahil et
    app.include_router(
        router,
        prefix="/api/v1"
    )
    
    # Ana sayfa endpoint'i
    @app.get("/", tags=["Root"])
    async def root():
        """
        Ana sayfa - API bilgileri
        """
        return {
            "name": "VeriSnap API",
            "description": "Almanya Sağlık Hizmeti Sağlayıcı Dizinleri Web Scraping Aracı",
            "version": settings.app_version,
            "status": "healthy",
            "docs_url": "/docs" if settings.debug else None,
            "features": {
                "web_scraping": "Almanya sağlık dizinlerinden veri toplama",
                "proxy_support": "Çoklu proxy rotation ve health check",
                "email_notifications": "SMTP ile e-posta bildirimleri",
                "rate_limiting": "API endpoint koruma",
                "authentication": "JWT token tabanlı kimlik doğrulama",
                "database": "SQLite/PostgreSQL veri saklama"
            },
            "supported_sites": settings.target_sites
        }
    
    # Global exception handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        HTTP exception handler
        """
        main_logger.warning(
            f"HTTP Exception: {exc.status_code}",
            detail=exc.detail,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "status_code": exc.status_code,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    # Generic exception handler
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """
        Generic exception handler
        """
        main_logger.error(
            f"Unhandled exception: {str(exc)}",
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host,
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error" if not settings.debug else str(exc),
                "status_code": 500,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    # Security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """
        Güvenlik header'larını ekler
        """
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Request logging middleware
        """
        import time
        start_time = time.time()
        
        # Request'i logla
        main_logger.info(
            f"Request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            content_length=request.headers.get("content-length", 0)
        )
        
        response = await call_next(request)
        
        # Response'u logla
        process_time = time.time() - start_time
        main_logger.info(
            f"Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=f"{process_time:.3f}s",
            client_ip=request.client.host
        )
        
        # Process time header'ı ekle
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    
    # Custom OpenAPI schema (sadece debug modunda)
    if settings.debug:
        def custom_openapi():
            if app.openapi_schema:
                return app.openapi_schema
            
            openapi_schema = get_openapi(
                title="VeriSnap API",
                version=settings.app_version,
                description="""
                # VeriSnap API
                
                Almanya Sağlık Hizmeti Sağlayıcı Dizinleri Web Scraping Aracı
                
                ## Özellikler
                
                - **Web Scraping**: Jameda, Doctolib gibi Almanya sağlık dizinlerinden veri toplama
                - **Proxy Desteği**: Çoklu proxy rotation ve automatic failover
                - **E-posta Bildirimleri**: SMTP ile işlem bildirimleri
                - **Rate Limiting**: API endpoint koruma ve güvenlik
                - **Authentication**: JWT token tabanlı kimlik doğrulama
                - **Veritabanı**: SQLite/PostgreSQL ile veri saklama
                
                ## Kullanım
                
                1. `/api/v1/auth/login` ile giriş yapın
                2. Dönen JWT token'ı Authorization header'ında kullanın: `Bearer <token>`
                3. `/api/v1/scraping/start` ile scraping işlemi başlatın
                4. `/api/v1/scraping/sessions` ile işlem durumunu takip edin
                
                ## Rate Limiting
                
                - Genel API: 100 request/saat
                - Login: 10 deneme/5 dakika
                - Scraping: 50 işlem/saat
                - E-posta: 20 e-posta/saat
                """,
                routes=app.routes,
            )
            
            # Security scheme ekle
            openapi_schema["components"]["securitySchemes"] = {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                },
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key"
                }
            }
            
            app.openapi_schema = openapi_schema
            return app.openapi_schema
        
        app.openapi = custom_openapi
    
    return app


# Global app instance
app = create_application()


# Uygulama çalıştırma fonksiyonu
def run_server():
    """
    Sunucuyu başlatır
    """
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug
    )


if __name__ == "__main__":
    run_server()
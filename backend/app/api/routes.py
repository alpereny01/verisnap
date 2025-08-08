"""
Ana API endpoints
Authentication, scraping, proxy ve email işlemleri
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import timedelta
import asyncio
import uuid

from ..database.operations import get_db, UserRepository, ScrapingRepository, ProxyRepository
from ..security.auth import (
    authenticate_user, create_access_token, get_current_active_user,
    require_scope, fake_users_db, get_password_hash
)
from ..security.rate_limiting import apply_rate_limit, rate_limiter, scrape_rate_limiter
from ..config.settings import settings
from ..config.logging import main_logger, security_logger
from ..scraper.orchestrator import scraping_orchestrator
from ..proxy.manager import proxy_manager
from ..email.manager import email_manager
from .schemas import *

# Router oluştur
router = APIRouter()


# Authentication Endpoints
@router.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Kullanıcı girişi
    JWT token döndürür
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=10, window_size=300)  # 5 dakikada 10 deneme
    
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        security_logger.warning(
            "Failed login attempt",
            username=form_data.username,
            ip=request.client.host,
            user_agent=request.headers.get("user-agent")
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": user.scopes},
        expires_delta=access_token_expires
    )
    
    security_logger.info(
        "Successful login",
        username=user.username,
        ip=request.client.host
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/register", response_model=UserResponse, tags=["Authentication"])
async def register(
    request: Request,
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Yeni kullanıcı kaydı
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=5, window_size=3600)  # Saatte 5 kayıt
    
    # Kullanıcı zaten var mı kontrol et
    existing_user = UserRepository.get_user_by_username(db, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    existing_email = UserRepository.get_user_by_email(db, user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Şifreyi hash'le
    hashed_password = get_password_hash(user_data.password)
    
    # Kullanıcıyı oluştur
    user = UserRepository.create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        scopes=user_data.scopes
    )
    
    main_logger.info(f"New user registered: {user.username}")
    
    return user


@router.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_current_user_info(
    current_user = Depends(get_current_active_user)
):
    """
    Mevcut kullanıcı bilgilerini döndürür
    """
    return current_user


# Scraping Endpoints
@router.post("/scraping/start", response_model=ScrapingResponse, tags=["Scraping"])
async def start_scraping(
    request: Request,
    scraping_request: ScrapingRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(require_scope("scrape")),
    db: Session = Depends(get_db)
):
    """
    Yeni scraping işlemi başlatır
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=50, window_size=3600)  # Saatte 50 scraping
    
    # Scraping limit kontrolü
    await scrape_rate_limiter.check_scraping_limit(scraping_request.target_site)
    
    try:
        # Session oluştur
        session = ScrapingRepository.create_session(
            db=db,
            user_id=current_user.id if hasattr(current_user, 'id') else 1,  # Fake DB için
            target_site=scraping_request.target_site,
            start_url=f"https://{scraping_request.target_site}/search",
            max_pages=scraping_request.max_pages,
            delay=scraping_request.delay,
            use_proxy=scraping_request.use_proxy,
            config={
                "specialty": scraping_request.specialty,
                "city": scraping_request.city,
                "headless": scraping_request.headless,
                "notify_email": scraping_request.notify_email
            }
        )
        
        # Background task olarak scraping'i başlat
        background_tasks.add_task(
            run_scraping_background,
            session.session_id,
            scraping_request.dict()
        )
        
        # Scraping counter'ı artır
        await scrape_rate_limiter.start_scraping(scraping_request.target_site)
        
        main_logger.info(
            f"Scraping session started",
            session_id=session.session_id,
            target_site=scraping_request.target_site,
            user=current_user.username if hasattr(current_user, 'username') else 'unknown'
        )
        
        return ScrapingResponse(
            session_id=session.session_id,
            status=StatusEnum.PENDING,
            message="Scraping işlemi başlatıldı",
            estimated_duration=scraping_request.max_pages * scraping_request.delay
        )
        
    except Exception as e:
        main_logger.error(f"Failed to start scraping: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scraping başlatılamadı: {str(e)}"
        )


async def run_scraping_background(session_id: str, scraping_params: Dict[str, Any]):
    """
    Background'da scraping çalıştırır
    """
    try:
        # E-posta bildirimi gönder (başlama)
        if scraping_params.get("notify_email"):
            await email_manager.send_scraping_notification(
                notification_type="started",
                user_email=scraping_params["notify_email"],
                session_data={
                    "session_id": session_id,
                    "target_site": scraping_params["target_site"],
                    "start_url": f"https://{scraping_params['target_site']}/search",
                    "max_pages": scraping_params["max_pages"],
                    "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            )
        
        # Scraping'i çalıştır
        result = await scraping_orchestrator.run_scraping_session(
            session_id=session_id,
            target_site=scraping_params["target_site"],
            search_params=scraping_params
        )
        
        # E-posta bildirimi gönder (tamamlama/hata)
        if scraping_params.get("notify_email"):
            notification_type = "completed" if result["success"] else "error"
            await email_manager.send_scraping_notification(
                notification_type=notification_type,
                user_email=scraping_params["notify_email"],
                session_data={
                    "session_id": session_id,
                    "target_site": scraping_params["target_site"],
                    "total_records": result.get("total_records", 0),
                    "pages_scraped": result.get("pages_scraped", 0),
                    "success_rate": result.get("success_rate", 0),
                    "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "duration": f"{result.get('duration', 0):.2f} saniye",
                    "error_message": result.get("error", "")
                }
            )
        
    except Exception as e:
        main_logger.error(f"Background scraping failed for session {session_id}: {str(e)}")
    finally:
        # Scraping counter'ı azalt
        await scrape_rate_limiter.finish_scraping(scraping_params["target_site"])


@router.get("/scraping/sessions", response_model=List[ScrapingSessionResponse], tags=["Scraping"])
async def get_scraping_sessions(
    request: Request,
    skip: int = 0,
    limit: int = 50,
    status: Optional[str] = None,
    current_user = Depends(require_scope("read")),
    db: Session = Depends(get_db)
):
    """
    Scraping session'larını listeler
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    # TODO: Database'den session'ları getir
    # Bu örnekte boş liste döndürüyoruz
    return []


@router.get("/scraping/sessions/{session_id}", response_model=ScrapingSessionResponse, tags=["Scraping"])
async def get_scraping_session(
    request: Request,
    session_id: str,
    current_user = Depends(require_scope("read")),
    db: Session = Depends(get_db)
):
    """
    Belirli bir scraping session'ı getirir
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    session = ScrapingRepository.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return session


@router.get("/scraping/sessions/{session_id}/data", response_model=List[HealthcareProviderResponse], tags=["Scraping"])
async def get_session_data(
    request: Request,
    session_id: str,
    skip: int = 0,
    limit: int = 100,
    current_user = Depends(require_scope("read")),
    db: Session = Depends(get_db)
):
    """
    Session'a ait toplanan veriyi döndürür
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    # Session var mı kontrol et
    session = ScrapingRepository.get_session_by_id(db, session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Veriyi getir
    data = ScrapingRepository.get_session_data(db, session.id, skip, limit)
    return data


# Proxy Endpoints
@router.get("/proxy/stats", response_model=Dict[str, Any], tags=["Proxy"])
async def get_proxy_stats(
    request: Request,
    current_user = Depends(require_scope("read"))
):
    """
    Proxy istatistiklerini döndürür
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    stats = await proxy_manager.get_proxy_stats()
    return stats


@router.post("/proxy/health-check", response_model=Dict[str, Any], tags=["Proxy"])
async def trigger_proxy_health_check(
    request: Request,
    current_user = Depends(require_scope("admin"))
):
    """
    Proxy health check'i tetikler
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=10, window_size=300)
    
    if proxy_manager.enabled:
        await proxy_manager.rotator.check_all_proxies_health()
        return {"message": "Proxy health check completed"}
    else:
        return {"message": "Proxy is disabled"}


# Email Endpoints
@router.post("/email/send", response_model=EmailResponse, tags=["Email"])
async def send_email(
    request: Request,
    email_request: EmailSendRequest,
    current_user = Depends(require_scope("write"))
):
    """
    E-posta gönderir
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=20, window_size=3600)  # Saatte 20 e-posta
    
    try:
        if email_request.template_name:
            # Template ile gönder
            result = await email_manager.send_template_email(
                template_name=email_request.template_name,
                to_emails=email_request.to_emails,
                variables=email_request.template_variables or {}
            )
        else:
            # Direct gönder
            result = await email_manager.sender.send_email(
                to_emails=email_request.to_emails,
                subject=email_request.subject,
                html_content=email_request.html_content,
                text_content=email_request.text_content,
                cc_emails=email_request.cc_emails,
                bcc_emails=email_request.bcc_emails
            )
        
        return EmailResponse(**result)
        
    except Exception as e:
        main_logger.error(f"Failed to send email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"E-posta gönderilemedi: {str(e)}"
        )


@router.get("/email/templates", response_model=List[str], tags=["Email"])
async def list_email_templates(
    request: Request,
    current_user = Depends(require_scope("read"))
):
    """
    E-posta şablonlarını listeler
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    return email_manager.list_templates()


@router.post("/email/test", response_model=Dict[str, Any], tags=["Email"])
async def test_email_configuration(
    request: Request,
    current_user = Depends(require_scope("admin"))
):
    """
    E-posta konfigürasyonunu test eder
    """
    # Rate limiting
    await apply_rate_limit(request, max_requests=5, window_size=300)
    
    result = await email_manager.test_email_configuration()
    return result


# System Endpoints
@router.get("/system/health", response_model=HealthResponse, tags=["System"])
async def health_check(request: Request):
    """
    Sistem sağlık kontrolü
    """
    try:
        # Database kontrol
        db_status = {"status": "healthy", "error": None}
        try:
            with db_manager.get_session() as db:
                db.execute("SELECT 1")
        except Exception as e:
            db_status = {"status": "unhealthy", "error": str(e)}
        
        # Proxy kontrol
        proxy_stats = await proxy_manager.get_proxy_stats()
        
        # Email kontrol
        email_status = await email_manager.test_email_configuration()
        
        overall_status = "healthy"
        if db_status["status"] != "healthy" or not email_status.get("success", False):
            overall_status = "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now(),
            version=settings.app_version,
            database=db_status,
            proxy=proxy_stats,
            email={"status": "healthy" if email_status.get("success") else "unhealthy"},
            uptime=0.0  # TODO: Implement uptime tracking
        )
        
    except Exception as e:
        main_logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service unhealthy"
        )


@router.get("/system/stats", response_model=SystemStats, tags=["System"])
async def get_system_stats(
    request: Request,
    current_user = Depends(require_scope("admin"))
):
    """
    Sistem istatistiklerini döndürür
    """
    # Rate limiting
    await apply_rate_limit(request)
    
    # TODO: Implement real statistics
    return SystemStats(
        total_users=0,
        total_sessions=0,
        total_scraped_records=0,
        active_sessions=0,
        failed_sessions=0,
        success_rate=0.0,
        avg_session_duration=0.0,
        most_popular_sites=[],
        proxy_stats=await proxy_manager.get_proxy_stats()
    )


@router.get("/rate-limit/info", response_model=Dict[str, Any], tags=["System"])
async def get_rate_limit_info(
    request: Request,
    current_user = Depends(get_current_active_user)
):
    """
    Rate limit bilgilerini döndürür
    """
    ip = request.client.host
    info = await rate_limiter.get_rate_limit_info(ip, "ip")
    return info
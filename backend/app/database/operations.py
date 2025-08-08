"""
Veritabanı işlemleri
Database connection, CRUD operations ve migrations
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import asyncio
import uuid
from contextlib import asynccontextmanager

from ..config.settings import settings
from ..config.logging import main_logger
from .models import Base, User, ScrapingSession, ScrapedData, ProxyServer, EmailTemplate


class DatabaseManager:
    """Veritabanı yönetim sınıfı"""
    
    def __init__(self):
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._is_initialized = False
    
    def initialize(self):
        """Veritabanı bağlantısını başlatır"""
        try:
            # Sync engine
            if "sqlite" in settings.database_url:
                self.engine = create_engine(
                    settings.database_url,
                    echo=settings.database_echo,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                self.engine = create_engine(
                    settings.database_url,
                    echo=settings.database_echo
                )
            
            # Async engine
            async_url = settings.database_url.replace("sqlite://", "sqlite+aiosqlite://")
            if "postgresql" in settings.database_url:
                async_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
            
            if "sqlite" in async_url:
                self.async_engine = create_async_engine(
                    async_url,
                    echo=settings.database_echo,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                self.async_engine = create_async_engine(
                    async_url,
                    echo=settings.database_echo
                )
            
            # Session makers
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            self.AsyncSessionLocal = sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._is_initialized = True
            main_logger.info("Database connection initialized", database_url=settings.database_url)
            
        except Exception as e:
            main_logger.error("Failed to initialize database", error=str(e))
            raise
    
    def create_tables(self):
        """Tabloları oluşturur"""
        try:
            Base.metadata.create_all(bind=self.engine)
            main_logger.info("Database tables created successfully")
        except Exception as e:
            main_logger.error("Failed to create database tables", error=str(e))
            raise
    
    def get_session(self) -> Session:
        """Sync database session döndürür"""
        if not self._is_initialized:
            self.initialize()
        return self.SessionLocal()
    
    @asynccontextmanager
    async def get_async_session(self):
        """Async database session döndürür"""
        if not self._is_initialized:
            self.initialize()
        
        async with self.AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


# Global database manager instance
db_manager = DatabaseManager()


class UserRepository:
    """Kullanıcı veritabanı işlemleri"""
    
    @staticmethod
    def create_user(db: Session, username: str, email: str, hashed_password: str, 
                   full_name: Optional[str] = None, scopes: List[str] = None) -> User:
        """
        Yeni kullanıcı oluşturur
        
        Args:
            db: Database session
            username: Kullanıcı adı
            email: E-posta adresi
            hashed_password: Hash'lenmiş şifre
            full_name: Tam ad
            scopes: Yetkiler
            
        Returns:
            User: Oluşturulan kullanıcı
        """
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            scopes=scopes or []
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """
        Kullanıcı adına göre kullanıcı getirir
        
        Args:
            db: Database session
            username: Kullanıcı adı
            
        Returns:
            Optional[User]: Kullanıcı objesi
        """
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """
        E-posta adresine göre kullanıcı getirir
        
        Args:
            db: Database session
            email: E-posta adresi
            
        Returns:
            Optional[User]: Kullanıcı objesi
        """
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """
        Kullanıcı listesi getirir
        
        Args:
            db: Database session
            skip: Atlanacak kayıt sayısı
            limit: Maksimum kayıt sayısı
            
        Returns:
            List[User]: Kullanıcı listesi
        """
        return db.query(User).offset(skip).limit(limit).all()


class ScrapingRepository:
    """Scraping veritabanı işlemleri"""
    
    @staticmethod
    def create_session(db: Session, user_id: int, target_site: str, start_url: str,
                      max_pages: int = 10, delay: int = 5, use_proxy: bool = False,
                      config: Dict[str, Any] = None) -> ScrapingSession:
        """
        Yeni scraping session oluşturur
        
        Args:
            db: Database session
            user_id: Kullanıcı ID
            target_site: Hedef site
            start_url: Başlangıç URL'si
            max_pages: Maksimum sayfa sayısı
            delay: Request arası bekleme süresi
            use_proxy: Proxy kullanım durumu
            config: Ek konfigürasyon
            
        Returns:
            ScrapingSession: Oluşturulan session
        """
        session_id = str(uuid.uuid4())
        session = ScrapingSession(
            session_id=session_id,
            user_id=user_id,
            target_site=target_site,
            start_url=start_url,
            max_pages=max_pages,
            delay_between_requests=delay,
            use_proxy=use_proxy,
            config=config or {}
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    @staticmethod
    def get_session_by_id(db: Session, session_id: str) -> Optional[ScrapingSession]:
        """
        Session ID'ye göre session getirir
        
        Args:
            db: Database session
            session_id: Session ID
            
        Returns:
            Optional[ScrapingSession]: Session objesi
        """
        return db.query(ScrapingSession).filter(ScrapingSession.session_id == session_id).first()
    
    @staticmethod
    def update_session_status(db: Session, session_id: str, status: str,
                            pages_scraped: int = None, total_records: int = None,
                            error_log: str = None) -> Optional[ScrapingSession]:
        """
        Session durumunu günceller
        
        Args:
            db: Database session
            session_id: Session ID
            status: Yeni durum
            pages_scraped: Scraping yapılan sayfa sayısı
            total_records: Toplam kayıt sayısı
            error_log: Hata logu
            
        Returns:
            Optional[ScrapingSession]: Güncellenmiş session
        """
        session = db.query(ScrapingSession).filter(ScrapingSession.session_id == session_id).first()
        if session:
            session.status = status
            if pages_scraped is not None:
                session.pages_scraped = pages_scraped
            if total_records is not None:
                session.total_records = total_records
            if error_log is not None:
                session.error_log = error_log
            
            db.commit()
            db.refresh(session)
        return session
    
    @staticmethod
    def save_scraped_data(db: Session, session_id: int, data: Dict[str, Any]) -> ScrapedData:
        """
        Toplanan veriyi kaydeder
        
        Args:
            db: Database session
            session_id: Session ID
            data: Toplanan veri
            
        Returns:
            ScrapedData: Kaydedilen veri
        """
        scraped_data = ScrapedData(
            session_id=session_id,
            source_url=data.get('source_url', ''),
            page_number=data.get('page_number', 1),
            provider_name=data.get('provider_name'),
            specialty=data.get('specialty'),
            address=data.get('address'),
            city=data.get('city'),
            postal_code=data.get('postal_code'),
            phone=data.get('phone'),
            email=data.get('email'),
            website=data.get('website'),
            rating=data.get('rating'),
            review_count=data.get('review_count'),
            raw_data=data,
            confidence_score=data.get('confidence_score', 0.0)
        )
        db.add(scraped_data)
        db.commit()
        db.refresh(scraped_data)
        return scraped_data
    
    @staticmethod
    def get_session_data(db: Session, session_id: int, skip: int = 0, limit: int = 100) -> List[ScrapedData]:
        """
        Session'a ait veriyi getirir
        
        Args:
            db: Database session
            session_id: Session ID
            skip: Atlanacak kayıt sayısı
            limit: Maksimum kayıt sayısı
            
        Returns:
            List[ScrapedData]: Toplanan veri listesi
        """
        return db.query(ScrapedData).filter(
            ScrapedData.session_id == session_id
        ).offset(skip).limit(limit).all()


class ProxyRepository:
    """Proxy veritabanı işlemleri"""
    
    @staticmethod
    def create_proxy(db: Session, name: str, host: str, port: int,
                    username: str = None, password: str = None,
                    proxy_type: str = "http", country: str = None) -> ProxyServer:
        """
        Yeni proxy oluşturur
        
        Args:
            db: Database session
            name: Proxy adı
            host: Host adresi
            port: Port numarası
            username: Kullanıcı adı
            password: Şifre
            proxy_type: Proxy tipi
            country: Ülke
            
        Returns:
            ProxyServer: Oluşturulan proxy
        """
        proxy = ProxyServer(
            name=name,
            host=host,
            port=port,
            username=username,
            password=password,
            proxy_type=proxy_type,
            country=country
        )
        db.add(proxy)
        db.commit()
        db.refresh(proxy)
        return proxy
    
    @staticmethod
    def get_active_proxies(db: Session) -> List[ProxyServer]:
        """
        Aktif proxy'leri getirir
        
        Args:
            db: Database session
            
        Returns:
            List[ProxyServer]: Aktif proxy listesi
        """
        return db.query(ProxyServer).filter(
            ProxyServer.is_active == True,
            ProxyServer.is_healthy == True
        ).all()
    
    @staticmethod
    def update_proxy_health(db: Session, proxy_id: int, is_healthy: bool,
                          response_time: float = None) -> Optional[ProxyServer]:
        """
        Proxy sağlık durumunu günceller
        
        Args:
            db: Database session
            proxy_id: Proxy ID
            is_healthy: Sağlıklı mı
            response_time: Yanıt süresi
            
        Returns:
            Optional[ProxyServer]: Güncellenmiş proxy
        """
        proxy = db.query(ProxyServer).filter(ProxyServer.id == proxy_id).first()
        if proxy:
            proxy.is_healthy = is_healthy
            if response_time is not None:
                proxy.response_time = response_time
            proxy.last_checked_at = datetime.now()
            
            db.commit()
            db.refresh(proxy)
        return proxy


def get_db():
    """Database session dependency için"""
    db = db_manager.get_session()
    try:
        yield db
    finally:
        db.close()


async def init_database():
    """Veritabanını başlatır"""
    db_manager.initialize()
    db_manager.create_tables()
    main_logger.info("Database initialized successfully")
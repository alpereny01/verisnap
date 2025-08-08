"""
Veritabanı migration script
İlk kurulum ve tablo oluşturma
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent))

from app.database.operations import init_database, db_manager
from app.database.models import User
from app.security.auth import get_password_hash
from app.config.settings import settings
from app.config.logging import main_logger


async def create_default_users():
    """Default kullanıcıları oluşturur"""
    try:
        with db_manager.get_session() as db:
            # Admin kullanıcısı var mı kontrol et
            admin_user = db.query(User).filter(User.username == "admin").first()
            
            if not admin_user:
                # Admin kullanıcısı oluştur
                admin_user = User(
                    username="admin",
                    email="admin@verisnap.com",
                    full_name="Administrator",
                    hashed_password=get_password_hash("admin123"),
                    is_active=True,
                    is_admin=True,
                    scopes=["read", "write", "admin", "scrape"]
                )
                db.add(admin_user)
                main_logger.info("Created admin user: admin/admin123")
            
            # Scraper kullanıcısı var mı kontrol et
            scraper_user = db.query(User).filter(User.username == "scraper").first()
            
            if not scraper_user:
                # Scraper kullanıcısı oluştur
                scraper_user = User(
                    username="scraper",
                    email="scraper@verisnap.com",
                    full_name="Scraper User",
                    hashed_password=get_password_hash("scraper123"),
                    is_active=True,
                    is_admin=False,
                    scopes=["read", "scrape"]
                )
                db.add(scraper_user)
                main_logger.info("Created scraper user: scraper/scraper123")
            
            db.commit()
            main_logger.info("Default users created successfully")
            
    except Exception as e:
        main_logger.error(f"Failed to create default users: {str(e)}")
        raise


async def run_migrations():
    """Migration'ları çalıştırır"""
    try:
        main_logger.info("Starting database migrations...")
        
        # Veritabanını başlat
        await init_database()
        main_logger.info("Database tables created")
        
        # Default kullanıcıları oluştur
        await create_default_users()
        
        main_logger.info("Database migrations completed successfully")
        
    except Exception as e:
        main_logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_migrations())
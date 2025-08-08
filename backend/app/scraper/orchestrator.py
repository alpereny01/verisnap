"""
Web scraping modülü
Almanya sağlık hizmeti sağlayıcı dizinlerinden veri toplama
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
import re
from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse
import json
import time
from dataclasses import dataclass, asdict
import random

from ..config.settings import settings
from ..config.logging import scraper_logger
from ..proxy.manager import proxy_manager, ProxyConfig
from ..database.operations import ScrapingRepository, db_manager


@dataclass
class HealthcareProvider:
    """Sağlık hizmeti sağlayıcı veri modeli"""
    name: Optional[str] = None
    specialty: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source_url: Optional[str] = None
    additional_info: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Dict formatına çevirir"""
        return asdict(self)
    
    def calculate_confidence_score(self) -> float:
        """Veri güvenilirlik skorunu hesaplar"""
        score = 0.0
        fields = [self.name, self.address, self.phone, self.email]
        filled_fields = sum(1 for field in fields if field and field.strip())
        
        # Temel alan doluluk skoru
        score += (filled_fields / len(fields)) * 70
        
        # Özel alan bonusları
        if self.rating is not None:
            score += 10
        if self.website:
            score += 10
        if self.specialty:
            score += 10
        
        return min(score, 100.0)


class BaseScraper:
    """Base scraper sınıfı"""
    
    def __init__(self, site_name: str):
        self.site_name = site_name
        self.session = None
        self.browser = None
        self.page = None
        self.proxy = None
        self.stats = {
            "pages_scraped": 0,
            "total_records": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
    
    async def setup(self, use_proxy: bool = False, headless: bool = True):
        """Scraper'ı hazırlar"""
        self.stats["start_time"] = time.time()
        
        if use_proxy:
            self.proxy = await proxy_manager.get_proxy_for_request()
            if self.proxy:
                scraper_logger.info(f"Using proxy: {self.proxy.host}:{self.proxy.port}")
        
        # Playwright setup
        self.playwright = await async_playwright().start()
        
        browser_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--disable-gpu"
        ]
        
        if self.proxy:
            proxy_config = {
                "server": f"http://{self.proxy.host}:{self.proxy.port}"
            }
            if self.proxy.username and self.proxy.password:
                proxy_config["username"] = self.proxy.username
                proxy_config["password"] = self.proxy.password
        else:
            proxy_config = None
        
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=browser_args,
            proxy=proxy_config
        )
        
        # Context ve page oluştur
        context = await self.browser.new_context(
            user_agent=settings.user_agent,
            viewport={"width": 1920, "height": 1080}
        )
        
        self.page = await context.new_page()
        
        # HTTP session (BeautifulSoup için)
        self.session = await proxy_manager.create_aiohttp_session(self.proxy)
    
    async def cleanup(self):
        """Kaynakları temizler"""
        self.stats["end_time"] = time.time()
        
        if self.session:
            await self.session.close()
        
        if self.page:
            await self.page.close()
        
        if self.browser:
            await self.browser.close()
        
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def wait_between_requests(self, min_delay: int = None, max_delay: int = None):
        """Request'ler arası bekleme"""
        if min_delay is None:
            min_delay = settings.retry_delay
        if max_delay is None:
            max_delay = min_delay * 2
        
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)
    
    def extract_clean_text(self, element) -> Optional[str]:
        """Temiz metin extract eder"""
        if not element:
            return None
        
        text = element.get_text(strip=True) if hasattr(element, 'get_text') else str(element).strip()
        
        # Çoklu boşlukları tek boşluğa çevir
        text = re.sub(r'\s+', ' ', text)
        
        return text if text else None
    
    def extract_phone(self, text: str) -> Optional[str]:
        """Telefon numarası extract eder"""
        if not text:
            return None
        
        # Almanya telefon numarası pattern'leri
        patterns = [
            r'\+49[\s\-]?\d{2,4}[\s\-]?\d{3,}[\s\-]?\d{2,}',  # +49 ile başlayan
            r'0\d{2,4}[\s\-/]?\d{3,}[\s\-/]?\d{2,}',  # 0 ile başlayan
            r'\(\d{2,4}\)[\s\-]?\d{3,}[\s\-]?\d{2,}'  # (0xx) formatı
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                phone = match.group()
                # Temizle
                phone = re.sub(r'[^\d\+\(\)]', '', phone)
                return phone
        
        return None
    
    def extract_email(self, text: str) -> Optional[str]:
        """E-posta adresi extract eder"""
        if not text:
            return None
        
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(pattern, text)
        
        return match.group() if match else None
    
    def extract_postal_code(self, text: str) -> Optional[str]:
        """Almanya posta kodu extract eder"""
        if not text:
            return None
        
        # Almanya posta kodu formatı: 5 haneli sayı
        pattern = r'\b\d{5}\b'
        match = re.search(pattern, text)
        
        return match.group() if match else None


class JamedaScraper(BaseScraper):
    """Jameda.de scraper sınıfı"""
    
    def __init__(self):
        super().__init__("jameda.de")
        self.base_url = "https://www.jameda.de"
    
    async def search_providers(self, specialty: str, city: str, max_pages: int = 10) -> List[HealthcareProvider]:
        """
        Jameda'da sağlık hizmeti sağlayıcıları arar
        
        Args:
            specialty: Uzmanlık alanı
            city: Şehir
            max_pages: Maksimum sayfa sayısı
            
        Returns:
            List[HealthcareProvider]: Bulunan sağlayıcılar
        """
        providers = []
        
        try:
            # Arama URL'si oluştur
            search_url = f"{self.base_url}/aerzte/{specialty.lower()}/{city.lower()}/"
            
            scraper_logger.info(f"Starting Jameda search: {search_url}")
            
            for page_num in range(1, max_pages + 1):
                page_url = f"{search_url}?page={page_num}"
                
                try:
                    await self.page.goto(page_url, wait_until="networkidle")
                    await self.wait_between_requests()
                    
                    # Sayfa içeriğini al
                    content = await self.page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Doktor kartlarını bul
                    doctor_cards = soup.find_all('div', class_='search-list-entry')
                    
                    if not doctor_cards:
                        scraper_logger.info(f"No more results found on page {page_num}")
                        break
                    
                    for card in doctor_cards:
                        provider = await self._extract_jameda_provider(card, page_url)
                        if provider and provider.name:
                            providers.append(provider)
                    
                    self.stats["pages_scraped"] += 1
                    scraper_logger.info(f"Scraped page {page_num}, found {len(doctor_cards)} providers")
                    
                except Exception as e:
                    self.stats["errors"] += 1
                    scraper_logger.error(f"Error scraping page {page_num}: {str(e)}")
                    continue
            
            self.stats["total_records"] = len(providers)
            scraper_logger.info(f"Jameda scraping completed: {len(providers)} providers found")
            
        except Exception as e:
            scraper_logger.error(f"Jameda scraping failed: {str(e)}")
            self.stats["errors"] += 1
        
        return providers
    
    async def _extract_jameda_provider(self, card_element, source_url: str) -> Optional[HealthcareProvider]:
        """Jameda provider kartından veri extract eder"""
        try:
            provider = HealthcareProvider(source_url=source_url)
            
            # İsim
            name_elem = card_element.find('a', class_='doc-name')
            if name_elem:
                provider.name = self.extract_clean_text(name_elem)
            
            # Uzmanlık
            specialty_elem = card_element.find('span', class_='doc-specialization')
            if specialty_elem:
                provider.specialty = self.extract_clean_text(specialty_elem)
            
            # Adres
            address_elem = card_element.find('div', class_='practice-address')
            if address_elem:
                address_text = self.extract_clean_text(address_elem)
                provider.address = address_text
                
                # Posta kodu ve şehir extract et
                postal_code = self.extract_postal_code(address_text)
                if postal_code:
                    provider.postal_code = postal_code
                    # Posta kodundan sonraki kelime genellikle şehir
                    parts = address_text.split(postal_code)
                    if len(parts) > 1:
                        city_part = parts[1].strip().split()[0] if parts[1].strip() else None
                        if city_part:
                            provider.city = city_part
            
            # Telefon
            phone_elem = card_element.find('a', href=re.compile(r'tel:'))
            if phone_elem:
                phone_text = phone_elem.get('href', '').replace('tel:', '')
                provider.phone = phone_text.strip()
            
            # Rating
            rating_elem = card_element.find('div', class_='rating-stars')
            if rating_elem:
                rating_text = rating_elem.get('data-rating')
                if rating_text:
                    try:
                        provider.rating = float(rating_text)
                    except ValueError:
                        pass
            
            # Review count
            review_elem = card_element.find('span', class_='rating-count')
            if review_elem:
                review_text = self.extract_clean_text(review_elem)
                if review_text:
                    numbers = re.findall(r'\d+', review_text)
                    if numbers:
                        provider.review_count = int(numbers[0])
            
            return provider
            
        except Exception as e:
            scraper_logger.error(f"Error extracting Jameda provider: {str(e)}")
            return None


class DoctolibScraper(BaseScraper):
    """Doctolib.de scraper sınıfı"""
    
    def __init__(self):
        super().__init__("doctolib.de")
        self.base_url = "https://www.doctolib.de"
    
    async def search_providers(self, specialty: str, city: str, max_pages: int = 10) -> List[HealthcareProvider]:
        """
        Doctolib'de sağlık hizmeti sağlayıcıları arar
        
        Args:
            specialty: Uzmanlık alanı
            city: Şehir
            max_pages: Maksimum sayfa sayısı
            
        Returns:
            List[HealthcareProvider]: Bulunan sağlayıcılar
        """
        providers = []
        
        try:
            # Arama URL'si oluştur
            search_url = f"{self.base_url}/arzt/{city.lower()}"
            
            scraper_logger.info(f"Starting Doctolib search: {search_url}")
            
            await self.page.goto(search_url, wait_until="networkidle")
            
            # Uzmanlık alanı seç (varsa)
            try:
                specialty_selector = f"text={specialty}"
                await self.page.click(specialty_selector, timeout=5000)
                await self.wait_between_requests()
            except:
                pass  # Uzmanlık alanı seçimi başarısız
            
            for page_num in range(1, max_pages + 1):
                try:
                    # Sayfa içeriğini al
                    content = await self.page.content()
                    soup = BeautifulSoup(content, 'html.parser')
                    
                    # Doktor kartlarını bul
                    doctor_cards = soup.find_all('div', class_='searchResult-item')
                    
                    if not doctor_cards:
                        scraper_logger.info(f"No more results found on page {page_num}")
                        break
                    
                    for card in doctor_cards:
                        provider = await self._extract_doctolib_provider(card, self.page.url)
                        if provider and provider.name:
                            providers.append(provider)
                    
                    self.stats["pages_scraped"] += 1
                    scraper_logger.info(f"Scraped page {page_num}, found {len(doctor_cards)} providers")
                    
                    # Sonraki sayfa
                    try:
                        next_button = await self.page.query_selector('a[aria-label="Next page"]')
                        if next_button:
                            await next_button.click()
                            await self.page.wait_for_load_state("networkidle")
                            await self.wait_between_requests()
                        else:
                            break
                    except:
                        break
                    
                except Exception as e:
                    self.stats["errors"] += 1
                    scraper_logger.error(f"Error scraping Doctolib page {page_num}: {str(e)}")
                    continue
            
            self.stats["total_records"] = len(providers)
            scraper_logger.info(f"Doctolib scraping completed: {len(providers)} providers found")
            
        except Exception as e:
            scraper_logger.error(f"Doctolib scraping failed: {str(e)}")
            self.stats["errors"] += 1
        
        return providers
    
    async def _extract_doctolib_provider(self, card_element, source_url: str) -> Optional[HealthcareProvider]:
        """Doctolib provider kartından veri extract eder"""
        try:
            provider = HealthcareProvider(source_url=source_url)
            
            # İsim
            name_elem = card_element.find('span', class_='doctor-name')
            if name_elem:
                provider.name = self.extract_clean_text(name_elem)
            
            # Uzmanlık
            specialty_elem = card_element.find('div', class_='doctor-speciality')
            if specialty_elem:
                provider.specialty = self.extract_clean_text(specialty_elem)
            
            # Adres
            address_elem = card_element.find('div', class_='doctor-address')
            if address_elem:
                address_text = self.extract_clean_text(address_elem)
                provider.address = address_text
                
                # Posta kodu ve şehir extract et
                postal_code = self.extract_postal_code(address_text)
                if postal_code:
                    provider.postal_code = postal_code
                    parts = address_text.split(postal_code)
                    if len(parts) > 1:
                        city_part = parts[1].strip().split()[0] if parts[1].strip() else None
                        if city_part:
                            provider.city = city_part
            
            return provider
            
        except Exception as e:
            scraper_logger.error(f"Error extracting Doctolib provider: {str(e)}")
            return None


class ScrapingOrchestrator:
    """Scraping işlemlerini koordine eden ana sınıf"""
    
    def __init__(self):
        self.scrapers = {
            "jameda.de": JamedaScraper,
            "doctolib.de": DoctolibScraper
        }
    
    async def run_scraping_session(
        self,
        session_id: str,
        target_site: str,
        search_params: Dict[str, Any],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Scraping session'ı çalıştırır
        
        Args:
            session_id: Session ID
            target_site: Hedef site
            search_params: Arama parametreleri
            progress_callback: İlerleme callback fonksiyonu
            
        Returns:
            Dict: Scraping sonuçları
        """
        scraper_logger.info(f"Starting scraping session {session_id} for {target_site}")
        
        if target_site not in self.scrapers:
            return {
                "success": False,
                "error": f"Unsupported target site: {target_site}",
                "session_id": session_id
            }
        
        scraper_class = self.scrapers[target_site]
        scraper = scraper_class()
        
        try:
            # Scraper'ı hazırla
            await scraper.setup(
                use_proxy=search_params.get("use_proxy", False),
                headless=search_params.get("headless", True)
            )
            
            # Database session'ını güncelle
            with db_manager.get_session() as db:
                ScrapingRepository.update_session_status(
                    db, session_id, "running", pages_scraped=0, total_records=0
                )
            
            # Scraping'i başlat
            providers = await scraper.search_providers(
                specialty=search_params.get("specialty", ""),
                city=search_params.get("city", ""),
                max_pages=search_params.get("max_pages", 10)
            )
            
            # Verileri veritabanına kaydet
            saved_count = 0
            with db_manager.get_session() as db:
                db_session = ScrapingRepository.get_session_by_id(db, session_id)
                if db_session:
                    for provider in providers:
                        provider_data = provider.to_dict()
                        provider_data["confidence_score"] = provider.calculate_confidence_score()
                        
                        ScrapingRepository.save_scraped_data(
                            db, db_session.id, provider_data
                        )
                        saved_count += 1
                    
                    # Session'ı tamamla
                    ScrapingRepository.update_session_status(
                        db, session_id, "completed",
                        pages_scraped=scraper.stats["pages_scraped"],
                        total_records=saved_count
                    )
            
            success_rate = (
                ((saved_count - scraper.stats["errors"]) / max(saved_count, 1)) * 100
                if saved_count > 0 else 0
            )
            
            result = {
                "success": True,
                "session_id": session_id,
                "target_site": target_site,
                "total_records": saved_count,
                "pages_scraped": scraper.stats["pages_scraped"],
                "errors": scraper.stats["errors"],
                "success_rate": success_rate,
                "duration": scraper.stats.get("end_time", 0) - scraper.stats.get("start_time", 0)
            }
            
            scraper_logger.info(f"Scraping session {session_id} completed successfully", **result)
            return result
            
        except Exception as e:
            error_message = str(e)
            scraper_logger.error(f"Scraping session {session_id} failed", error=error_message)
            
            # Hata durumunu veritabanına kaydet
            with db_manager.get_session() as db:
                ScrapingRepository.update_session_status(
                    db, session_id, "failed",
                    pages_scraped=scraper.stats.get("pages_scraped", 0),
                    total_records=scraper.stats.get("total_records", 0),
                    error_log=error_message
                )
            
            return {
                "success": False,
                "error": error_message,
                "session_id": session_id,
                "target_site": target_site
            }
            
        finally:
            await scraper.cleanup()


# Global scraping orchestrator instance
scraping_orchestrator = ScrapingOrchestrator()
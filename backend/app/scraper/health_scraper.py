"""
Almanya sağlık dizinleri web scraping modülü
Bu modül Selenium + BeautifulSoup kullanarak Alman sağlık dizinlerinden veri çeker
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config.settings import settings

# Logging setup
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
logger = logging.getLogger(__name__)

class HealthProviderData:
    """Sağlık sağlayıcısı veri modeli"""
    
    def __init__(self, **kwargs):
        self.name: str = kwargs.get('name', '')
        self.address: str = kwargs.get('address', '')
        self.phone: str = kwargs.get('phone', '')
        self.email: str = kwargs.get('email', '')
        self.website: str = kwargs.get('website', '')
        self.specialty: str = kwargs.get('specialty', '')
        self.city: str = kwargs.get('city', '')
        self.postal_code: str = kwargs.get('postal_code', '')
        self.opening_hours: str = kwargs.get('opening_hours', '')
        self.rating: str = kwargs.get('rating', '')
        self.source_url: str = kwargs.get('source_url', '')
        self.scraped_at: float = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Veriyi dictionary'e çevirir"""
        return {
            'name': self.name,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'website': self.website,
            'specialty': self.specialty,
            'city': self.city,
            'postal_code': self.postal_code,
            'opening_hours': self.opening_hours,
            'rating': self.rating,
            'source_url': self.source_url,
            'scraped_at': self.scraped_at
        }

class HealthDirectoryScraper:
    """Ana sağlık dizini scraper sınıfı"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.driver: Optional[webdriver.Chrome] = None
        self.scraped_data: List[HealthProviderData] = []
    
    def _setup_selenium_driver(self) -> webdriver.Chrome:
        """Selenium Chrome driver'ını kurar"""
        chrome_options = Options()
        
        if settings.SELENIUM_HEADLESS:
            chrome_options.add_argument('--headless')
        
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(settings.SELENIUM_IMPLICIT_WAIT)
        
        return driver
    
    async def scrape_gelbeseiten(self, search_term: str = "arzt", location: str = "berlin") -> List[HealthProviderData]:
        """
        Gelbe Seiten'den sağlık sağlayıcıları bilgilerini çeker
        
        Args:
            search_term: Arama terimi (varsayılan: "arzt")
            location: Konum (varsayılan: "berlin")
            
        Returns:
            List[HealthProviderData]: Çekilen veriler
        """
        logger.info(f"Gelbe Seiten'den scraping başlatılıyor: {search_term} in {location}")
        
        try:
            if not self.driver:
                self.driver = self._setup_selenium_driver()
            
            # Gelbe Seiten arama URL'si oluştur
            base_url = "https://www.gelbeseiten.de"
            search_url = f"{base_url}/Suche/{search_term}/{location}"
            
            self.driver.get(search_url)
            
            # Cookie kabul et (varsa)
            try:
                cookie_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CLASS_NAME, "gdpr-accept-button"))
                )
                cookie_button.click()
            except TimeoutException:
                logger.info("Cookie popup bulunamadı veya zaten kabul edilmiş")
            
            # Sonuçları bekle
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "mod-Treffer"))
            )
            
            results = []
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Sonuçları parse et
            for result_div in soup.find_all('div', class_='mod-Treffer'):
                try:
                    data = self._parse_gelbeseiten_result(result_div, base_url)
                    if data:
                        results.append(data)
                except Exception as e:
                    logger.error(f"Gelbe Seiten sonuç parse hatası: {e}")
                    continue
            
            logger.info(f"Gelbe Seiten'den {len(results)} sonuç çekildi")
            return results
            
        except Exception as e:
            logger.error(f"Gelbe Seiten scraping hatası: {e}")
            return []
    
    def _parse_gelbeseiten_result(self, result_div, base_url: str) -> Optional[HealthProviderData]:
        """Gelbe Seiten sonucunu parse eder"""
        try:
            # İş adı
            name_elem = result_div.find('h2', class_='highlight-title')
            name = name_elem.get_text(strip=True) if name_elem else ''
            
            # Adres
            address_elem = result_div.find('div', class_='address')
            address = address_elem.get_text(strip=True) if address_elem else ''
            
            # Telefon
            phone_elem = result_div.find('span', class_='phone')
            phone = phone_elem.get_text(strip=True) if phone_elem else ''
            
            # Website
            website_elem = result_div.find('a', class_='website-link')
            website = website_elem.get('href', '') if website_elem else ''
            
            # Uzmanlaşma alanı
            specialty_elem = result_div.find('div', class_='category')
            specialty = specialty_elem.get_text(strip=True) if specialty_elem else 'Arzt'
            
            # Rating
            rating_elem = result_div.find('div', class_='rating')
            rating = rating_elem.get_text(strip=True) if rating_elem else ''
            
            if name:  # En azından isim varsa veriyi kaydet
                return HealthProviderData(
                    name=name,
                    address=address,
                    phone=phone,
                    website=website,
                    specialty=specialty,
                    rating=rating,
                    source_url="gelbeseiten.de"
                )
            
        except Exception as e:
            logger.error(f"Gelbe Seiten sonuç parse hatası: {e}")
        
        return None
    
    async def scrape_das_oertliche(self, search_term: str = "arzt", location: str = "berlin") -> List[HealthProviderData]:
        """
        Das Örtliche'den sağlık sağlayıcıları bilgilerini çeker
        
        Args:
            search_term: Arama terimi
            location: Konum
            
        Returns:
            List[HealthProviderData]: Çekilen veriler
        """
        logger.info(f"Das Örtliche'den scraping başlatılıyor: {search_term} in {location}")
        
        try:
            if not self.driver:
                self.driver = self._setup_selenium_driver()
            
            base_url = "https://www.das-oertliche.de"
            search_url = f"{base_url}/Themen/{search_term}.html"
            
            self.driver.get(search_url)
            
            # Konum gir
            try:
                location_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "ci"))
                )
                location_input.clear()
                location_input.send_keys(location)
                
                # Arama butonuna tıkla
                search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                search_button.click()
                
                # Sonuçları bekle
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "entry"))
                )
                
            except TimeoutException:
                logger.warning("Das Örtliche arama yapılamadı")
                return []
            
            results = []
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Sonuçları parse et
            for result_div in soup.find_all('div', class_='entry'):
                try:
                    data = self._parse_das_oertliche_result(result_div)
                    if data:
                        results.append(data)
                except Exception as e:
                    logger.error(f"Das Örtliche sonuç parse hatası: {e}")
                    continue
            
            logger.info(f"Das Örtliche'den {len(results)} sonuç çekildi")
            return results
            
        except Exception as e:
            logger.error(f"Das Örtliche scraping hatası: {e}")
            return []
    
    def _parse_das_oertliche_result(self, result_div) -> Optional[HealthProviderData]:
        """Das Örtliche sonucunu parse eder"""
        try:
            # İş adı
            name_elem = result_div.find('h2')
            name = name_elem.get_text(strip=True) if name_elem else ''
            
            # Adres
            address_elem = result_div.find('div', class_='address')
            address = address_elem.get_text(strip=True) if address_elem else ''
            
            # Telefon
            phone_elem = result_div.find('span', class_='phone-number')
            phone = phone_elem.get_text(strip=True) if phone_elem else ''
            
            if name:
                return HealthProviderData(
                    name=name,
                    address=address,
                    phone=phone,
                    specialty='Arzt',
                    source_url="das-oertliche.de"
                )
            
        except Exception as e:
            logger.error(f"Das Örtliche sonuç parse hatası: {e}")
        
        return None
    
    async def scrape_multiple_sources(
        self, 
        search_term: str = "arzt", 
        location: str = "berlin",
        sources: List[str] = None
    ) -> List[HealthProviderData]:
        """
        Birden fazla kaynaktan veri çeker
        
        Args:
            search_term: Arama terimi
            location: Konum
            sources: Kullanılacak kaynaklar listesi
            
        Returns:
            List[HealthProviderData]: Tüm kaynaklardan çekilen veriler
        """
        if sources is None:
            sources = ["gelbeseiten", "das_oertliche"]
        
        all_results = []
        
        for source in sources:
            try:
                if source == "gelbeseiten":
                    results = await self.scrape_gelbeseiten(search_term, location)
                    all_results.extend(results)
                elif source == "das_oertliche":
                    results = await self.scrape_das_oertliche(search_term, location)
                    all_results.extend(results)
                
                # Rate limiting için kısa bekleme
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"{source} scraping hatası: {e}")
                continue
        
        # Tekrar eden verileri temizle (isim ve adres bazında)
        unique_results = self._remove_duplicates(all_results)
        
        logger.info(f"Toplam {len(unique_results)} benzersiz sonuç çekildi")
        return unique_results
    
    def _remove_duplicates(self, results: List[HealthProviderData]) -> List[HealthProviderData]:
        """Tekrar eden verileri temizler"""
        seen = set()
        unique_results = []
        
        for result in results:
            # İsim ve adres kombinasyonunu key olarak kullan
            key = (result.name.lower().strip(), result.address.lower().strip())
            
            if key not in seen and result.name:
                seen.add(key)
                unique_results.append(result)
        
        return unique_results
    
    def close(self):
        """Selenium driver'ını kapatır"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Selenium driver kapatıldı")

# Global scraper instance
health_scraper = HealthDirectoryScraper()
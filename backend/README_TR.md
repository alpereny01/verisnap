# VeriSnap - Profesyonel Web Scraping API'si

VeriSnap, Almanya sağlık dizinlerinden (Gelbe Seiten, Das Örtliche) profesyonel veri toplama uygulamasıdır.

## Kurulum

### 1. Gerekli Bağımlılıkları Yükleyin

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment Ayarları

`.env.example` dosyasını `.env` olarak kopyalayın ve ayarlarınızı yapılandırın:

```bash
cp .env.example .env
```

Önemli ayarlar:
- `API_KEY`: Güvenli bir API anahtarı belirleyin
- `SECRET_KEY`: JWT tokenları için güvenli bir anahtar
- `SELENIUM_HEADLESS`: Selenium'u görünür/görünmez modda çalıştırın

### 3. Uygulamayı Başlatın

```bash
cd backend/app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Kullanımı

### Authentication

Tüm endpoint'ler API key gerektir. Authorization header'ında Bearer token olarak gönderin:

```bash
Authorization: Bearer your-api-key-here
```

### Ana Endpoint'ler

#### 1. Sistem Bilgisi
```bash
GET /
GET /health
GET /api/info
```

#### 2. Sağlık Sağlayıcıları Scraping

**Tüm Kaynaklardan Veri Çekme:**
```bash
POST /scrape/health-providers
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "search_term": "zahnarzt",
  "location": "münchen",
  "sources": ["gelbeseiten", "das_oertliche"]
}
```

**Sadece Gelbe Seiten:**
```bash
POST /scrape/gelbeseiten
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "search_term": "kardiologe",
  "location": "hamburg"
}
```

**Sadece Das Örtliche:**
```bash
POST /scrape/das-oertliche
Content-Type: application/json
Authorization: Bearer your-api-key

{
  "search_term": "frauenarzt", 
  "location": "köln"
}
```

### Desteklenen Arama Terimleri

- `arzt` - Genel doktor
- `zahnarzt` - Diş hekimi
- `frauenarzt` - Kadın doğum uzmanı
- `kardiologe` - Kardiyolog
- `dermatologe` - Dermatolog
- `orthopäde` - Ortopedist
- `neurologie` - Nöroloji
- `psychiater` - Psikiyatrist

### Desteklenen Şehirler

Berlin, München, Hamburg, Köln, Frankfurt, Stuttgart, Düsseldorf, Dortmund, Essen, Leipzig ve diğer Alman şehirleri.

## Güvenlik Özellikleri

### Rate Limiting
- Varsayılan: Dakikada 100 istek
- IP bazında kontrol
- Aşım durumunda HTTP 429 döner

### API Key Authentication  
- Bearer token tabanlı kimlik doğrulama
- Permission tabanlı erişim kontrolü
- Geçersiz key durumunda HTTP 401 döner

### CORS
- Yapılandırılabilir origin kontrolü
- Varsayılan: localhost:3000

## Çıktı Formatı

```json
{
  "success": true,
  "message": "5 adet sağlık sağlayıcısı verisi çekildi",
  "data": {
    "search_term": "zahnarzt",
    "location": "münchen", 
    "sources_used": ["gelbeseiten"],
    "total_results": 5,
    "results": [
      {
        "name": "Dr. Max Mustermann",
        "address": "Musterstraße 123, 80333 München",
        "phone": "+49 89 123456",
        "email": "info@praxis-mustermann.de",
        "website": "https://www.praxis-mustermann.de",
        "specialty": "Zahnarzt",
        "city": "München",
        "postal_code": "80333",
        "opening_hours": "Mo-Fr: 08:00-18:00",
        "rating": "4.5/5",
        "source_url": "gelbeseiten.de",
        "scraped_at": 1640995200.0
      }
    ]
  },
  "timestamp": 1640995200.0
}
```

## Hata Kodları

- `400` - Geçersiz istek parametreleri
- `401` - Geçersiz API key
- `403` - Yetersiz izin
- `429` - Rate limit aşıldı
- `500` - Sunucu hatası

## Loglama

- Tüm istekler loglanır
- Hata detayları kaydedilir
- Log seviyesi: INFO (varsayılan)
- Log dosyası: `verisnap.log`

## Debug Modu

Development ortamında `DEBUG=True` ayarlandığında:
- Detaylı hata mesajları
- Test endpoint'leri (`/debug/test-scraper`)
- Verbose loglama

## Teknik Detaylar

### Kullanılan Teknolojiler
- **FastAPI**: Modern, hızlı web framework
- **Selenium**: Web browser otomasyonu
- **BeautifulSoup**: HTML parsing
- **SlowAPI**: Rate limiting
- **SQLAlchemy**: Database ORM (opsiyonel)

### Scraping Stratejisi
1. Selenium ile sayfayı yükle
2. Cookie popup'larını otomatik kabul et
3. Arama formunu doldur ve gönder
4. Sonuçları BeautifulSoup ile parse et
5. Veriyi normalize et ve tekrarlananları kaldır

### Performans
- Concurrent scraping: 3 paralel işlem (varsayılan)
- Request timeout: 30 saniye
- Implicit wait: 10 saniye
- Headless mode: Etkin (varsayılan)

## Örnek Kullanım

```python
import requests

# API bilgilerini al
response = requests.get(
    'http://localhost:8000/api/info',
    headers={'Authorization': 'Bearer your-api-key'}
)

# Scraping yap
response = requests.post(
    'http://localhost:8000/scrape/health-providers',
    headers={'Authorization': 'Bearer your-api-key'},
    json={
        'search_term': 'zahnarzt',
        'location': 'berlin',
        'sources': ['gelbeseiten']
    }
)

data = response.json()
print(f"Toplam {data['data']['total_results']} sonuç bulundu")
```

## Sorun Giderme

### Selenium Hatası
ChromeDriver yüklü olduğundan emin olun:
```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# Mac
brew install chromedriver

# Windows
# ChromeDriver'ı indirip PATH'e ekleyin
```

### Network Timeout
İnternet bağlantınızı kontrol edin ve `REQUEST_TIMEOUT` değerini artırın.

### Rate Limiting
İstek sıklığınızı azaltın veya `RATE_LIMIT_REQUESTS` değerini artırın.

## Lisans

Bu proje MIT lisansı altında dağıtılmaktadır.
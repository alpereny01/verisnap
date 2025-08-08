# VeriSnap

**Almanya Sağlık Hizmeti Sağlayıcı Dizinleri Web Scraping Aracı**

VeriSnap, Almanya'daki sağlık hizmeti sağlayıcı dizinlerinden (Jameda, Doctolib, vb.) veri toplayan profesyonel bir web scraping aracıdır. Modern güvenlik özellikleri, proxy desteği ve e-posta bildirimleri ile production-ready bir çözüm sunar.

## 🌟 Özellikler

### 🔍 Web Scraping
- **Desteklenen Siteler**: Jameda.de, Doctolib.de, Arztauskunft.de, Deutsche-aerzte.info
- **Selenium & BeautifulSoup**: Güçlü scraping engine'i
- **Error Handling**: Otomatik retry mechanism ve hata yönetimi
- **Data Validation**: Güvenilirlik skorları ile veri kalite kontrolü

### 🔒 Güvenlik
- **JWT Authentication**: Token tabanlı kimlik doğrulama
- **API Key Support**: Ek güvenlik katmanı
- **Rate Limiting**: API endpoint koruma
- **Input Validation**: Güvenli veri işleme
- **Secure Headers**: Production-ready güvenlik

### 🌐 Proxy Desteği
- **Multi-Proxy Rotation**: Çoklu proxy döngüsü
- **Health Check**: Otomatik proxy sağlık kontrolü
- **Automatic Failover**: Başarısız proxy'leri otomatik değiştirme
- **Performance Monitoring**: Proxy performans takibi

### 📧 E-posta Sistemi
- **SMTP Integration**: Çoklu SMTP provider desteği
- **Template System**: Özelleştirilebilir e-posta şablonları
- **Notifications**: Scraping işlem bildirimleri
- **HTML/Text Support**: Çoklu format desteği

### 🗄️ Veritabanı
- **SQLite/PostgreSQL**: Esnek veritabanı desteği
- **ORM Integration**: SQLAlchemy ile modern veri yönetimi
- **Migration System**: Otomatik veritabanı güncellemeleri
- **Data Models**: Yapılandırılmış veri saklama

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Repository'yi klonlayın
git clone https://github.com/alpereny01/verisnap.git
cd verisnap/backend

# Otomatik kurulum scripti
./scripts/setup.sh

# Veya manuel kurulum:
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
pip install -r requirements.txt
playwright install chromium
```

### 2. Konfigürasyon

```bash
# Environment dosyasını kopyalayın
cp ../.env.example .env

# .env dosyasını düzenleyin
nano .env
```

**Önemli Ayarlar:**
```env
# Güvenlik
SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
API_KEY=your-api-key-change-this-in-production

# E-posta (Gmail örneği)
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Proxy (opsiyonel)
USE_PROXY=True
```

### 3. Veritabanı Kurulumu

```bash
# Migration çalıştır
python scripts/migrate.py
```

### 4. Uygulamayı Başlatma

```bash
# Development modunda
python -m app.main

# Veya uvicorn ile
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. API Dokümantasyonu

Uygulama çalıştıktan sonra:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📖 Kullanım

### 1. Authentication

```bash
# Login
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"

# Response: {"access_token": "...", "token_type": "bearer"}
```

### 2. Scraping İşlemi

```bash
# Scraping başlat
curl -X POST "http://localhost:8000/api/v1/scraping/start" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_site": "jameda.de",
    "specialty": "hausarzt",
    "city": "berlin",
    "max_pages": 10,
    "notify_email": "your-email@example.com"
  }'
```

### 3. İşlem Takibi

```bash
# Session durumu
curl -X GET "http://localhost:8000/api/v1/scraping/sessions/SESSION_ID" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Toplanan veri
curl -X GET "http://localhost:8000/api/v1/scraping/sessions/SESSION_ID/data" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🏗️ Proje Yapısı

```
backend/
├── app/
│   ├── main.py                 # Ana uygulama
│   ├── api/                    # API endpoints
│   │   ├── routes.py           # Route tanımları
│   │   └── schemas.py          # Pydantic modeller
│   ├── config/                 # Konfigürasyon
│   │   ├── settings.py         # Uygulama ayarları
│   │   └── logging.py          # Log konfigürasyonu
│   ├── database/               # Veritabanı
│   │   ├── models.py           # SQLAlchemy modeller
│   │   └── operations.py       # CRUD işlemleri
│   ├── security/               # Güvenlik
│   │   ├── auth.py             # Authentication
│   │   └── rate_limiting.py    # Rate limiting
│   ├── proxy/                  # Proxy yönetimi
│   │   └── manager.py          # Proxy operations
│   ├── email/                  # E-posta
│   │   └── manager.py          # E-posta işlemleri
│   └── scraper/               # Web scraping
│       └── orchestrator.py    # Scraping koordinatörü
├── scripts/                   # Yardımcı scriptler
│   ├── migrate.py            # Database migration
│   └── setup.sh              # Kurulum scripti
└── requirements.txt          # Dependencies
```

## 🔧 Konfigürasyon

### Environment Variables

| Değişken | Açıklama | Default |
|----------|----------|---------|
| `DEBUG` | Debug modu | `False` |
| `SECRET_KEY` | JWT secret key | - |
| `DATABASE_URL` | Veritabanı URL | `sqlite:///./verisnap.db` |
| `USE_PROXY` | Proxy kullanım | `False` |
| `MAX_CONCURRENT_SCRAPES` | Eşzamanlı scraping | `3` |
| `RATE_LIMIT_REQUESTS` | Rate limit | `100` |

### Desteklenen Siteler

- **jameda.de**: Almanya'nın en büyük doktor arama platformu
- **doctolib.de**: Online randevu ve doktor arama
- **arztauskunft.de**: Resmi doktor bilgi sistemi
- **deutsche-aerzte.info**: Doktor dizini

## 🛡️ Güvenlik

### Rate Limiting
- **Genel API**: 100 request/saat
- **Login**: 10 deneme/5 dakika
- **Scraping**: 50 işlem/saat
- **E-posta**: 20 e-posta/saat

### Authentication
- JWT token tabanlı sistem
- Scope-based yetkilendirme
- API key desteği

### Default Kullanıcılar
- **admin/admin123**: Tam yetki
- **scraper/scraper123**: Scraping yetkisi

## 📊 Monitoring

### System Health
```bash
curl -X GET "http://localhost:8000/api/v1/system/health"
```

### Proxy Stats
```bash
curl -X GET "http://localhost:8000/api/v1/proxy/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Rate Limit Info
```bash
curl -X GET "http://localhost:8000/api/v1/rate-limit/info" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🚀 Production Deployment

### 1. Environment Setup
```env
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=WARNING
DATABASE_URL=postgresql://user:pass@localhost/verisnap
```

### 2. Docker (Opsiyonel)
```bash
# Dockerfile oluşturun ve build edin
docker build -t verisnap .
docker run -p 8000:8000 --env-file .env verisnap
```

### 3. Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Commit yapın (`git commit -m 'Add amazing feature'`)
4. Push edin (`git push origin feature/amazing-feature`)
5. Pull Request açın

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🆘 Destek

- **Issues**: GitHub Issues kullanın
- **Dokümantasyon**: `/docs` endpoint'ini ziyaret edin
- **Email**: support@verisnap.com

## 🔄 Changelog

### v1.0.0 (2024-01-XX)
- ✨ İlk release
- 🔍 Jameda.de ve Doctolib.de desteği
- 🔒 JWT authentication
- 🌐 Proxy rotation sistemi
- 📧 E-posta bildirimleri
- 🗄️ SQLite/PostgreSQL desteği

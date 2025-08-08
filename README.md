# VeriSnap - Professional Web Scraping Application

A professional web scraping tool for collecting business information from German healthcare provider directories (Gelbe Seiten, Das Örtliche).

## 🚀 Features

- **Professional FastAPI Backend** with authentication and rate limiting
- **Selenium + BeautifulSoup** web scraping engine
- **Multi-source scraping** from German health directories
- **API key authentication** with permission-based access control
- **Rate limiting** to prevent abuse
- **Comprehensive logging** and error handling
- **Turkish language support** with detailed comments

## 📁 Project Structure

```
backend/
├── app/
│   ├── config/          # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py  # Environment variables & settings
│   ├── security/        # Authentication & security
│   │   ├── __init__.py
│   │   └── auth.py      # API key auth & rate limiting
│   ├── scraper/         # Web scraping modules
│   │   ├── __init__.py
│   │   └── health_scraper.py  # German health directory scraper
│   ├── api/             # API routes (reserved for future expansion)
│   │   └── __init__.py
│   └── main.py          # FastAPI application
├── requirements.txt     # Python dependencies
├── start.sh            # Quick start script
├── test_api.py         # API testing script
└── README_TR.md        # Turkish documentation
```

## 🛠️ Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file and update:
# - API_KEY: Your secure API key
# - SECRET_KEY: JWT secret key
# - Other settings as needed
```

### 3. Start the Application

```bash
# Option 1: Use the startup script
./start.sh

# Option 2: Manual start
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Test the API

```bash
# Run the test suite
python test_api.py

# Or test manually
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/health
```

## 📖 API Documentation

Once running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **API Info**: http://localhost:8000/api/info

## 🔧 API Usage

### Authentication

All endpoints require API key authentication:

```bash
Authorization: Bearer your-api-key-here
```

### Main Endpoints

```bash
# Multi-source health provider scraping
POST /scrape/health-providers
{
  "search_term": "zahnarzt",
  "location": "münchen", 
  "sources": ["gelbeseiten", "das_oertliche"]
}

# Gelbe Seiten only
POST /scrape/gelbeseiten
{
  "search_term": "kardiologe",
  "location": "hamburg"
}

# Das Örtliche only  
POST /scrape/das-oertliche
{
  "search_term": "frauenarzt",
  "location": "köln"
}
```

### Supported Search Terms

- `arzt` - General practitioner
- `zahnarzt` - Dentist
- `frauenarzt` - Gynecologist
- `kardiologe` - Cardiologist
- `dermatologe` - Dermatologist
- `orthopäde` - Orthopedist
- And more medical specialties

### Supported Cities

Berlin, München, Hamburg, Köln, Frankfurt, Stuttgart, Düsseldorf, and other German cities.

## 🛡️ Security Features

- **API Key Authentication**: Bearer token-based authentication
- **Rate Limiting**: 100 requests/minute per IP (configurable)
- **CORS Protection**: Configurable allowed origins
- **Permission System**: Role-based access control
- **Input Validation**: Comprehensive request validation

## 🔧 Configuration

Key environment variables:

```bash
# Security
API_KEY=your-secure-api-key-here
SECRET_KEY=your-jwt-secret-key

# Rate limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

# Scraping
SELENIUM_HEADLESS=True
MAX_CONCURRENT_SCRAPES=3
REQUEST_TIMEOUT=30

# Database (optional)
DATABASE_URL=sqlite:///./verisnap.db
```

## 📊 Response Format

```json
{
  "success": true,
  "message": "5 health providers scraped successfully",
  "data": {
    "search_term": "zahnarzt",
    "location": "münchen",
    "total_results": 5,
    "results": [
      {
        "name": "Dr. Max Mustermann",
        "address": "Musterstraße 123, 80333 München",
        "phone": "+49 89 123456",
        "email": "info@praxis-mustermann.de",
        "website": "https://www.praxis-mustermann.de",
        "specialty": "Zahnarzt",
        "rating": "4.5/5",
        "source_url": "gelbeseiten.de",
        "scraped_at": 1640995200.0
      }
    ]
  }
}
```

## 🚨 Error Handling

- `400` - Bad request parameters
- `401` - Invalid API key
- `403` - Insufficient permissions
- `429` - Rate limit exceeded
- `500` - Server error

## 🧪 Testing

Run the comprehensive test suite:

```bash
# Test with default settings
python test_api.py

# Test with custom URL and API key
python test_api.py http://localhost:8000 your-api-key
```

## 📝 Logging

- All requests are logged
- Error details are captured
- Configurable log level (INFO by default)
- Log file: `verisnap.log`

## 🔍 Troubleshooting

### ChromeDriver Issues

Install ChromeDriver for Selenium:

```bash
# Ubuntu/Debian
sudo apt-get install chromium-browser chromium-chromedriver

# Mac
brew install chromedriver

# Windows
# Download ChromeDriver and add to PATH
```

### Network Timeouts

- Check internet connection
- Increase `REQUEST_TIMEOUT` value
- Verify target websites are accessible

### Rate Limiting

- Reduce request frequency
- Increase `RATE_LIMIT_REQUESTS` value
- Implement request queuing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if needed
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🌍 Language Support

- **English**: Primary documentation
- **Turkish**: Complete code comments and `README_TR.md`

---

**Note**: This application is designed for educational and research purposes. Please respect the terms of service of the websites being scraped and implement appropriate delays and rate limiting.

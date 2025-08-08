#!/bin/bash

# VeriSnap Kurulum ve Başlatma Scripti

echo "🚀 VeriSnap - Profesyonel Web Scraping API'si"
echo "=============================================="

# Current directory check
if [ ! -f "requirements.txt" ]; then
    echo "❌ Hata: Bu script backend/ dizininde çalıştırılmalıdır"
    echo "Kullanım: cd backend && ./start.sh"
    exit 1
fi

echo "📦 Bağımlılıkları yüklüyor..."
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "❌ Bağımlılık yükleme hatası! Lütfen internet bağlantınızı kontrol edin."
    exit 1
fi

echo "⚙️  Environment ayarları kontrol ediliyor..."

# .env dosyasını kontrol et
if [ ! -f ".env" ]; then
    echo "📝 .env dosyası bulunamadı, .env.example'dan kopyalanıyor..."
    cp .env.example .env
    echo "⚠️  Lütfen .env dosyasını düzenleyip API_KEY ve SECRET_KEY değerlerini güncelleyin!"
fi

echo "🔧 ChromeDriver kontrol ediliyor..."
if ! command -v chromedriver &> /dev/null; then
    echo "⚠️  ChromeDriver bulunamadı. Selenium çalışmayabilir."
    echo "Ubuntu/Debian için: sudo apt-get install chromium-chromedriver"
    echo "Mac için: brew install chromedriver"
fi

echo "🌐 API sunucusu başlatılıyor..."
echo "📖 API dökümantasyonu: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo ""
echo "Durdurmak için: Ctrl+C"
echo ""

cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
#!/bin/bash

# VeriSnap Development Setup Script
# Geliştirme ortamı kurulum scripti

echo "🚀 VeriSnap Development Setup"
echo "=============================="

# Virtual environment oluştur
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Dependencies yükle
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Playwright browser'ları yükle
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Environment dosyasını kopyala
echo "⚙️  Setting up environment..."
if [ ! -f .env ]; then
    cp ../.env.example .env
    echo "✅ Created .env file from .env.example"
    echo "⚠️  Please update .env file with your settings"
else
    echo "ℹ️  .env file already exists"
fi

# Veritabanı migration
echo "🗄️  Running database migrations..."
python scripts/migrate.py

echo ""
echo "✅ Setup completed!"
echo ""
echo "🎯 Next steps:"
echo "1. Update .env file with your configuration"
echo "2. Run: python -m app.main"
echo "3. Visit: http://localhost:8000/docs"
echo ""
echo "📚 Default users:"
echo "- admin/admin123 (full access)"
echo "- scraper/scraper123 (scraping access)"
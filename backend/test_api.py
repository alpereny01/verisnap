"""
VeriSnap API Test Script
Bu script, VeriSnap API'sinin temel işlevlerini test eder
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import sys
from typing import Dict, Any

class VeriSnapAPITester:
    """VeriSnap API test sınıfı"""
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = "your-secure-api-key-here"):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
    
    def make_request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Dict[str, Any]:
        """HTTP request yapar"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Request oluştur
            if data:
                data_bytes = json.dumps(data).encode('utf-8')
                req = urllib.request.Request(url, data=data_bytes, headers=self.headers, method=method)
            else:
                req = urllib.request.Request(url, headers=self.headers, method=method)
            
            # Request gönder
            with urllib.request.urlopen(req, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                return {
                    'success': True,
                    'status_code': response.status,
                    'data': response_data
                }
                
        except urllib.error.HTTPError as e:
            error_data = {}
            try:
                error_data = json.loads(e.read().decode('utf-8'))
            except:
                error_data = {'detail': str(e)}
                
            return {
                'success': False,
                'status_code': e.code,
                'error': error_data
            }
        except Exception as e:
            return {
                'success': False,
                'status_code': 0,
                'error': {'detail': str(e)}
            }
    
    def test_basic_endpoints(self):
        """Temel endpoint'leri test eder"""
        print("🧪 Temel endpoint testleri...")
        
        tests = [
            {'name': 'Ana sayfa', 'endpoint': '/', 'method': 'GET'},
            {'name': 'Sağlık kontrolü', 'endpoint': '/health', 'method': 'GET'},
            {'name': 'API bilgisi', 'endpoint': '/api/info', 'method': 'GET'},
            {'name': 'API istatistikleri', 'endpoint': '/api/stats', 'method': 'GET'}
        ]
        
        results = []
        for test in tests:
            print(f"  📝 Test: {test['name']}")
            result = self.make_request(test['endpoint'], test['method'])
            
            if result['success']:
                print(f"    ✅ Başarılı (Status: {result['status_code']})")
                results.append(True)
            else:
                print(f"    ❌ Hatalı (Status: {result['status_code']}, Error: {result['error']})")
                results.append(False)
        
        return all(results)
    
    def test_scraping_endpoints(self):
        """Scraping endpoint'lerini test eder"""
        print("\n🧪 Scraping endpoint testleri...")
        
        # Basit test verisi
        test_data = {
            'search_term': 'zahnarzt',
            'location': 'münchen',
            'sources': ['gelbeseiten']
        }
        
        tests = [
            {'name': 'Multi-source scraping', 'endpoint': '/scrape/health-providers', 'data': test_data},
            {'name': 'Gelbe Seiten scraping', 'endpoint': '/scrape/gelbeseiten', 'data': test_data},
            {'name': 'Das Örtliche scraping', 'endpoint': '/scrape/das-oertliche', 'data': test_data}
        ]
        
        results = []
        for test in tests:
            print(f"  📝 Test: {test['name']}")
            result = self.make_request(test['endpoint'], 'POST', test['data'])
            
            if result['success']:
                print(f"    ✅ Request başarılı (Status: {result['status_code']})")
                print(f"    📊 Response: {result['data'].get('message', 'No message')}")
                results.append(True)
            else:
                status = result['status_code']
                if status == 401:
                    print(f"    ⚠️  Kimlik doğrulama hatası - API key kontrol edin")
                elif status == 403:
                    print(f"    ⚠️  Yetki hatası - API key permissions kontrol edin")
                elif status == 429:
                    print(f"    ⚠️  Rate limit aşıldı")
                else:
                    print(f"    ❌ Hata (Status: {status}, Error: {result['error']})")
                results.append(False)
        
        return any(results)  # En az bir test başarılı olsun
    
    def test_authentication(self):
        """Authentication testleri"""
        print("\n🧪 Authentication testleri...")
        
        # Geçersiz API key ile test
        old_key = self.api_key
        self.api_key = "invalid-key"
        self.headers['Authorization'] = f'Bearer {self.api_key}'
        
        print("  📝 Test: Geçersiz API key")
        result = self.make_request('/api/info')
        
        if result['status_code'] == 401:
            print("    ✅ Geçersiz API key doğru şekilde reddedildi")
            auth_result = True
        else:
            print("    ❌ Geçersiz API key kabul edildi (güvenlik riski!)")
            auth_result = False
        
        # API key'i geri yükle
        self.api_key = old_key
        self.headers['Authorization'] = f'Bearer {self.api_key}'
        
        return auth_result
    
    def run_all_tests(self):
        """Tüm testleri çalıştırır"""
        print(f"🚀 VeriSnap API Test Suite")
        print(f"📍 Base URL: {self.base_url}")
        print(f"🔑 API Key: {self.api_key[:20]}...")
        print("=" * 50)
        
        # Sunucu erişilebilirlik testi
        print("🧪 Sunucu erişilebilirlik testi...")
        connection_result = self.make_request('/')
        
        if not connection_result['success']:
            print(f"❌ Sunucuya bağlanılamıyor: {connection_result['error']}")
            print("🔧 Kontrol edin:")
            print("  1. Sunucu çalışıyor mu? (uvicorn main:app --reload)")
            print("  2. Port açık mı? (8000)")
            print("  3. URL doğru mu?")
            return False
        
        print("✅ Sunucu erişilebilir")
        
        # Test grupları
        basic_ok = self.test_basic_endpoints()
        auth_ok = self.test_authentication()
        scraping_ok = self.test_scraping_endpoints()
        
        # Sonuçları özetle
        print("\n" + "=" * 50)
        print("📊 Test Sonuçları:")
        print(f"  Basic endpoints: {'✅ Başarılı' if basic_ok else '❌ Başarısız'}")
        print(f"  Authentication: {'✅ Başarılı' if auth_ok else '❌ Başarısız'}")
        print(f"  Scraping: {'✅ Başarılı' if scraping_ok else '❌ Başarısız'}")
        
        if all([basic_ok, auth_ok, scraping_ok]):
            print("\n🎉 Tüm testler başarılı! API hazır kullanıma.")
        else:
            print("\n⚠️  Bazı testler başarısız. Lütfen hataları kontrol edin.")
        
        return all([basic_ok, auth_ok, scraping_ok])

def main():
    """Ana test fonksiyonu"""
    # Komut satırı argümanları
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    api_key = sys.argv[2] if len(sys.argv) > 2 else "your-secure-api-key-here"
    
    # Test çalıştır
    tester = VeriSnapAPITester(base_url, api_key)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
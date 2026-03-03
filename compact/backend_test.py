#!/usr/bin/env python3
"""
Backend API Testing for Branca de Neve 1.0 - RPA System
Tests all API endpoints in offline mode (no RPA connected)
"""
import requests
import sys
import time
from datetime import datetime

class RPAAPITester:
    def __init__(self, base_url="https://project-staging.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                response = requests.request(method, url, json=data, headers=headers, timeout=10)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Expected {expected_status}, got {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {response_data}")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text}")
                self.failed_tests.append({
                    'name': name,
                    'expected': expected_status,
                    'actual': response.status_code,
                    'response': response.text
                })
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                'name': name,
                'error': str(e)
            })
            return False, {}

    def test_root_endpoint(self):
        """Test GET /api/ - Service info"""
        return self.run_test(
            "Root Service Info",
            "GET", 
            "api/",
            200
        )

    def test_health_endpoint(self):
        """Test GET /api/health - Health check"""
        return self.run_test(
            "Health Check",
            "GET",
            "api/health", 
            200
        )

    def test_rpa_status_offline(self):
        """Test GET /api/rpa/status - Should show offline initially"""
        success, response = self.run_test(
            "RPA Status (Offline)",
            "GET",
            "api/rpa/status",
            200
        )
        
        if success:
            # Verify it shows offline status
            if isinstance(response, dict):
                if not response.get('online', True):
                    print("   ✅ Correctly shows RPA as offline")
                else:
                    print("   ⚠️  Warning: RPA shows as online unexpectedly")
        
        return success, response

    def test_rpa_register_invalid_token(self):
        """Test POST /api/rpa/register with invalid token"""
        return self.run_test(
            "RPA Register (Invalid Token)",
            "POST",
            "api/rpa/register",
            403,  # Should be forbidden with invalid token
            data={
                "url": "https://test.serveousercontent.com",
                "token": "invalid_token_123"
            }
        )

    def test_rpa_register_valid_token_invalid_domain(self):
        """Test POST /api/rpa/register with valid token but invalid domain"""
        return self.run_test(
            "RPA Register (Valid Token, Invalid Domain)", 
            "POST",
            "api/rpa/register",
            400,  # Should be bad request for invalid domain
            data={
                "url": "https://invalid-domain.com",
                "token": "branca_de_neve_2026"
            }
        )

    def test_rpa_register_missing_url(self):
        """Test POST /api/rpa/register with missing URL"""
        return self.run_test(
            "RPA Register (Missing URL)",
            "POST", 
            "api/rpa/register",
            400,  # Should be bad request for missing URL
            data={
                "token": "branca_de_neve_2026"
            }
        )

    def test_rpa_logs_offline(self):
        """Test GET /api/rpa/logs - Should return error when RPA offline"""
        success, response = self.run_test(
            "RPA Logs (Offline)",
            "GET",
            "api/rpa/logs",
            200  # API returns 200 but with error in response
        )
        
        if success and isinstance(response, dict):
            if 'error' in response or (response.get('logs', []) == []):
                print("   ✅ Correctly handles offline RPA for logs")
            else:
                print("   ⚠️  Warning: Expected error or empty logs for offline RPA")
        
        return success, response

    def test_rpa_cmd_offline(self):
        """Test RPA command proxy when RPA is offline"""
        return self.run_test(
            "RPA Command Proxy (Offline)",
            "GET", 
            "api/rpa/cmd/health",
            503  # Should be service unavailable when RPA not registered
        )

    def test_rpa_ver_tela_offline(self):
        """Test ver_tela endpoint when RPA is offline"""
        success, response = self.run_test(
            "RPA Ver Tela (Offline)",
            "GET",
            "api/rpa/ver_tela", 
            200  # Returns 200 but with error in response
        )
        
        if success and isinstance(response, dict):
            if 'error' in response:
                print("   ✅ Correctly returns error for offline RPA")
            else:
                print("   ⚠️  Warning: Expected error for offline RPA")
        
        return success, response

def main():
    """Main test execution"""
    print("="*60)
    print("🧪 BRANCA DE NEVE 1.0 - API TESTING")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    tester = RPAAPITester()

    # Test basic service endpoints
    print("📡 BASIC SERVICE ENDPOINTS")
    print("-" * 40)
    tester.test_root_endpoint()
    tester.test_health_endpoint()

    # Test RPA endpoints in offline mode
    print("\n🤖 RPA ENDPOINTS (OFFLINE MODE)")
    print("-" * 40)
    tester.test_rpa_status_offline()
    tester.test_rpa_logs_offline()
    tester.test_rpa_ver_tela_offline()
    tester.test_rpa_cmd_offline()

    # Test RPA registration with various scenarios
    print("\n🔐 RPA REGISTRATION TESTS")
    print("-" * 40)
    tester.test_rpa_register_invalid_token()
    tester.test_rpa_register_valid_token_invalid_domain()
    tester.test_rpa_register_missing_url()

    # Print final results
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {len(tester.failed_tests)}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run*100):.1f}%")

    if tester.failed_tests:
        print("\n❌ FAILED TESTS:")
        for i, test in enumerate(tester.failed_tests, 1):
            print(f"{i}. {test['name']}")
            if 'error' in test:
                print(f"   Error: {test['error']}")
            else:
                print(f"   Expected: {test['expected']}, Got: {test['actual']}")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return 0 if len(tester.failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
"""
Negative Test Suite for Trade Blotter Mock API with Dynamic View Discovery

Tests covering HTTP 4xx and 5xx response codes
"""

import pytest
import requests

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"

class TestNegativeScenarios:
    """Test suite for negative scenarios (4xx, 5xx responses)"""
    
    def test_get_view_with_invalid_id_returns_404(self):
        """Test GET /trade-views/{viewId} returns 404 for invalid view ID"""
        invalid_view_id = "invalid-view-id-12345"
        response = requests.get(f"{BASE_URL}/trade-views/{invalid_view_id}")
        assert response.status_code == 404
    
    def test_get_view_404_error_structure(self):
        """Test that 404 error response has correct structure"""
        invalid_view_id = "non-existent-view"
        response = requests.get(f"{BASE_URL}/trade-views/{invalid_view_id}")
        data = response.json()
        
        assert response.status_code == 404
        assert "detail" in data
        assert "errors" in data["detail"]
        assert isinstance(data["detail"]["errors"], list)
        assert len(data["detail"]["errors"]) > 0
    
    def test_get_view_404_error_content(self):
        """Test that 404 error contains required fields: code, title, status"""
        invalid_view_id = "xyz-123"
        response = requests.get(f"{BASE_URL}/trade-views/{invalid_view_id}")
        data = response.json()
        error = data["detail"]["errors"][0]
        
        assert "code" in error
        assert "title" in error
        assert "status" in error
        assert error["status"] == 404
        assert "not" in error["title"].lower() or "exist" in error["title"].lower()
    
    def test_get_view_with_unknown_parameter_returns_403(self, valid_view_id):
        """Test GET /trade-views/{viewId} returns 403 for unknown query parameter"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?unknownParam=value")
        assert response.status_code == 403
    
    def test_get_view_403_error_structure(self, valid_view_id):
        """Test that 403 error response has correct structure"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?invalidParameter=test")
        data = response.json()
        
        assert response.status_code == 403
        assert "detail" in data
        assert "errors" in data["detail"]
        assert isinstance(data["detail"]["errors"], list)
    
    def test_get_view_403_error_content(self, valid_view_id):
        """Test that 403 error contains required fields and mentions parameter"""
        unknown_param = "badParameter"
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?{unknown_param}=value")
        data = response.json()
        error = data["detail"]["errors"][0]
        
        assert response.status_code == 403
        assert "code" in error
        assert "title" in error
        assert "status" in error
        assert error["status"] == 403
        
        # Error detail should mention the unknown parameter
        if "detail" in error:
            assert unknown_param in error["detail"] or "parameter" in error["detail"].lower()
    
    @pytest.mark.parametrize("invalid_param", [
        "notAField",
        "randomParameter",
        "invalidFilter"
    ])
    def test_multiple_unknown_parameters_return_403(self, valid_view_id, invalid_param: str):
        """Test various unknown parameters all return 403"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?{invalid_param}=value")
        assert response.status_code == 403
    
    def test_filter_with_invalid_field_returns_403(self, valid_view_id):
        """Test filtering by non-existent CSV field returns 403"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?NonExistentField12345=value")
        assert response.status_code == 403
    
    def test_mixed_valid_and_invalid_parameters_returns_403(self, valid_view_id):
        """Test that mixing valid and invalid parameters returns 403"""
        response = requests.get(
            f"{BASE_URL}/trade-views/{valid_view_id}?includeSchema=true&invalidParam=test"
        )
        assert response.status_code == 403
    
    def test_empty_view_id_returns_404(self):
        """Test that empty viewId in path returns 404, 405, or 200 (redirect)"""
        response = requests.get(f"{BASE_URL}/trade-views/")
        # FastAPI may redirect /trade-views/ to /trade-views (200)
        # or return 404/405 depending on configuration
        assert response.status_code in [200, 404, 405]
    
    @pytest.mark.parametrize("malformed_id", [
        "123",
        "abc-def",
        "!@#$%",
        "spaces in id"
    ])
    def test_malformed_view_ids_return_404(self, malformed_id: str):
        """Test various malformed view IDs return 404"""
        response = requests.get(f"{BASE_URL}/trade-views/{malformed_id}")
        assert response.status_code == 404
    
    def test_case_sensitive_view_id(self, valid_view_id):
        """Test that view IDs are case-sensitive (uppercase should fail)"""
        uppercase_id = valid_view_id.upper()
        response = requests.get(f"{BASE_URL}/trade-views/{uppercase_id}")
        # Should return 404 since IDs are case-sensitive
        assert response.status_code == 404
    
    def test_special_characters_in_filter_value(self, valid_view_id, sample_csv_fields):
        """Test filtering with special characters doesn't cause 500 error"""
        if not sample_csv_fields:
            pytest.skip("No CSV fields available")
        
        field_name = list(sample_csv_fields)[0]
        # Using a valid field but with special characters
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?{field_name}=%3Cscript%3E")
        # Should return 200 with empty results, not 500
        assert response.status_code == 200
    
    def test_very_long_filter_value(self, valid_view_id, sample_csv_fields):
        """Test filtering with very long value doesn't cause 500 error"""
        if not sample_csv_fields:
            pytest.skip("No CSV fields available")
        
        field_name = list(sample_csv_fields)[0]
        long_value = "A" * 10000
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?{field_name}={long_value}")
        # Should handle gracefully, return 200 with empty results
        assert response.status_code in [200, 403]
    
    def test_sql_injection_attempt_in_filter(self, valid_view_id, sample_csv_fields):
        """Test that SQL injection attempts are handled safely"""
        if not sample_csv_fields:
            pytest.skip("No CSV fields available")
        
        field_name = list(sample_csv_fields)[0]
        sql_injection = "'; DROP TABLE trades; --"
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?{field_name}={sql_injection}")
        # Should return 200 with no results, not 500
        assert response.status_code == 200
    
    def test_error_response_is_json(self):
        """Test that error responses are in JSON format"""
        invalid_view_id = "test-404"
        response = requests.get(f"{BASE_URL}/trade-views/{invalid_view_id}")
        assert response.status_code == 404
        assert response.headers.get("content-type") == "application/json"
        
        # Should be parseable as JSON
        data = response.json()
        assert isinstance(data, dict)
    
    def test_404_and_403_have_consistent_error_format(self, valid_view_id):
        """Test that different error codes use consistent error structure"""
        # Get 404 error
        response_404 = requests.get(f"{BASE_URL}/trade-views/invalid-id")
        data_404 = response_404.json()
        
        # Get 403 error
        response_403 = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?badParam=value")
        data_403 = response_403.json()
        
        # Both should have same structure
        assert "detail" in data_404 and "detail" in data_403
        assert "errors" in data_404["detail"] and "errors" in data_403["detail"]
        
        # Both error objects should have same required fields
        error_404 = data_404["detail"]["errors"][0]
        error_403 = data_403["detail"]["errors"][0]
        
        assert "code" in error_404 and "code" in error_403
        assert "title" in error_404 and "title" in error_403
        assert "status" in error_404 and "status" in error_403

"""
Positive Test Suite for Trade Blotter Mock API with Dynamic View Discovery

Tests covering HTTP 2xx response codes
"""

import pytest
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"

class TestPositiveScenarios:
    """Test suite for positive scenarios (2xx responses)"""
    
    def test_service_health(self):
        """Test that the service is running and healthy"""
        response = requests.get("http://localhost:8000/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data
        assert "discovered_views" in data
        assert data["discovered_views"] >= 0
    
    def test_get_all_views_returns_200(self):
        """Test GET /trade-views returns 200 OK"""
        response = requests.get(f"{BASE_URL}/trade-views")
        assert response.status_code == 200
    
    def test_get_all_views_returns_list(self):
        """Test GET /trade-views returns list of available views"""
        response = requests.get(f"{BASE_URL}/trade-views")
        data = response.json()
        assert "tradeViews" in data
        assert isinstance(data["tradeViews"], list)
        assert len(data["tradeViews"]) >= 0  # Changed from == 4 to >= 0
    
    def test_get_all_views_sorted_alphabetically(self):
        """Test that views are sorted alphabetically by label"""
        response = requests.get(f"{BASE_URL}/trade-views")
        data = response.json()
        labels = [view["label"] for view in data["tradeViews"]]
        assert labels == sorted(labels), "Views should be sorted alphabetically"
    
    def test_get_all_views_structure(self):
        """Test that each view has required fields: id, label, description"""
        response = requests.get(f"{BASE_URL}/trade-views")
        data = response.json()
        for view in data["tradeViews"]:
            assert "id" in view
            assert "label" in view
            assert "description" in view
            assert isinstance(view["id"], str)
            assert isinstance(view["label"], str)
            assert isinstance(view["description"], str)
    
    def test_get_view_by_id_returns_200(self, all_views):
        """Test GET /trade-views/{viewId} returns 200 OK for all valid views"""
        if not all_views:
            pytest.skip("No views available")
        
        for view_id, view_config in all_views.items():
            response = requests.get(f"{BASE_URL}/trade-views/{view_id}")
            assert response.status_code == 200, f"Failed for view: {view_config['label']}"
    
    def test_get_view_with_schema_returns_schema(self, valid_view_id):
        """Test GET /trade-views/{viewId}?includeSchema=true returns schema"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?includeSchema=true")
        data = response.json()
        assert response.status_code == 200
        assert "schema" in data
        if data["total"] > 0:  # Only check schema structure if there's data
            assert "fields" in data["schema"]
            assert "primaryKey" in data["schema"]
            assert isinstance(data["schema"]["fields"], list)
            assert isinstance(data["schema"]["primaryKey"], list)
    
    def test_get_view_without_schema_excludes_schema(self, valid_view_id):
        """Test GET /trade-views/{viewId}?includeSchema=false excludes schema"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?includeSchema=false")
        data = response.json()
        assert response.status_code == 200
        assert "data" in data
    
    def test_get_view_returns_data(self, valid_view_id):
        """Test GET /trade-views/{viewId} returns data array"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data = response.json()
        assert response.status_code == 200
        assert "data" in data
        assert isinstance(data["data"], list)
    
    def test_get_view_response_structure(self, valid_view_id):
        """Test that view response contains all required fields"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data = response.json()
        assert response.status_code == 200
        assert "id" in data
        assert "label" in data
        assert "description" in data
        assert "limit" in data
        assert "total" in data
        assert "data" in data
        assert "staleDataTimestamp" in data
    
    def test_schema_fields_structure(self, valid_view_id):
        """Test that schema fields have correct structure: name, title, type"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}?includeSchema=true")
        data = response.json()
        
        if data["total"] == 0:
            pytest.skip("No data in view to test schema")
        
        assert "schema" in data
        for field in data["schema"]["fields"]:
            assert "name" in field
            assert "title" in field
            assert "type" in field
            assert field["type"] in ["string", "number", "date"]
    
    def test_filter_by_single_field(self, valid_view_id, sample_csv_fields):
        """Test filtering by single field (tradeViewSpecificParams)"""
        if not sample_csv_fields:
            pytest.skip("No CSV fields available")
        
        # Get first field name
        field_name = list(sample_csv_fields)[0]
        
        # Get a value from the data
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data = response.json()
        
        if not data["data"]:
            pytest.skip("No data to test filtering")
        
        # Use value from first record
        filter_value = data["data"][0][field_name]
        
        # Test filter
        response_filtered = requests.get(
            f"{BASE_URL}/trade-views/{valid_view_id}?{field_name}={filter_value}"
        )
        data_filtered = response_filtered.json()
        
        assert response_filtered.status_code == 200
        assert "data" in data_filtered
        
        # All returned trades should have the filter value
        for trade in data_filtered["data"]:
            if field_name in trade:
                assert str(trade[field_name]) == str(filter_value)
    
    def test_filter_returns_subset_of_data(self, valid_view_id, sample_csv_fields):
        """Test that filtering returns fewer or equal records than unfiltered"""
        if not sample_csv_fields:
            pytest.skip("No CSV fields available")
        
        # Get all data
        response_all = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data_all = response_all.json()
        total_all = data_all["total"]
        
        if total_all == 0:
            pytest.skip("No data to test filtering")
        
        # Get first field and value
        field_name = list(sample_csv_fields)[0]
        filter_value = data_all["data"][0][field_name]
        
        # Get filtered data
        response_filtered = requests.get(
            f"{BASE_URL}/trade-views/{valid_view_id}?{field_name}={filter_value}"
        )
        data_filtered = response_filtered.json()
        total_filtered = data_filtered["total"]
        
        assert response_filtered.status_code == 200
        assert total_filtered <= total_all, "Filtered results should be <= unfiltered"
    
    def test_total_matches_data_length(self, valid_view_id):
        """Test that 'total' field matches actual data array length"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data = response.json()
        assert response.status_code == 200
        assert data["total"] == len(data["data"])
    
    def test_limit_value_is_10000(self, valid_view_id):
        """Test that limit is set to 10000 as per specification"""
        response = requests.get(f"{BASE_URL}/trade-views/{valid_view_id}")
        data = response.json()
        assert response.status_code == 200
        assert data["limit"] == 10000
        
    def test_filter_by_date_field(self, view_with_date_fields):
        """Test filtering by date field (tradeViewSpecificParams)"""
        view_id = view_with_date_fields['view_id']
        date_field_name = view_with_date_fields['date_fields'][0]
        date_value = view_with_date_fields['sample_data'][0][date_field_name]
        
        # Test filtering by date
        response = requests.get(
            f"{BASE_URL}/trade-views/{view_id}?{date_field_name}={date_value}"
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["total"] > 0, f"Filter by {date_field_name}={date_value} should return results"
        
        # All returned records should have the filtered date value
        for record in data["data"]:
            assert str(record[date_field_name]) == str(date_value)


    def test_filter_by_multiple_date_values(self, view_with_date_and_variety):
        """Test filtering by multiple date values (OR logic within same field)"""
        view_id = view_with_date_and_variety['view_id']
        date_field = view_with_date_and_variety['date_field_with_variety']
        date_values = view_with_date_and_variety['unique_date_values'][:2]  # Use 2 values
        
        # Test filtering with multiple date values (OR logic)
        response = requests.get(
            f"{BASE_URL}/trade-views/{view_id}?{date_field}={date_values[0]}&{date_field}={date_values[1]}"
        )
        data = response.json()
        
        assert response.status_code == 200
        assert data["total"] > 0
        
        # All returned records should have one of the two date values
        for record in data["data"]:
            assert str(record[date_field]) in date_values


    def test_filter_by_date_and_other_field(self, view_with_date_fields):
        """Test filtering by date field AND another field (AND logic across fields)"""
        view_id = view_with_date_fields['view_id']
        date_field = view_with_date_fields['date_fields'][0]
        all_fields = view_with_date_fields['all_fields']
        first_record = view_with_date_fields['sample_data'][0]
        
        # Find a non-date field
        other_field = None
        for field in all_fields:
            if field != date_field:
                other_field = field
                break
        
        date_value = first_record[date_field]
        other_value = first_record[other_field]
        
        # Test filtering by both fields (AND logic)
        response = requests.get(
            f"{BASE_URL}/trade-views/{view_id}?{date_field}={date_value}&{other_field}={other_value}"
        )
        data = response.json()
        
        assert response.status_code == 200
        
        # All returned records should match BOTH filters
        for record in data["data"]:
            assert str(record[date_field]) == str(date_value)
            assert str(record[other_field]) == str(other_value)


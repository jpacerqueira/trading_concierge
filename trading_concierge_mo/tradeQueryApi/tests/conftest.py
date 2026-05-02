"""
Pytest configuration and shared fixtures with dynamic view discovery
"""

import pytest
import requests
import sys
from pathlib import Path
from dateutil import parser

# Ensure src/tradeQueryApi is importable when running tests from repo root
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from view_manager import ViewManager

BASE_URL = "http://localhost:8000"

# Initialize ViewManager for tests
view_manager = ViewManager()

def _get_date_fields_from_row(row):
    date_fields = []
    for field_name, field_value in row.items():
        if not isinstance(field_value, (int, float)):
            try:
                parser.parse(field_value, fuzzy=False)
                date_fields.append(field_name)
            except (ValueError, parser.ParserError):
                pass
    return date_fields

@pytest.fixture(scope="session", autouse=True)
def check_service_running():
    """
    Check if the service is running before tests start
    This fixture runs once per test session
    """
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            pytest.exit("Service is not healthy. Start the service with: python main.py")
    except requests.exceptions.ConnectionError:
        pytest.exit("Cannot connect to service. Start the service with: python main.py")
    except requests.exceptions.Timeout:
        pytest.exit("Service connection timeout. Check if service is running on port 8000")
    except Exception as e:
        pytest.exit(f"Unexpected error checking service: {e}")
    
    print("\nOK: Service is running and healthy")

@pytest.fixture
def base_url():
    """Provide base URL for API endpoints"""
    return f"{BASE_URL}/v1/api/trade-blotter"

@pytest.fixture
def valid_view_id():
    """Provide a valid view ID for testing (first discovered view)"""
    view_ids = view_manager.get_all_view_ids()
    if not view_ids:
        pytest.skip("No views available in data/ folder")
    return view_ids[0]

@pytest.fixture
def all_view_ids():
    """Provide all valid view IDs dynamically discovered"""
    return view_manager.get_all_view_ids()

@pytest.fixture
def all_views():
    """Provide all view configurations"""
    return view_manager.discover_views()

@pytest.fixture
def sample_csv_fields(valid_view_id):
    """Provide sample CSV fields from first view"""
    return view_manager.get_csv_fields(valid_view_id)

@pytest.fixture
def view_with_date_fields():
    """
    Find and return a view that has data AND contains date fields in schema
    Raises:
        pytest.skip: If no view with date fields and data is found
    """
    views = view_manager.discover_views()
    
    if not views:
        pytest.skip("No views available in data/ folder")
    
    for view_id, view_config in views.items():
        # Load CSV data
        data = view_manager.load_csv_data(view_config["csv_file"])
        
        if not data:
            continue  # Skip empty views
        
        # Check for date fields
        all_fields = set(data[0].keys())
        date_fields = _get_date_fields_from_row(data[0])
        
        # If we found date fields, return this view
        if date_fields:
            return {
                'view_id': view_id,
                'view_config': view_config,
                'date_fields': date_fields,
                'all_fields': all_fields,
                'sample_data': data
            }
    
    # No view with date fields found
    pytest.skip("No view with date fields and data found in data/ folder")

@pytest.fixture
def view_with_multiple_records():
    """
    Find and return a view that has multiple records (at least 2)   
    Raises:
        pytest.skip: If no view with multiple records is found
    """
    views = view_manager.discover_views()
    
    if not views:
        pytest.skip("No views available in data/ folder")
    
    for view_id, view_config in views.items():
        data = view_manager.load_csv_data(view_config["csv_file"])
        
        if len(data) >= 2:
            return {
                'view_id': view_id,
                'view_config': view_config,
                'data': data,
                'record_count': len(data)
            }
    
    pytest.skip("No view with multiple records found in data/ folder")

@pytest.fixture
def view_with_date_and_variety():
    """
    Find and return a view that has:
    - Data (not empty)
    - Date fields
    - Multiple unique values in at least one date field (for OR filtering tests)
    Raises:
        pytest.skip: If no suitable view is found
    """
    views = view_manager.discover_views()
    
    if not views:
        pytest.skip("No views available in data/ folder")
    
    for view_id, view_config in views.items():
        data = view_manager.load_csv_data(view_config["csv_file"])
        
        if len(data) < 2:
            continue  # Need at least 2 records
        
        # Check for date fields
        all_fields = set(data[0].keys())
        date_fields = _get_date_fields_from_row(data[0])
        
        if not date_fields:
            continue
        
        # Check if any date field has multiple unique values
        for date_field in date_fields:
            unique_values = set()
            for record in data:
                value = record.get(date_field)
                if value:
                    unique_values.add(str(value))
            
            if len(unique_values) >= 2:
                return {
                    'view_id': view_id,
                    'view_config': view_config,
                    'date_fields': date_fields,
                    'date_field_with_variety': date_field,
                    'unique_date_values': list(unique_values)[:3],  # Max 3 for testing
                    'all_fields': all_fields,
                    'sample_data': data
                }
    
    pytest.skip("No view with date fields and value variety found in data/ folder")

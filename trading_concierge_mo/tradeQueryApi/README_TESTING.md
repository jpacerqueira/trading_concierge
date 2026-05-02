# Testing Guide for Trade Blotter Mock API

This guide covers the setup and execution of tests for the Trade Blotter Mock API using pytest framework.

## Table of Contents

1. [Overview](#overview)
2. [Initial Setup](#initial-setup)
3. [Test Structure](#test-structure)
4. [Running Tests](#running-tests)
5. [Test Scenarios](#test-scenarios)
6. [Interpreting Results](#interpreting-results)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The test suite is organized into two main categories:

- **Positive Tests** (`tests/test_positive.py`) - Tests covering HTTP 2xx response codes
- **Negative Tests** (`tests/test_negative.py`) - Tests covering HTTP 4xx and 5xx response codes

The test framework uses **pytest**, a powerful Python testing framework that provides:
- Clear test organization
- Parametrized testing
- Detailed output
- Easy test discovery

---

## Initial Setup

### Step 1: Install Dependencies

Make sure you have all required packages installed:

```bash
pip install -r requirements.txt
```

This will install:
- `fastapi==0.128.0` - Web framework
- `uvicorn==0.40.0` - ASGI server
- `pydantic==2.12.5` - Data validation
- `python-multipart==0.0.22` - Form data parsing
- `requests==2.31.0` - HTTP client for tests
- `pytest==8.0.0` - Testing framework

### Step 2: Start the Service

Before running tests, the service must be running:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The service should be accessible at `http://localhost:8000`

### Step 3: Verify Service is Running

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-04T00:00:00.000Z",
  "version": "1.0.0"
}
```

---

## Test Structure

```
.
├── pytest.ini            # Pytest settings
├── tests/                # Pytest tests and fixtures
│   ├── conftest.py       # Pytest configuration and fixtures
│   ├── test_positive.py  # Positive test scenarios (2xx)
│   └── test_negative.py  # Negative test scenarios (4xx, 5xx)
└── README_TESTING.md     # This file
```

### File Descriptions

**tests/conftest.py**
- Shared pytest fixtures
- Service health check
- Common test data

**pytest.ini**
- Test discovery patterns
- Output formatting
- Test markers

**tests/test_positive.py**
- Tests for successful responses (HTTP 2xx)
- Validates core functionality
- Checks data structure and content

**tests/test_negative.py**
- Tests for error responses (HTTP 4xx, 5xx)
- Validates error handling
- Security and edge cases

---

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Positive Tests Only

```bash
pytest tests/test_positive.py
```

### Run Negative Tests Only

```bash
pytest tests/test_negative.py
```

### Run Specific Test Class

```bash
pytest tests/test_positive.py::TestPositiveScenarios
```

### Run Specific Test Method

```bash
pytest tests/test_positive.py::TestPositiveScenarios::test_get_all_views_returns_200
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Detailed Output

```bash
pytest -vv
```

### Run and Stop on First Failure

```bash
pytest -x
```

### Run and Show Print Statements

```bash
pytest -s
```

### Run Tests Matching Pattern

```bash
pytest -k "filter"
```

This runs all tests with "filter" in the name.

---

## Test Scenarios

### Positive Test Scenarios (tests/test_positive.py)

#### Service Health Tests
- ✅ Service is running and healthy
- ✅ Health endpoint returns correct structure

#### GET /trade-views Tests
- ✅ Returns HTTP 200 OK
- ✅ Returns list of 4 available views
- ✅ Views are sorted alphabetically by label
- ✅ Each view has required fields: id, label, description
- ✅ View structure is correct

#### GET /trade-views/{viewId} Tests
- ✅ Returns HTTP 200 OK for all valid view IDs
- ✅ Returns schema when includeSchema=true
- ✅ Schema contains fields and primaryKey
- ✅ Excludes schema when includeSchema=false
- ✅ Returns data array with trade records
- ✅ Response contains all required fields
- ✅ Field structure is correct (name, title, type)
- ✅ Total matches actual data length
- ✅ Limit is set to 10000

#### Filtering Tests (tradeViewSpecificParams)
- ✅ Filter by single field works correctly
- ✅ Filter by multiple fields (AND logic) works
- ✅ Filtered results are subset of unfiltered
- ✅ All returned records match filter criteria

**Key Tested Parameters:**
- `viewId` - View identifier
- `includeSchema` - Schema inclusion flag
- `tradeViewSpecificParams` - Dynamic field filters

### Negative Test Scenarios (tests/test_negative.py)

#### HTTP 404 Tests (Not Found)
- ✅ Invalid view ID returns 404
- ✅ 404 error has correct structure (detail.errors[])
- ✅ 404 error contains: code, title, status
- ✅ Error message indicates "not found"
- ✅ Malformed view IDs return 404
- ✅ Case-sensitive view ID validation
- ✅ Empty view ID returns 404/405

#### HTTP 403 Tests (Forbidden)
- ✅ Unknown query parameter returns 403
- ✅ 403 error has correct structure
- ✅ 403 error mentions parameter name
- ✅ Multiple unknown parameters return 403
- ✅ Invalid filter field returns 403
- ✅ Mixed valid/invalid parameters return 403

#### Security & Edge Cases
- ✅ Special characters in filter values handled safely
- ✅ Very long filter values don't cause 500
- ✅ SQL injection attempts handled safely
- ✅ Multiple identical parameters handled correctly
- ✅ Error responses are JSON format
- ✅ Error format is consistent across error types

---

## Interpreting Results

### Successful Test Run

```
============================= test session starts ==============================
collected 45 items

tests/test_positive.py::TestPositiveScenarios::test_service_health PASSED      [  2%]
tests/test_positive.py::TestPositiveScenarios::test_get_all_views_returns_200 PASSED [  4%]
...
tests/test_negative.py::TestNegativeScenarios::test_get_view_with_invalid_id_returns_404 PASSED [ 95%]
...

============================== 45 passed in 2.34s ===============================
```

### Failed Test Example

```
FAILED tests/test_positive.py::TestPositiveScenarios::test_get_all_views_returns_200
AssertionError: assert 500 == 200
```

This indicates the test expected HTTP 200 but received HTTP 500.

### Test Summary

At the end of the test run, you'll see:
- Number of tests passed
- Number of tests failed
- Number of tests skipped
- Total execution time

---

## Troubleshooting

### Issue: "Cannot connect to service"

**Solution:**
1. Check if service is running: `curl http://localhost:8000/health`
2. Start the service: `python main.py`
3. Verify port 8000 is not in use by another process

### Issue: "ModuleNotFoundError: No module named 'pytest'"

**Solution:**
```bash
pip install pytest
```

Or reinstall all dependencies:
```bash
pip install -r requirements.txt
```

### Issue: "ModuleNotFoundError: No module named 'requests'"

**Solution:**
```bash
pip install requests
```

### Issue: Tests fail with 500 errors

**Solution:**
1. Check service logs for errors
2. Verify CSV files exist in `data/` folder
3. Ensure CSV files have correct format (semicolon-separated)
4. Restart the service

### Issue: Tests pass but data seems wrong

**Solution:**
1. Verify CSV file content in `data/` folder
2. Check that view IDs in tests match `VIEWS_CONFIG` in `main.py`
3. Ensure CSV files are properly formatted

### Issue: Pytest not discovering tests

**Solution:**
1. Ensure test files start with `test_`
2. Ensure test functions start with `test_`
3. Run from project root directory
4. Check `pytest.ini` configuration

---

## Test Data

Tests use the following default views:

| View ID | Label | CSV File |
|---------|-------|----------|
| 44a30c97-a4c1-407e-8293-ecafd163e299 | Daily Basic | DailyBasic.csv |
| 6d2a8328-0d53-40dd-bfc2-77802672eca8 | Daily Detailed | DailyDetailed.csv |
| 95c14eb5-034f-4b81-90c0-9c44b12d74b1 | Live Basic | LiveBasic.csv |
| 7843c17a-e1d7-4135-831a-90b421b3d469 | Live Detailed | LiveDetailed.csv |

Ensure these CSV files exist in the `data/` folder before running tests.

---

## Adding New Tests

### Adding a Positive Test

Add to `tests/test_positive.py`:

```python
def test_my_new_feature(self):
    """Test description"""
    response = requests.get(f"{BASE_URL}/trade-views")
    assert response.status_code == 200
    # Add more assertions
```

### Adding a Negative Test

Add to `tests/test_negative.py`:

```python
def test_my_error_case(self):
    """Test description"""
    response = requests.get(f"{BASE_URL}/trade-views/bad-id")
    assert response.status_code == 404
    # Add more assertions
```

### Using Parametrized Tests

```python
@pytest.mark.parametrize("view_id,expected_label", [
    ("view-1", "Label 1"),
    ("view-2", "Label 2")
])
def test_parametrized(self, view_id, expected_label):
    response = requests.get(f"{BASE_URL}/trade-views/{view_id}")
    assert response.json()["label"] == expected_label
```

---

## Best Practices

1. **Keep tests independent** - Each test should be able to run alone
2. **Use descriptive names** - Test names should clearly indicate what they test
3. **One assertion per concept** - Tests should verify one thing clearly
4. **Clean up after tests** - If tests modify data, restore it
5. **Use fixtures** - Share common setup via pytest fixtures
6. **Document edge cases** - Add comments for non-obvious test scenarios

---

## Continuous Integration

To run tests in CI/CD pipeline:

```bash
# Start service in background
python main.py &
sleep 5  # Wait for service to start

# Run tests
pytest --junitxml=test-results.xml

# Stop service
pkill -f "python main.py"
```

---

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Requests Documentation](https://requests.readthedocs.io/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)

---

## Summary

**Quick Start:**
1. `pip install -r requirements.txt`
2. `python main.py` (in separate terminal)
3. `pytest` (run all tests)
4. `pytest tests/test_positive.py` (positive tests only)
5. `pytest tests/test_negative.py` (negative tests only)

**Test Coverage:**
- ✅ 25+ positive test cases
- ✅ 20+ negative test cases
- ✅ Schema validation
- ✅ Filtering functionality
- ✅ Error handling
- ✅ Security edge cases


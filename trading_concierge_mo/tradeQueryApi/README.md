# MX Trade Blotter Mock Service

FastAPI mock implementation of MX User Trade Views API based on OpenAPI specification.

## Features

- **GET /v1/api/trade-blotter/trade-views** - List all available trade views
- **GET /v1/api/trade-blotter/trade-views/{viewId}** - Get view schema and data with filtering support
- Positive responses (HTTP 200) and negative responses (303, 403, 404, 500)
- CSV-based data storage for easy maintenance
- Query parameter filtering support with validation
- Schema generation from data
- **Pydantic models** for request/response validation
- **Comprehensive test suite** with pytest

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Service

```bash
python main.py
```

Service will be available at: `http://localhost:8000`

### 3. Run Tests

```bash
pytest
```

See [Testing Guide](README_TESTING.md) for detailed testing instructions.

## Project Structure

```
.
├── main.py                 # FastAPI application with Pydantic models
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── README_TESTING.md       # Testing guide
├── EXAMPLES.md             # Detailed API usage examples
├── .gitignore             # Git ignore rules
├── pytest.ini             # Pytest configuration
├── tests/                 # Pytest tests and fixtures
│   ├── conftest.py        # Shared fixtures
│   ├── test_positive.py   # Positive test scenarios (2xx)
│   └── test_negative.py   # Negative test scenarios (4xx, 5xx)
└── data/                  # CSV data files (semicolon-separated)
    ├── DailyBasic.csv     # Daily Basic view data (10 trades)
    ├── DailyDetailed.csv  # Daily Detailed view data (3 trades)
    ├── LiveBasic.csv      # Live Basic view data (3 trades)
    └── LiveDetailed.csv   # Live Detailed view data (3 trades)
```

## API Documentation

Interactive API documentation (Swagger UI): `http://localhost:8000/docs`

## Available Trade Views

| View ID | Label | Description | CSV File |
|---------|-------|-------------|----------|
| 44a30c97-a4c1-407e-8293-ecafd163e299 | Daily Basic | User friendly description for Daily Basic | DailyBasic.csv |
| 6d2a8328-0d53-40dd-bfc2-77802672eca8 | Daily Detailed | User friendly description for Daily Detailed | DailyDetailed.csv |
| 95c14eb5-034f-4b81-90c0-9c44b12d74b1 | Live Basic | User friendly description for Live Basic | LiveBasic.csv |
| 7843c17a-e1d7-4135-831a-90b421b3d469 | Live Detailed | User friendly description for Live Detailed | LiveDetailed.csv |

## API Examples

### 1. Get all trade views

```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views"
```

### 2. Get specific view with schema

```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?includeSchema=true"
```

### 3. Filter trades

```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=IRS&LiveStatus=LIVE"
```

See [EXAMPLES.md](EXAMPLES.md) for more detailed examples.

## Testing

The project includes comprehensive test coverage using pytest.

### Run All Tests

```bash
pytest
```

### Run Positive Tests (2xx responses)

```bash
pytest tests/test_positive.py
```

### Run Negative Tests (4xx, 5xx responses)

```bash
pytest tests/test_negative.py
```

### Test Coverage

- ✅ 25+ positive test cases
- ✅ 20+ negative test cases
- ✅ Schema validation
- ✅ Filtering functionality
- ✅ Error handling
- ✅ Security edge cases

See [README_TESTING.md](README_TESTING.md) for complete testing guide.

## Data Management

### CSV File Format

- Files are stored in the `data/` folder
- Semicolon (`;`) separated values
- First row contains column headers
- Each CSV file represents one trade view

### Adding a New View

1. Create a CSV file in the `data/` folder (e.g., `MyNewView.csv`)
2. Add view configuration to `VIEWS_CONFIG` in `main.py`:

```python
"new-uuid-here": {
    "id": "new-uuid-here",
    "label": "My New View",
    "description": "Description of my new view",
    "csv_file": "MyNewView.csv"
}
```

### Modifying Trade Data

Simply edit the CSV files in the `data/` folder. The mock service will automatically load the updated data on the next request.

## Query Parameters

### includeSchema (boolean, default: true)

Controls whether schema information is included in the response.

### internalDealPerspective (string, optional)

Filter internal deals by perspective:
- `INITIATOR` - Show initiator perspective
- `BENEFICIARY` - Show beneficiary perspective

### tradeViewSpecificParams (dynamic)

Filter data by specific field values. Multiple values can be passed for each field.

**Note:** Only field names present in the CSV data are accepted. Unknown parameters will return 403 Forbidden.

## Response Codes

| Code | Description | Example |
|------|-------------|---------|
| 200 | Success | Valid request with data |
| 303 | See Other | Pagination redirect (when data > 10000 rows) |
| 403 | Forbidden | Unknown query parameter |
| 404 | Not Found | Invalid view ID |
| 500 | Internal Server Error | Server error |

## Dependencies

- **FastAPI 0.128.0** - Modern, fast web framework for building APIs
- **Uvicorn 0.40.0** - ASGI server implementation
- **Pydantic 2.12.5** - Data validation using Python type annotations
- **python-multipart 0.0.22** - Multipart form data parsing
- **requests 2.31.0** - HTTP client for testing
- **pytest 8.0.0** - Testing framework

## Pydantic Models

The service uses Pydantic models for strong typing and validation:

- `ViewCore` - Core view information (id, label, description)
- `FieldSchema` - Field schema definition
- `ViewSchema` - Schema describing data structure
- `ViewDetailsResponse` - Complete view response with data
  - Uses `schema_` field with alias `"schema"` to avoid BaseModel attribute shadowing
- `TradeViewsResponse` - List of available views
- `ErrorResponse` - Standardized error responses

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload
```

### Checking FastAPI Version

```python
import fastapi
print(fastapi.__version__)
```

Or from command line:
```bash
pip show fastapi
```

## Error Handling

The service implements comprehensive error handling:

- **403 Forbidden** - Unknown query parameters are validated and rejected
- **404 Not Found** - Invalid view IDs return proper error response
- **500 Internal Server Error** - All unexpected exceptions are caught and returned with error details

All error responses follow the standardized error format from the OpenAPI specification.

## Limitations & Future Enhancements

Current implementation provides basic mock functionality. Potential enhancements:

- [ ] Advanced filtering with operators (eq, in, nin, gt, lt, etc.)
- [ ] Pagination/snapshot support
- [ ] POST /trade-views/{viewId}/search endpoint
- [ ] Authentication/authorization
- [ ] Date filtering (TODAY keyword support)
- [ ] columnValues parameter parsing
- [ ] bookedOrAmendedDate filtering

## License

Mock service for development and testing purposes.

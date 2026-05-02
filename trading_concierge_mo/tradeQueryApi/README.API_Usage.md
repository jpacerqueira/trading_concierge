# API Usage Examples

This document provides detailed examples of using the Trade Blotter Mock API.

## Table of Contents

1. [Basic Examples](#basic-examples)
2. [Filtering Examples](#filtering-examples)
3. [Error Handling](#error-handling)
4. [Python Client Examples](#python-client-examples)
5. [cURL Examples](#curl-examples)

---

## Basic Examples

### 1. Get All Available Views

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views"
```

**Response (200 OK):**
```json
{
  "tradeViews": [
    {
      "id": "44a30c97-a4c1-407e-8293-ecafd163e299",
      "label": "Daily Basic",
      "description": "User friendly description for Daily Basic"
    },
    {
      "id": "6d2a8328-0d53-40dd-bfc2-77802672eca8",
      "label": "Daily Detailed",
      "description": "User friendly description for Daily Detailed"
    },
    {
      "id": "95c14eb5-034f-4b81-90c0-9c44b12d74b1",
      "label": "Live Basic",
      "description": "User friendly description for Live Basic"
    },
    {
      "id": "7843c17a-e1d7-4135-831a-90b421b3d469",
      "label": "Live Detailed",
      "description": "User friendly description for Live Detailed"
    }
  ]
}
```

---

### 2. Get Specific View with Schema

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?includeSchema=true
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?includeSchema=true"
```

**Response (200 OK):**
```json
{
  "id": "44a30c97-a4c1-407e-8293-ecafd163e299",
  "label": "Daily Basic",
  "description": "User friendly description for Daily Basic",
  "limit": 10000,
  "total": 10,
  "staleDataTimestamp": "2026-02-03T22:50:00.000Z",
  "schema": {
    "fields": [
      {
        "name": "BrokerFeeCcy",
        "title": "BrokerFeeCcy",
        "type": "string"
      },
      {
        "name": "ContractTypology",
        "type": "string"
      },
      {
        "name": "FaceAmount",
        "type": "number"
      }
    ],
    "primaryKey": ["GlobalID"]
  },
  "data": [...]
}
```

---

### 3. Get View Without Schema

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?includeSchema=false
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?includeSchema=false"
```

**Response (200 OK):**
```json
{
  "id": "44a30c97-a4c1-407e-8293-ecafd163e299",
  "label": "Daily Basic",
  "description": "User friendly description for Daily Basic",
  "limit": 10000,
  "total": 10,
  "staleDataTimestamp": "2026-02-03T22:50:00.000Z",
  "data": [...]
}
```

---

## Filtering Examples

The API supports dynamic filtering using `tradeViewSpecificParams`. Any field from the CSV data can be used as a filter parameter.

### Filter Logic

- **Multiple values for same field**: OR logic
  - `?ContractTypology=Spot&ContractTypology=IRS` → Spot OR IRS

- **Multiple different fields**: AND logic
  - `?ContractTypology=IRS&Counterpart=COMPANY A` → IRS AND COMPANY A

---

### 4. Filter by Single Field

**Filter trades with ContractTypology = "Spot"**

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?ContractTypology=Spot
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=Spot"
```

**Response:**
Only returns trades where `ContractTypology` equals "Spot".

---

### 5. Filter by Multiple Values (OR Logic)

**Filter trades with ContractTypology = "Spot" OR "IRS"**

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?ContractTypology=Spot&ContractTypology=IRS
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=Spot&ContractTypology=IRS"
```

**Response:**
Returns trades where `ContractTypology` is either "Spot" OR "IRS".

---

### 6. Filter by Multiple Fields (AND Logic)

**Filter trades with ContractTypology = "IRS" AND Counterpart = "COMPANY A"**

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?ContractTypology=IRS&Counterpart=COMPANY%20A
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=IRS&Counterpart=COMPANY%20A"
```

**Response:**
Returns trades where `ContractTypology` is "IRS" AND `Counterpart` is "COMPANY A".

---

### 7. Filter by Status

**Filter trades with LiveStatus = "LIVE"**

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?LiveStatus=LIVE
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?LiveStatus=LIVE"
```

**Response:**
Only returns trades with `LiveStatus` equal to "LIVE".

---

### 8. Complex Filtering

**Filter: (Spot OR IRS) AND (COMPANY A OR COMPANY B) AND LIVE**

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/{viewId}?ContractTypology=Spot&ContractTypology=IRS&Counterpart=COMPANY%20A&Counterpart=COMPANY%20B&LiveStatus=LIVE
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=Spot&ContractTypology=IRS&Counterpart=COMPANY%20A&Counterpart=COMPANY%20B&LiveStatus=LIVE"
```

---

## Error Handling

### 9. View Not Found (404)

**Request:**
```bash
GET /v1/api/trade-blotter/trade-views/invalid-view-id
```

**cURL:**
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/invalid-view-id"
```

**Response (404 Not Found):**
```json
{
  "detail": {
    "errors": [
      {
        "code": "MX-ERROR-CATALOG-CODE-1",
        "title": "Target URL or object does not exist.",
        "detail": "View not found",
        "status": 404
      }
    ]
  }
}
```

---

### 10. Unauthorized (401)

**Request:**
```bash
GET /v1/api/trade-blotter/error/401
```

**Response (401 Unauthorized):**
```json
{
  "detail": {
    "errors": [
      {
        "code": "MX-ERROR-CATALOG-CODE-1",
        "title": "Unauthorized",
        "detail": "Authentication is required.",
        "status": 401
      }
    ]
  }
}
```

---

### 11. Forbidden (403)

**Request:**
```bash
GET /v1/api/trade-blotter/error/403
```

**Response (403 Forbidden):**
```json
{
  "detail": {
    "errors": [
      {
        "code": "MX-ERROR-CATALOG-CODE-1",
        "title": "Forbidden",
        "detail": "User does not have permission to perform this action.",
        "status": 403
      }
    ]
  }
}
```

---

### 12. Internal Server Error (500)

**Request:**
```bash
GET /v1/api/trade-blotter/error/500
```

**Response (500 Internal Server Error):**
```json
{
  "detail": {
    "errors": [
      {
        "code": "MX-ERROR-CATALOG-CODE-0",
        "title": "Internal Server Error",
        "status": 500
      }
    ]
  }
}
```

---

## Python Client Examples

### Example 1: Get All Views

```python
import requests

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"

response = requests.get(f"{BASE_URL}/trade-views")
views = response.json()["tradeViews"]

for view in views:
    print(f"{view['label']}: {view['id']}")
```

---

### Example 2: Get Filtered Data

```python
import requests

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"
VIEW_ID = "44a30c97-a4c1-407e-8293-ecafd163e299"

# Filter by ContractTypology
params = {
    "ContractTypology": "IRS",
    "includeSchema": True
}

response = requests.get(f"{BASE_URL}/trade-views/{VIEW_ID}", params=params)
data = response.json()

print(f"Total trades: {data['total']}")
print(f"Fields: {[f['name'] for f in data['schema']['fields']]}")

for trade in data['data']:
    print(f"Instrument: {trade.get('Instrument')}, Counterpart: {trade.get('Counterpart')}")
```

---

### Example 3: Filter with Multiple Values

```python
import requests
from urllib.parse import urlencode

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"
VIEW_ID = "44a30c97-a4c1-407e-8293-ecafd163e299"

# Build query string with multiple values
params = [
    ("ContractTypology", "Spot"),
    ("ContractTypology", "IRS"),
    ("LiveStatus", "LIVE")
]

url = f"{BASE_URL}/trade-views/{VIEW_ID}?{urlencode(params)}"
response = requests.get(url)
data = response.json()

print(f"Filtered results: {data['total']} trades")
```

---

### Example 4: Error Handling

```python
import requests

BASE_URL = "http://localhost:8000/v1/api/trade-blotter"

try:
    response = requests.get(f"{BASE_URL}/trade-views/invalid-id")
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    error_data = e.response.json()
    print(f"Error {e.response.status_code}: {error_data['detail']['errors'][0]['title']}")
```

---

## cURL Examples

### Basic Request
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views"
```

### With Pretty Print (using jq)
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views" | jq .
```

### Filter by Single Field
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=Spot"
```

### Filter by Multiple Fields
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299?ContractTypology=IRS&Counterpart=COMPANY%20A"
```

### With Headers
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json"
```

### Save Response to File
```bash
curl -X GET "http://localhost:8000/v1/api/trade-blotter/trade-views/44a30c97-a4c1-407e-8293-ecafd163e299" \
  -o response.json
```

---

## Notes

- All query parameters are case-sensitive
- Field names must match exactly with CSV column headers
- Empty strings in CSV are returned as empty strings in JSON
- Numeric values are automatically converted to numbers
- Date fields (format: DD/MM/YYYY) are detected and typed as "date" in schema

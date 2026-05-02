"""
FastAPI Mock Service for MX Trade Blotter API

Implements /trade-views and /trade-views/{viewId} endpoints

Enhanced version with Pydantic models and Dynamic View Discovery
"""

from fastapi import FastAPI, Query, Path, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, UTC
import uuid
from dateutil import parser
from urllib.parse import parse_qs

from view_manager import ViewManager

# Pydantic Models
class ViewCore(BaseModel):
    """Core View schema"""
    id: str = Field(..., description="Unique identifier of the View")
    label: str = Field(..., description="Label of the View")
    description: str = Field(..., description="User friendly description of the View")

class FieldSchema(BaseModel):
    """Field schema definition"""
    name: str = Field(..., description="Name of the field")
    title: str = Field(..., description="Short description of the field")
    type: str = Field(..., description="Type of the field (string, number, date)")

class ViewSchema(BaseModel):
    """Schema describing the structure of the data"""
    fields: List[FieldSchema]
    primaryKey: List[str]

class ViewDetailsResponse(ViewCore):
    """View details with schema and data"""
    limit: int = Field(..., description="Maximum number of rows supported")
    total: int = Field(..., description="Total number of trades")
    staleDataTimestamp: Optional[str] = Field(None, description="Timestamp if data is stale")
    schema_: Optional[ViewSchema] = Field(None, alias="schema", description="Schema definition")
    data: List[Dict[str, Union[str, int, float, None]]]
    
    class Config:
        populate_by_name = True  # Allows both 'schema' and 'schema_' to work


class TradeViewsResponse(BaseModel):
    """List of available trade views"""
    tradeViews: List[ViewCore]

class ErrorDetail(BaseModel):
    """Error detail structure"""
    code: str
    title: str
    detail: Optional[str] = None
    status: int

class ErrorResponse(BaseModel):
    """Error response structure"""
    errors: List[ErrorDetail]

# FastAPI Application
app = FastAPI(
    title="Trade Blotter Mock",
    description="Mock service for MX User Trade Views API with Dynamic View Discovery",
    version="2.0.0",
    redoc_url=None  # Disable ReDoc
)

# Initialize View Manager
view_manager = ViewManager()

def get_schema_from_data(data: List[Dict[str, Any]]) -> ViewSchema:
    """Generate schema from data fields"""
    if not data:
        return ViewSchema(fields=[], primaryKey=[])
    
    fields = []
    first_row = data[0]
    
    for key, value in first_row.items():
        field_type = "string"
        if isinstance(value, (int, float)):
            field_type = "number"
        elif isinstance(value, str):
            try:
                parser.parse(value, fuzzy=False)
                field_type = "date"
            except (ValueError, parser.ParserError):
                field_type = "string"
            
        fields.append(FieldSchema(
            name=key,
            title=key,
            type=field_type
        ))
    
    # Use first field as primary key (or 'Trade nb' if exists)
    primary_key = ["Trade nb"] if "Trade nb" in first_row else [list(first_row.keys())[0]]
    
    return ViewSchema(fields=fields, primaryKey=primary_key)

def parse_trade_view_params(query_string: str, known_params: set) -> Dict[str, List[str]]:
    """
    Parse tradeViewSpecificParams from query string
    Filters out known parameters and returns dynamic field filters
    """
    params = parse_qs(query_string)
    
    # Remove known parameters
    trade_view_params = {}
    for key, values in params.items():
        if key not in known_params:
            trade_view_params[key] = values
    
    return trade_view_params

def validate_query_params(request: Request, known_params: set, view_id: str) -> None:
    """
    Validate query parameters - raise 403 for unknown parameters
    """
    params = parse_qs(str(request.query_params))
    
    # Get CSV fields for the specific view
    valid_fields = view_manager.get_csv_fields(view_id)
    
    # Check for unknown parameters
    for param_name in params.keys():
        if param_name not in known_params and param_name not in valid_fields:
            raise HTTPException(
                status_code=403,
                detail={
                    "errors": [{
                        "code": "MX-ERROR-CATALOG-CODE-2",
                        "title": "Forbidden",
                        "detail": f"Unknown query parameter: {param_name}",
                        "status": 403
                    }]
                }
            )

@app.get(
    "/v1/api/trade-blotter/trade-views",
    response_model=TradeViewsResponse,
    responses={
        200: {"description": "List of views", "model": TradeViewsResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse}
    },
    summary="Get Views",
    description="Retrieve the list of available trade-views (dynamically discovered from CSV files), ordered alphabetically"
)
async def get_trade_views():
    """
    Get list of available trade views (dynamically discovered from data/ folder)
    Returns: HTTP 200 with list of views, HTTP 500 on internal error
    """
    try:
        # Dynamically discover views
        views_config = view_manager.discover_views()
        
        views_list = [
            ViewCore(
                id=view["id"],
                label=view["label"],
                description=view["description"]
            )
            for view in views_config.values()
        ]
        
        # Sort alphabetically by label
        views_list.sort(key=lambda x: x.label)
        
        return TradeViewsResponse(tradeViews=views_list)
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "errors": [{
                    "code": "MX-ERROR-CATALOG-CODE-0",
                    "title": "Internal Server Error",
                    "detail": str(e),
                    "status": 500
                }]
            }
        )

@app.get(
    "/v1/api/trade-blotter/trade-views/{viewId}",
    response_model=ViewDetailsResponse,
    responses={
        200: {"description": "View details and data", "model": ViewDetailsResponse},
        303: {"description": "Redirect to snapshot for pagination"},
        403: {"description": "Forbidden - unknown parameters", "model": ErrorResponse},
        404: {"description": "View not found", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse}
    },
    summary="Get View Details & Data",
    description="Get view schema and data with optional filtering support (views dynamically discovered)"
)
async def get_trade_view(
    request: Request,
    viewId: str = Path(..., description="Target View ID"),
    includeSchema: bool = Query(True, description="Include schema in response"),
    internalDealPerspective: Optional[str] = Query(
        None,
        description="Internal deal perspective filter",
        pattern="^(INITIATOR|BENEFICIARY)$"
    )
):
    """
    Get view details and data with dynamic filtering support
    Supports tradeViewSpecificParams for filtering on any field in the view
    Returns:
    - HTTP 200 with view data
    - HTTP 303 for pagination redirect
    - HTTP 403 for unknown parameters
    - HTTP 404 if view not found
    - HTTP 500 on internal error
    """
    try:
        print("get_trade_view called", viewId, request.query_params)
        
        # Dynamically discover views
        view_config = view_manager.get_view(viewId)
        
        # Check if view exists
        if not view_config:
            raise HTTPException(
                status_code=404,
                detail={
                    "errors": [{
                        "code": "MX-ERROR-CATALOG-CODE-1",
                        "title": "Target URL or object does not exist.",
                        "detail": f"View not found: {viewId}",
                        "status": 404
                    }]
                }
            )
        
        # Validate query parameters (raises 403 for unknown params)
        known_params = {"includeSchema", "internalDealPerspective"}
        validate_query_params(request, known_params, viewId)
        
        # Load data from CSV
        data = view_manager.load_csv_data(view_config["csv_file"])
        
        # Parse dynamic filter parameters (tradeViewSpecificParams)
        filter_params = parse_trade_view_params(str(request.query_params), known_params)
        
        # Apply filters if any
        if filter_params:
            data = view_manager.apply_filters(data, filter_params)
        
        # Build response
        response_data = {
            "id": view_config["id"],
            "label": view_config["label"],
            "description": view_config["description"],
            "limit": 10000,
            "total": len(data),
            "data": data,
            "staleDataTimestamp": datetime.now(UTC).isoformat()
        }
        
        # Add schema if requested
        if includeSchema and data:
            response_data["schema_"] = get_schema_from_data(data)
        elif includeSchema:
            # Return empty schema if no data
            response_data["schema_"] = ViewSchema(fields=[], primaryKey=[])
        
        # Check if pagination needed (total > limit)
        if len(data) > 10000:
            # Return 303 redirect to snapshot endpoint
            snapshot_id = str(uuid.uuid4())
            location = f"/v1/api/trade-blotter/trade-views/{viewId}/snapshots/{snapshot_id}"
            return JSONResponse(
                status_code=303,
                headers={"Location": location},
                content={}
            )
        
        return ViewDetailsResponse(**response_data)
    
    except HTTPException:
        # Re-raise HTTP exceptions (404, 403)
        raise
    except Exception as e:
        # Catch any other errors and return 500
        raise HTTPException(
            status_code=500,
            detail={
                "errors": [{
                    "code": "MX-ERROR-CATALOG-CODE-0",
                    "title": "Internal Server Error",
                    "detail": str(e),
                    "status": 500
                }]
            }
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "2.0.0",
        "discovered_views": len(view_manager.discover_views())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
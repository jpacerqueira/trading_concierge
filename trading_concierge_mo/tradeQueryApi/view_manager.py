"""
Shared View Manager for Trade Blotter Mock Service

Handles dynamic view discovery, CSV operations, and data management
Used by both the FastAPI service and tests
"""

import csv
import os
import glob
import re
from typing import Dict, Any, List, Optional


class ViewManager:
    """Manages trade views with dynamic discovery from CSV files"""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize ViewManager
        
        Args:
            data_dir: Path to data directory. If None, uses ./data relative to this file
        """
        if data_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.data_dir = os.path.join(base_dir, "data")
        else:
            self.data_dir = data_dir
        
        # Ensure data directory exists
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
    
    def discover_views(self) -> Dict[str, Dict[str, str]]:
        """
        Dynamically discover views from CSV files in data/ folder
        
        Naming convention: {view name}--{uuid}.csv
        Example: All-Default-small242-dffa-447e-b221-8c328d785906.csv
        
        Returns:
            Dictionary mapping view UUID to view configuration
        """
        views_config = {}
        
        # Pattern to match: {view name}--{uuid}.csv
        pattern = re.compile(
            r'^(.+?)--(.+)\.csv$',
            re.IGNORECASE
        )
        
        # Scan all CSV files in data directory
        csv_files = glob.glob(os.path.join(self.data_dir, "*.csv"))
        
        for filepath in csv_files:
            filename = os.path.basename(filepath)
            match = pattern.match(filename)
            
            if match:
                view_name = match.group(1)
                view_uuid = match.group(2).lower()
                
                # Clean up view name: replace underscores/hyphens with spaces
                label = view_name.replace("_", " ").replace("-", " ").strip()
                # Remove extra spaces
                label = " ".join(label.split())
                
                views_config[view_uuid] = {
                    "id": view_uuid,
                    "label": label,
                    "description": f"Trade view: {label}",
                    "csv_file": filename
                }
        
        return views_config
    
    def get_view(self, view_id: str) -> Optional[Dict[str, str]]:
        """
        Get a specific view configuration by ID
        
        Args:
            view_id: UUID of the view
            
        Returns:
            View configuration dict or None if not found
        """
        views = self.discover_views()
        return views.get(view_id)
    
    def get_all_view_ids(self) -> List[str]:
        """
        Get list of all available view IDs
        
        Returns:
            List of view UUIDs
        """
        return list(self.discover_views().keys())
    
    def load_csv_data(self, filename: str) -> List[Dict[str, Any]]:
        """
        Load trade data from CSV file (semicolon-separated)
        
        Args:
            filename: Name of CSV file in data directory
            
        Returns:
            List of trade records as dictionaries
        """
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return []
        
        trades = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                # Convert numeric fields
                processed_row = {}
                for key, value in row.items():
                    # Guard: if value is not a simple string, just keep it as-is
                    if not isinstance(value, str):
                        processed_row[key] = value
                        continue
                    
                    if value == "":
                        processed_row[key] = ""
                    else:
                        try:
                            if "." in value:
                                processed_row[key] = float(value)
                            else:
                                processed_row[key] = int(value)
                        except ValueError:
                            processed_row[key] = value
                trades.append(processed_row)
        return trades
    
    def get_csv_fields(self, view_id: str) -> set:
        """
        Get all field names from a CSV file for a given view
        
        Args:
            view_id: UUID of the view
            
        Returns:
            Set of field names
        """
        view = self.get_view(view_id)
        if not view:
            return set()
        
        data = self.load_csv_data(view["csv_file"])
        if not data:
            return set()
        
        return set(data[0].keys())
    
    def apply_filters(
        self, 
        data: List[Dict[str, Any]], 
        filter_params: Dict[str, List[str]]
    ) -> List[Dict[str, Any]]:
        """
        Apply tradeViewSpecificParams filters to data
        Supports filtering with multiple values (OR logic within same field, AND logic across fields)
        
        Args:
            data: List of trade records
            filter_params: Dictionary of field names to filter values
            
        Returns:
            Filtered list of trade records
        """
        if not filter_params:
            return data
        
        filtered_data = []
        for row in data:
            match = True
            for field_name, filter_values in filter_params.items():
                # Check if field exists in row
                if field_name not in row:
                    match = False
                    break
                
                # Convert row value to string for comparison
                row_value = str(row[field_name])
                
                # Check if row value matches any of the filter values (OR logic)
                if not any(str(v) == row_value for v in filter_values):
                    match = False
                    break
            
            if match:
                filtered_data.append(row)
        
        return filtered_data

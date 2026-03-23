#!/usr/bin/env python3
"""
SafeJSONEncoder - Handle NaN/Infinity in JSON APIs

Copy this file into your Flask/FastAPI project and use safe_jsonify()
instead of jsonify() for responses that may contain float NaN values.
"""

import json
import math
from flask import Response


class SafeJSONEncoder(json.JSONEncoder):
    """
    JSON encoder that handles NaN, Infinity, -Infinity by converting to null.
    
    Python's default json.dumps() outputs NaN/Infinity as bare words which
    are NOT valid JSON (JavaScript's JSON.parse() will reject them).
    
    This encoder recursively sanitizes the data structure, converting any
    non-finite floats to None (which becomes null in JSON).
    """
    
    def encode(self, obj):
        obj = self._sanitize(obj)
        return super().encode(obj)
    
    def _sanitize(self, obj):
        """Recursively replace NaN/Infinity with None"""
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj


def safe_jsonify(data, status_code=200, headers=None):
    """
    Return a Flask Response with JSON data, handling NaN/Infinity values.
    
    Args:
        data: Python dict/list to serialize
        status_code: HTTP status code (default 200)
        headers: Optional dict of HTTP headers
    
    Returns:
        Flask Response object with application/json mimetype
    
    Example:
        @app.route('/api/stocks')
        def get_stocks():
            results = db.query(Stock).all()
            # May contain NaN from calculations
            return safe_jsonify([r.to_dict() for r in results])
    """
    response = Response(
        json.dumps(data, cls=SafeJSONEncoder, ensure_ascii=False),
        mimetype='application/json',
        status=status_code
    )
    if headers:
        response.headers.update(headers)
    return response


def find_non_finite(obj, path=""):
    """
    Debug helper: Find all NaN/Infinity values in a data structure.
    
    Args:
        obj: Data structure to search (dict, list, or primitive)
        path: Current path (for recursive calls)
    
    Prints locations of all non-finite floats found.
    
    Example:
        data = fetch_from_database()
        find_non_finite(data)  # Prints: Found NaN at .results[5].return_10d
    """
    if isinstance(obj, float):
        if math.isnan(obj):
            print(f"Found NaN at {path}")
        elif math.isinf(obj):
            print(f"Found {'Infinity' if obj > 0 else '-Infinity'} at {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_non_finite(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_non_finite(v, f"{path}[{i}]")


# Example usage
if __name__ == "__main__":
    # Test data with problematic values
    test_data = {
        "stocks": [
            {"code": "AAPL", "price": 150.0, "change": float('nan')},
            {"code": "GOOG", "price": float('inf'), "change": -5.5},
        ],
        "metadata": {
            "total": 2,
            "avg_change": float('nan'),
        }
    }
    
    print("Finding non-finite values:")
    find_non_finite(test_data)
    
    print("\nStandard json.dumps (invalid JSON):")
    try:
        bad_json = json.dumps(test_data)
        print(bad_json[:100])
    except Exception as e:
        print(f"Error: {e}")
    
    print("\nSafe JSON (valid):")
    safe_json = json.dumps(test_data, cls=SafeJSONEncoder)
    print(safe_json)
    
    # Verify it's valid JSON
    print("\nParsing back:")
    parsed = json.loads(safe_json)
    print(f"Parsed successfully: {parsed['stocks'][0]['change']}")

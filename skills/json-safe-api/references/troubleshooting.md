# Troubleshooting JSON API Issues

## Problem: "JSON Parse Error" in Frontend

### Symptom
JavaScript console shows:
```
SyntaxError: Unexpected identifier "NaN"
# or
SyntaxError: Unexpected token 'I', "Infinity" is not valid JSON
```

### Diagnosis Steps

#### Step 1: Check Raw Response

In browser DevTools:
1. Open Network tab
2. Find the failing request
3. Click "Response" tab
4. Look for bare words `NaN`, `Infinity`, or `-Infinity`

```json
// ❌ Invalid JSON (what Python produces by default)
{"value": NaN, "score": Infinity}

// ✅ Valid JSON (what JavaScript expects)
{"value": null, "score": null}
```

#### Step 2: Verify with Command Line

```bash
# Test if response is valid JSON
curl -s http://localhost:5000/api/data | python3 -m json.tool

# If this shows an error, your backend is producing invalid JSON
# If this works but browser fails, check encoding/proxy issues
```

#### Step 3: Find the Source of NaN

Add this to your Python code before JSON serialization:

```python
import math

def find_nan(obj, path=""):
    """Debug helper to find NaN/Infinity in data"""
    if isinstance(obj, float):
        if math.isnan(obj):
            print(f"⚠️  NaN found at: {path}")
        elif math.isinf(obj):
            print(f"⚠️  Infinity found at: {path}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            find_nan(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            find_nan(v, f"{path}[{i}]")

# Use it
find_nan(your_data)
```

### Common Sources of NaN/Infinity

| Source | Example | Fix |
|--------|---------|-----|
| Database NULL → float | `float(row['nullable_col'])` | Check for None first |
| Division by zero | `1.0 / 0` | Add zero check |
| 0.0 / 0.0 | `0.0 / 0.0` → NaN | Add validation |
| Pandas/Numpy | `df['col'].mean()` with NaNs | Use `fillna()` or `dropna()` |
| Math domain errors | `math.log(-1)` | Validate inputs |

### Quick Fixes

#### Option 1: Use SafeJSONEncoder (Recommended)

See [safe_json_encoder.py](safe_json_encoder.py) for implementation.

```python
from flask import Response
import json

class SafeJSONEncoder(json.JSONEncoder):
    def encode(self, obj):
        # Sanitize NaN/Infinity to None
        obj = self._sanitize(obj)
        return super().encode(obj)
    
    def _sanitize(self, obj):
        import math
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj

def safe_jsonify(data):
    return Response(
        json.dumps(data, cls=SafeJSONEncoder),
        mimetype='application/json'
    )
```

#### Option 2: Clean Data Before Serialization

```python
def clean_float(value):
    """Convert NaN/Infinity to None"""
    import math
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value

# Apply to your data
cleaned_data = {
    k: clean_float(v) if isinstance(v, float) else v
    for k, v in raw_data.items()
}
```

#### Option 3: Fix at Database Level

```python
# When fetching from database
def safe_float(value):
    if value is None:
        return None
    import math
    f = float(value)
    if math.isnan(f) or math.isinf(f):
        return None
    return f

# Usage
row = {
    'price': safe_float(db_row['price']),
    'change': safe_float(db_row['change']),
}
```

---

## Problem: 404 / "No Data Found" Despite Data Existing

### Symptom
API returns 404 or empty results, but data exists in database.

### Common Causes

#### Wrong Database Path

```python
# ❌ Wrong: Relative path depends on working directory
DB_PATH = "data/dashboard.db"

# ✅ Correct: Absolute path based on file location
from pathlib import Path
DB_PATH = Path(__file__).parent / "data" / "dashboard.db"
```

**Debug:**
```python
# Add to app startup
print(f"Using database: {DB_PATH}")
print(f"Database exists: {DB_PATH.exists()}")
```

#### Date Format Mismatch

```python
# Request comes in as: 2026-03-20
# Database stores: 2026-03-20 00:00:00 (datetime)
# Or: 20260320 (integer)

# Always normalize dates
from datetime import datetime

def normalize_date(date_str):
    """Convert various formats to YYYY-MM-DD"""
    if isinstance(date_str, datetime):
        return date_str.strftime('%Y-%m-%d')
    # Handle other formats...
    return date_str
```

#### Caching Issues

After code changes:
```bash
# Kill all Python processes (stale cached bytecode)
pkill -9 -f "python"

# Or specifically your app
pkill -9 -f "app.py"

# Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +
```

---

## Frontend Debugging Checklist

When buttons don't work or show wrong state:

1. **Check browser console** for JavaScript errors
2. **Check Network tab** for failed requests
3. **Verify React build** is fresh:
   ```bash
   npm run build
   # Then hard refresh browser: Cmd+Shift+R
   ```
4. **Add debug logging** in useEffect/fetch:
   ```javascript
   console.log('API response:', data);
   console.log('Setting state:', processedData);
   ```
5. **Check state updates** in React DevTools:
   - Components tab → find your component
   - Check props and state values

---

## Quick Reference: Valid vs Invalid JSON

| Python Value | Standard json.dumps | SafeJSONEncoder |
|--------------|---------------------|-----------------|
| `float('nan')` | `NaN` ❌ | `null` ✅ |
| `float('inf')` | `Infinity` ❌ | `null` ✅ |
| `float('-inf')` | `-Infinity` ❌ | `null` ✅ |
| `None` | `null` ✅ | `null` ✅ |
| `True` | `true` ✅ | `true` ✅ |
| `"text"` | `"text"` ✅ | `"text"` ✅ |
| `123.45` | `123.45` ✅ | `123.45` ✅ |

Remember: **Only SafeJSONEncoder column produces valid JSON that JavaScript can parse.**

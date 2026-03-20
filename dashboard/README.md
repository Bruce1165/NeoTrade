# Trading Screener Dashboard

A Flask-based web dashboard for running and visualizing trading screeners.

## Features

- **Screener Management**: View and run 3 built-in screeners
  - Coffee Cup Pattern Screener (咖啡杯形态筛选器)
  - Er Ban Hui Tiao Screener (二板回调筛选器)
  - Zhang Ting Bei Liang Yin Screener (涨停倍量阴筛选器)

- **Results Visualization**: 
  - Calendar view of all screening runs
  - Filter results by screener and date
  - Interactive K-line charts using ECharts

- **Database Storage**: SQLite database stores run history and results for fast retrieval

## Directory Structure

```
dashboard/
├── app.py              # Flask backend API
├── models.py           # Database models and operations
├── screeners.py        # Screener registry and execution
├── static/
│   ├── index.html      # Main UI
│   ├── app.js          # Frontend logic
│   └── style.css       # Styling
└── data/
    └── dashboard.db    # SQLite database
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/screeners` | GET | List all screeners |
| `/api/screeners/<name>` | GET | Get screener details |
| `/api/screeners/<name>/run` | POST | Run a screener |
| `/api/runs` | GET | Get historical runs |
| `/api/results` | GET | Get results by screener and date |
| `/api/stock/<code>/chart` | GET | Get stock K-line data |
| `/api/calendar` | GET | Get calendar view data |

## Running the Dashboard

1. Install dependencies:
```bash
pip3 install flask flask-cors
```

2. Start the Flask server:
```bash
cd dashboard
python3 app.py
```

3. Open in browser:
```
http://localhost:5001/static/index.html
```

## Usage

1. **Screeners Page**: View available screeners, view their source code, and run them
2. **Results Page**: Select a screener and date to view matching stocks
3. **Calendar Page**: View all screening runs organized by date
4. **Stock Charts**: Click on any stock card to view its K-line chart

## Database Schema

### screeners
- id, name, display_name, description, file_path, config, created_at, updated_at

### screener_runs
- id, screener_name, run_date, status, started_at, completed_at, error_message, stocks_found

### screener_results
- id, run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_data

### stock_price_cache
- id, stock_code, trade_date, open, high, low, close, volume, amount

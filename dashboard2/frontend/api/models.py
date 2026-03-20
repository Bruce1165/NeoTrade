#!/usr/bin/env python3
"""
Dashboard Database Models
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "dashboard.db"

def init_db():
    """Initialize database tables"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Screener definitions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screeners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            file_path TEXT NOT NULL,
            config TEXT,  -- JSON config
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Screener runs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT NOT NULL,
            run_date DATE NOT NULL,
            status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            stocks_found INTEGER DEFAULT 0,
            UNIQUE(screener_name, run_date)
        )
    ''')
    
    # Screener results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS screener_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            stock_code TEXT NOT NULL,
            stock_name TEXT,
            close_price REAL,
            turnover REAL,
            pct_change REAL,
            extra_data TEXT,  -- JSON for screener-specific data
            FOREIGN KEY (run_id) REFERENCES screener_runs(id) ON DELETE CASCADE
        )
    ''')
    
    # Stock price data cache for charts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_price_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code TEXT NOT NULL,
            trade_date DATE NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            amount REAL,
            UNIQUE(stock_code, trade_date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Screener operations
def get_all_screeners():
    """Get all registered screeners"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_screener(name):
    """Get screener by name"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM screeners WHERE name = ?", (name,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def register_screener(name, display_name, description, file_path, config=None):
    """Register or update a screener"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    config_json = json.dumps(config) if config else None
    
    cursor.execute('''
        INSERT INTO screeners (name, display_name, description, file_path, config)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            display_name = excluded.display_name,
            description = excluded.description,
            file_path = excluded.file_path,
            config = excluded.config,
            updated_at = CURRENT_TIMESTAMP
    ''', (name, display_name, description, file_path, config_json))
    
    conn.commit()
    conn.close()

def delete_screener(name):
    """Delete a screener from database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM screeners WHERE name = ?', (name,))
    conn.commit()
    conn.close()

def update_screener(name, display_name=None, description=None):
    """Update screener metadata"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if display_name is not None:
        updates.append('display_name = ?')
        params.append(display_name)
    
    if description is not None:
        updates.append('description = ?')
        params.append(description)
    
    if updates:
        updates.append('updated_at = CURRENT_TIMESTAMP')
        query = f"UPDATE screeners SET {', '.join(updates)} WHERE name = ?"
        params.append(name)
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()

# Screener run operations
def create_run(screener_name, run_date):
    """Create a new screener run record"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO screener_runs (screener_name, run_date, status, started_at)
            VALUES (?, ?, 'running', CURRENT_TIMESTAMP)
        ''', (screener_name, run_date))
        run_id = cursor.lastrowid
        conn.commit()
        return run_id
    except sqlite3.IntegrityError:
        # Already exists, update status
        cursor.execute('''
            UPDATE screener_runs 
            SET status = 'running', started_at = CURRENT_TIMESTAMP, 
                completed_at = NULL, error_message = NULL, stocks_found = 0
            WHERE screener_name = ? AND run_date = ?
        ''', (screener_name, run_date))
        conn.commit()
        
        cursor.execute('''
            SELECT id FROM screener_runs WHERE screener_name = ? AND run_date = ?
        ''', (screener_name, run_date))
        run_id = cursor.fetchone()[0]
        
        # Clear old results
        cursor.execute('DELETE FROM screener_results WHERE run_id = ?', (run_id,))
        conn.commit()
        return run_id
    finally:
        conn.close()

def complete_run(run_id, stocks_found=0, error_message=None):
    """Mark a run as completed or failed"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    status = 'failed' if error_message else 'completed'
    
    cursor.execute('''
        UPDATE screener_runs 
        SET status = ?, completed_at = CURRENT_TIMESTAMP, 
            stocks_found = ?, error_message = ?
        WHERE id = ?
    ''', (status, stocks_found, error_message, run_id))
    
    conn.commit()
    conn.close()

def get_run(screener_name, run_date):
    """Get run by screener and date"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM screener_runs WHERE screener_name = ? AND run_date = ?
    ''', (screener_name, run_date))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_runs(screener_name=None, limit=50):
    """Get historical runs"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if screener_name:
        cursor.execute('''
            SELECT * FROM screener_runs 
            WHERE screener_name = ?
            ORDER BY run_date DESC
            LIMIT ?
        ''', (screener_name, limit))
    else:
        cursor.execute('''
            SELECT * FROM screener_runs 
            ORDER BY run_date DESC
            LIMIT ?
        ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# Results operations
def save_result(run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_data=None):
    """Save a screener result"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    extra_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else None
    
    cursor.execute('''
        INSERT INTO screener_results 
        (run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (run_id, stock_code, stock_name, close_price, turnover, pct_change, extra_json))
    
    conn.commit()
    conn.close()

def get_results(run_id):
    """Get results for a run"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM screener_results WHERE run_id = ?
    ''', (run_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        d = dict(row)
        if d.get('extra_data'):
            d['extra_data'] = json.loads(d['extra_data'])
        results.append(d)
    return results

def get_results_by_date(screener_name, run_date):
    """Get results by screener and date"""
    run = get_run(screener_name, run_date)
    if not run:
        return None
    return get_results(run['id'])

# Stock price cache operations
def cache_stock_prices(stock_code, df):
    """Cache stock price data"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT OR REPLACE INTO stock_price_cache 
            (stock_code, trade_date, open, high, low, close, volume, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_code,
            row['trade_date'].strftime('%Y-%m-%d') if hasattr(row['trade_date'], 'strftime') else row['trade_date'],
            row['open'], row['high'], row['low'], row['close'],
            row.get('volume', 0), row.get('amount', 0)
        ))
    
    conn.commit()
    conn.close()

def get_cached_prices(stock_code, days=60):
    """Get cached prices for a stock"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM stock_price_cache 
        WHERE stock_code = ?
        ORDER BY trade_date DESC
        LIMIT ?
    ''', (stock_code, days))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

if __name__ == '__main__':
    init_db()

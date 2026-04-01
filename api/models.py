#!/usr/bin/env python3
"""
Dashboard Database Models
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Use the dashboard database
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
    
    # Strategy backtest results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_backtest_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_version TEXT NOT NULL,
            screener_name TEXT NOT NULL,
            params TEXT NOT NULL,  -- JSON encoded parameters
            train_start DATE NOT NULL,
            train_end DATE NOT NULL,
            total_return REAL DEFAULT 0,
            sharpe_ratio REAL DEFAULT 0,
            max_drawdown REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            total_trades INTEGER DEFAULT 0,
            profit_factor REAL DEFAULT 0,
            calmar_ratio REAL DEFAULT 0,
            volatility REAL DEFAULT 0,
            avg_trade_return REAL DEFAULT 0,
            avg_hold_days REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            git_commit TEXT,
            parent_version TEXT  -- Previous generation for lineage
        )
    ''')
    
    # Strategy trades table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS strategy_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            backtest_id INTEGER NOT NULL,
            trade_date DATE NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            action TEXT NOT NULL,  -- BUY, SELL
            price REAL NOT NULL,
            shares INTEGER,
            position_value REAL,
            realized_pnl REAL,
            realized_pnl_pct REAL,
            hold_days INTEGER,
            exit_reason TEXT,  -- target_hit, stop_loss, timeout, end_of_data
            FOREIGN KEY (backtest_id) REFERENCES strategy_backtest_results(id) ON DELETE CASCADE
        )
    ''')
    
    # Experiment configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS experiment_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            screener_name TEXT NOT NULL,
            param_space TEXT NOT NULL,  -- JSON: parameter ranges and constraints
            mutation_strategy TEXT DEFAULT 'gaussian',  -- gaussian, grid, random
            population_size INTEGER DEFAULT 10,
            elite_ratio REAL DEFAULT 0.2,
            mutation_rate REAL DEFAULT 0.3,
            crossover_rate REAL DEFAULT 0.5,
            max_generations INTEGER DEFAULT 100,
            early_stop_patience INTEGER DEFAULT 20,
            target_sharpe REAL DEFAULT 1.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Access log table for visitor statistics
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT,
            user_agent TEXT,
            request_path TEXT,
            access_date DATE NOT NULL,
            access_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Access statistics summary (daily aggregation)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS access_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_date DATE UNIQUE NOT NULL,
            daily_count INTEGER DEFAULT 0,
            unique_ips INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

# Access log operations
def log_access(ip_address, user_agent, request_path):
    """Log a single access"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute('''
        INSERT INTO access_logs (ip_address, user_agent, request_path, access_date)
        VALUES (?, ?, ?, ?)
    ''', (ip_address, user_agent, request_path, today))
    
    conn.commit()
    conn.close()

def update_daily_stats():
    """Update daily access statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Count today's accesses (excluding local IPs)
    cursor.execute('''
        SELECT COUNT(*) as total_count, COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date = ? 
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (today,))
    
    row = cursor.fetchone()
    daily_count = row['total_count']
    unique_ips = row['unique_ips']
    
    # Upsert daily stats
    cursor.execute('''
        INSERT INTO access_stats (stat_date, daily_count, unique_ips)
        VALUES (?, ?, ?)
        ON CONFLICT(stat_date) DO UPDATE SET
            daily_count = excluded.daily_count,
            unique_ips = excluded.unique_ips,
            updated_at = CURRENT_TIMESTAMP
    ''', (today, daily_count, unique_ips))
    
    conn.commit()
    conn.close()

def get_access_stats():
    """Get access statistics for today and this month (count unique IPs only)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    first_day_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    
    # Today's unique IP count (each IP counted once per day)
    cursor.execute('''
        SELECT COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date = ?
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (today,))
    
    today_row = cursor.fetchone()
    
    # This month's unique IP count
    cursor.execute('''
        SELECT COUNT(DISTINCT ip_address) as unique_ips
        FROM access_logs
        WHERE access_date >= ?
        AND ip_address NOT IN ('127.0.0.1', '::1', 'localhost')
        AND ip_address NOT LIKE '192.168.%'
        AND ip_address NOT LIKE '10.%'
        AND ip_address NOT LIKE '172.1[6-9].%'
        AND ip_address NOT LIKE '172.2[0-9].%'
        AND ip_address NOT LIKE '172.3[0-1].%'
    ''', (first_day_of_month,))
    
    month_row = cursor.fetchone()
    conn.close()
    
    return {
        'today': {
            'date': today,
            'unique_visitors': today_row['unique_ips']
        },
        'this_month': {
            'start_date': first_day_of_month,
            'end_date': today,
            'unique_visitors': month_row['unique_ips']
        }
    }

if __name__ == '__main__':
    init_db()

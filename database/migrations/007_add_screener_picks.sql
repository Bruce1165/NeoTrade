-- Migration 007: Add screener pick monitoring table
-- Created: 2026-03-21
-- Purpose: Track screener picks through 10-day monitoring pipeline

-- New table: screener_picks
CREATE TABLE IF NOT EXISTS screener_picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_id TEXT NOT NULL,              -- 'coffee_cup_screener', 'er_ban_hui_tiao_screener', etc.
    stock_code TEXT NOT NULL,               -- Stock code (e.g., '600519')
    entry_date TEXT NOT NULL,               -- Day 0 (pick date, YYYY-MM-DD)
    entry_price REAL,                       -- Day 0 closing price
    expected_exit_date TEXT,                -- Day 10 (10th trading day, YYYY-MM-DD)
    
    status TEXT DEFAULT 'active',           -- 'active', 'graduated', 'failed'
    exit_date TEXT,                         -- When marked graduated/failed (YYYY-MM-DD)
    exit_reason TEXT,                       -- 'completed_10_days', 'failed_day_X_[reason]'
    
    -- Daily tracking (JSON array of day checks)
    -- Format: [{"day": 1, "date": "2026-03-24", "status": "pass", "close_price": 172.0, "note": ""}, ...]
    daily_checks TEXT DEFAULT '[]',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_picks_screener ON screener_picks(screener_id);
CREATE INDEX IF NOT EXISTS idx_picks_screener_date ON screener_picks(screener_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_picks_status ON screener_picks(status);
CREATE INDEX IF NOT EXISTS idx_picks_active ON screener_picks(screener_id, stock_code, status) WHERE status = 'active';

-- Index for finding picks needing review today
CREATE INDEX IF NOT EXISTS idx_picks_exit_date ON screener_picks(expected_exit_date);

-- Trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_screener_picks_timestamp 
AFTER UPDATE ON screener_picks
BEGIN
    UPDATE screener_picks SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

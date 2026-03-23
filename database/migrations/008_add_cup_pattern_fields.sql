-- Migration 008: Add cup pattern fields for Coffee Cup screener
-- Created: 2026-03-21
-- Purpose: Store cup rim and bottom prices for dynamic exit calculations

-- Add new columns to screener_picks
ALTER TABLE screener_picks ADD COLUMN cup_rim_price REAL;
ALTER TABLE screener_picks ADD COLUMN cup_bottom_price REAL;
ALTER TABLE screener_picks ADD COLUMN max_price_seen REAL;  -- Track highest price for early success

-- Index for coffee cup specific queries
CREATE INDEX IF NOT EXISTS idx_picks_cup_pattern ON screener_picks(screener_id, cup_rim_price, cup_bottom_price) 
WHERE screener_id = 'coffee_cup_screener';

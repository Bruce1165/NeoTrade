#!/usr/bin/env python3
"""
NeoTrade Strategy Research Agent
Independent strategy development and optimization
"""

import os
import sys
import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
LOG_DIR = PROJECT_ROOT / "logs" / "strategy_research"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StrategyResearcher:
    """
    Strategy Research and Development Agent
    
    Goals:
    - Win rate > 65%
    - Annual return > 50%
    - Stop loss < 10%
    - No high frequency
    """
    
    def __init__(self):
        self.db_path = PROJECT_ROOT / "data" / "stock_data.db"
        self.conn = None
        
    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        logger.info(f"Connected to database: {self.db_path}")
        return self
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, *args):
        self.close()
    
    def check_data_quality(self) -> Dict:
        """Check data quality and availability"""
        logger.info("=" * 60)
        logger.info("DATA QUALITY CHECK")
        logger.info("=" * 60)
        
        report = {
            'daily_prices': {},
            'stocks': {},
            'indices': {},
            'quality_issues': []
        }
        
        # Check daily_prices
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT 
                MIN(trade_date) as min_date,
                MAX(trade_date) as max_date,
                COUNT(DISTINCT code) as stock_count,
                COUNT(*) as total_records
            FROM daily_prices
        ''')
        row = cursor.fetchone()
        report['daily_prices'] = {
            'date_range': f"{row['min_date']} to {row['max_date']}",
            'stock_count': row['stock_count'],
            'total_records': row['total_records']
        }
        logger.info(f"Daily prices: {row['stock_count']} stocks, {row['min_date']} to {row['max_date']}")
        
        # Check for data gaps
        cursor.execute('''
            SELECT code, COUNT(*) as count
            FROM daily_prices
            GROUP BY code
            ORDER BY count ASC
            LIMIT 10
        ''')
        low_volume = cursor.fetchall()
        if low_volume:
            logger.warning(f"Stocks with lowest record counts: {[dict(r) for r in low_volume]}")
            report['quality_issues'].append(f"Some stocks have low record counts")
        
        # Check stocks table
        cursor.execute('SELECT COUNT(*) FROM stocks')
        report['stocks']['total'] = cursor.fetchone()[0]
        
        # Check sector data availability
        cursor.execute('''
            SELECT 
                COUNT(CASE WHEN industry IS NOT NULL AND industry != '' THEN 1 END) as has_industry,
                COUNT(CASE WHEN sector_lv1 IS NOT NULL AND sector_lv1 != '' THEN 1 END) as has_sector_lv1,
                COUNT(CASE WHEN total_market_cap IS NOT NULL THEN 1 END) as has_market_cap
            FROM stocks
        ''')
        row = cursor.fetchone()
        report['stocks']['industry_coverage'] = f"{row['has_industry']}/{report['stocks']['total']}"
        report['stocks']['sector_coverage'] = f"{row['has_sector_lv1']}/{report['stocks']['total']}"
        report['stocks']['market_cap_coverage'] = f"{row['has_market_cap']}/{report['stocks']['total']}"
        
        logger.info(f"Industry data: {row['has_industry']}/{report['stocks']['total']} stocks")
        logger.info(f"Sector data: {row['has_sector_lv1']}/{report['stocks']['total']} stocks")
        logger.info(f"Market cap data: {row['has_market_cap']}/{report['stocks']['total']} stocks")
        
        # Check for index data (market trend)
        cursor.execute('''
            SELECT DISTINCT code FROM daily_prices 
            WHERE code LIKE 'sh%' OR code LIKE 'sz%' OR code LIKE '000%'
            LIMIT 20
        ''')
        indices = [r[0] for r in cursor.fetchall()]
        report['indices']['available'] = indices[:10]
        logger.info(f"Potential indices: {indices[:10]}")
        
        # Sample stock data
        cursor.execute('''
            SELECT code, open, high, low, close, volume, amount
            FROM daily_prices
            ORDER BY trade_date DESC
            LIMIT 1
        ''')
        sample = cursor.fetchone()
        if sample:
            logger.info(f"Latest sample data: {dict(sample)}")
        
        return report
    
    def design_strategy(self) -> Dict:
        """
        Design the multi-timeframe momentum strategy
        
        Strategy: "Trend Momentum with Sector Confirmation"
        
        Core Logic:
        1. Long-term trend (200-day MA) defines direction
        2. Medium-term momentum (20-day RS) selects stocks
        3. Short-term entry (pullback to 10-day MA)
        4. Sector strength filter (top 30% sectors)
        5. Volatility filter (exclude high volatility)
        """
        logger.info("\n" + "=" * 60)
        logger.info("STRATEGY DESIGN: Trend Momentum with Sector Confirmation")
        logger.info("=" * 60)
        
        strategy = {
            'name': 'neo_trend_momentum_v1',
            'description': 'Multi-timeframe momentum strategy with sector confirmation',
            'timeframes': {
                'long': '200-day MA for trend direction',
                'medium': '50-day MA for intermediate trend',
                'short': '20-day RS + 10-day MA pullback entry'
            },
            'entry_conditions': [
                'Price > 200-day MA (long-term uptrend)',
                'Price > 50-day MA (medium-term uptrend)',
                '20-day RS in top 20% of market',
                'Sector RS in top 30%',
                'Price within 5% of 10-day MA (pullback entry)',
                'ATR(14) < 5% (volatility filter)'
            ],
            'exit_conditions': [
                'Stop loss: -8% from entry',
                'Take profit: +20% from entry',
                'Time stop: 15 days',
                'Price < 50-day MA (trend reversal)'
            ],
            'position_sizing': {
                'max_positions': 5,
                'capital_per_position': 2000,  # 1万 / 5 = 2千 each
                'max_sector_exposure': 40  # Max 40% in one sector
            },
            'parameters': {
                'trend_ma_long': 200,
                'trend_ma_medium': 50,
                'entry_ma_short': 10,
                'rs_lookback': 20,
                'rs_threshold': 80,  # Top 20%
                'sector_rs_threshold': 70,  # Top 30%
                'pullback_pct': 5,
                'volatility_atr_threshold': 5,
                'stop_loss': 8,
                'take_profit': 20,
                'max_hold_days': 15
            }
        }
        
        for key, value in strategy.items():
            if isinstance(value, dict):
                logger.info(f"\n{key.upper()}:")
                for k, v in value.items():
                    logger.info(f"  {k}: {v}")
            elif isinstance(value, list):
                logger.info(f"\n{key.upper()}:")
                for i, item in enumerate(value, 1):
                    logger.info(f"  {i}. {item}")
            else:
                logger.info(f"{key}: {value}")
        
        return strategy
    
    def save_strategy_config(self, strategy: Dict):
        """Save strategy configuration"""
        config_dir = PROJECT_ROOT / "scripts" / "neo_strategy"
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / "strategy_config.json"
        with open(config_file, 'w') as f:
            json.dump(strategy, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\nStrategy config saved to: {config_file}")
    
    def run(self):
        """Main research workflow"""
        logger.info("=" * 60)
        logger.info("NEO STRATEGY RESEARCH AGENT - STARTING")
        logger.info("=" * 60)
        logger.info(f"Goals: Win rate > 65%, Annual return > 50%, Stop loss < 10%")
        logger.info(f"Log file: {log_file}")
        
        try:
            with self.connect():
                # Step 1: Data quality check
                data_report = self.check_data_quality()
                
                # Step 2: Strategy design
                strategy = self.design_strategy()
                
                # Step 3: Save configuration
                self.save_strategy_config(strategy)
                
                logger.info("\n" + "=" * 60)
                logger.info("PHASE 1 COMPLETE: Data checked, strategy designed")
                logger.info("=" * 60)
                logger.info("Next: Implement backtest engine and run baseline")
                
                # Save report
                report_file = LOG_DIR / f"research_report_{datetime.now().strftime('%Y%m%d')}.json"
                full_report = {
                    'timestamp': datetime.now().isoformat(),
                    'data_quality': data_report,
                    'strategy': strategy
                }
                with open(report_file, 'w') as f:
                    json.dump(full_report, f, indent=2, default=str)
                logger.info(f"Full report saved to: {report_file}")
                
        except Exception as e:
            logger.error(f"Research failed: {e}", exc_info=True)
            raise


if __name__ == '__main__':
    researcher = StrategyResearcher()
    researcher.run()

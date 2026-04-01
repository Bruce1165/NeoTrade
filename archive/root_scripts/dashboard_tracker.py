"""
Dashboard Tracker - 将回测结果同步到 Dashboard 数据库
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional
import os


class DashboardTracker:
    """Dashboard 结果追踪器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # 使用项目 Dashboard 数据库
            self.db_path = '/Users/mac/.openclaw/workspace-neo/data/stock_data.db'
        else:
            self.db_path = db_path
        
        self._ensure_tables()
    
    def _ensure_tables(self):
        """确保必要的表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建策略回测结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_backtest_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                config_json TEXT NOT NULL,
                metrics_json TEXT NOT NULL,
                total_return REAL,
                sharpe_ratio REAL,
                max_drawdown REAL,
                win_rate REAL,
                total_trades INTEGER,
                profit_factor REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER,
                trade_date TEXT NOT NULL,
                code TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                shares INTEGER NOT NULL,
                amount REAL NOT NULL,
                commission REAL,
                stamp_duty REAL,
                realized_pnl REAL,
                realized_pnl_pct REAL,
                hold_days INTEGER,
                exit_reason TEXT,
                signal_score REAL,
                FOREIGN KEY (backtest_id) REFERENCES strategy_backtest_results(id)
            )
        ''')
        
        # 创建每日净值表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_daily_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER,
                date TEXT NOT NULL,
                cash REAL,
                positions_value REAL,
                total_value REAL,
                total_return REAL,
                num_positions INTEGER,
                exposure REAL,
                drawdown REAL,
                daily_return REAL,
                FOREIGN KEY (backtest_id) REFERENCES strategy_backtest_results(id)
            )
        ''')
        
        # 创建策略实验表（用于autoresearch追踪）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_date TEXT NOT NULL,
                hypothesis TEXT,
                config_changes TEXT,
                metrics_before TEXT,
                metrics_after TEXT,
                sharpe_before REAL,
                sharpe_after REAL,
                improvement REAL,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_backtest_result(self, result: Dict, strategy_version: str = None) -> int:
        """记录回测结果到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if strategy_version is None:
            strategy_version = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        metrics = result.get('metrics', {})
        config = result.get('config', {})
        
        # 插入主记录
        cursor.execute('''
            INSERT INTO strategy_backtest_results 
            (run_date, strategy_version, config_json, metrics_json, 
             total_return, sharpe_ratio, max_drawdown, win_rate, 
             total_trades, profit_factor)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            strategy_version,
            json.dumps(config, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False),
            metrics.get('total_return'),
            metrics.get('sharpe_ratio'),
            metrics.get('max_drawdown'),
            metrics.get('win_rate'),
            metrics.get('total_trades'),
            metrics.get('profit_factor')
        ))
        
        backtest_id = cursor.lastrowid
        
        # 插入交易记录
        trades = result.get('trades', [])
        for trade in trades:
            cursor.execute('''
                INSERT INTO strategy_trades 
                (backtest_id, trade_date, code, action, price, shares, amount,
                 commission, stamp_duty, realized_pnl, realized_pnl_pct,
                 hold_days, exit_reason, signal_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id,
                trade.get('date'),
                trade.get('code'),
                trade.get('action'),
                trade.get('price'),
                trade.get('shares'),
                trade.get('amount'),
                trade.get('commission'),
                trade.get('stamp_duty'),
                trade.get('realized_pnl'),
                trade.get('realized_pnl_pct'),
                trade.get('hold_days'),
                trade.get('exit_reason'),
                trade.get('signal_score')
            ))
        
        # 插入每日净值
        daily_values = result.get('daily_values', [])
        for dv in daily_values:
            cursor.execute('''
                INSERT INTO strategy_daily_values 
                (backtest_id, date, cash, positions_value, total_value,
                 total_return, num_positions, exposure, drawdown, daily_return)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id,
                dv.get('date'),
                dv.get('cash'),
                dv.get('positions_value'),
                dv.get('total_value'),
                dv.get('total_return'),
                dv.get('num_positions'),
                dv.get('exposure'),
                dv.get('drawdown'),
                dv.get('daily_return')
            ))
        
        conn.commit()
        conn.close()
        
        print(f"回测结果已记录到 Dashboard (ID: {backtest_id})")
        print(f"  - 交易记录: {len(trades)}条")
        print(f"  - 日净值记录: {len(daily_values)}条")
        
        return backtest_id
    
    def record_experiment(self, hypothesis: str, config_changes: Dict,
                          metrics_before: Dict, metrics_after: Dict,
                          notes: str = "") -> int:
        """记录一次策略实验"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sharpe_before = metrics_before.get('sharpe_ratio', 0)
        sharpe_after = metrics_after.get('sharpe_ratio', 0)
        improvement = sharpe_after - sharpe_before
        
        # 判断实验状态
        if improvement > 0.05:
            status = "success"
        elif improvement > -0.05:
            status = "neutral"
        else:
            status = "failed"
        
        cursor.execute('''
            INSERT INTO strategy_experiments 
            (experiment_date, hypothesis, config_changes, metrics_before, metrics_after,
             sharpe_before, sharpe_after, improvement, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            hypothesis,
            json.dumps(config_changes, ensure_ascii=False),
            json.dumps(metrics_before, ensure_ascii=False),
            json.dumps(metrics_after, ensure_ascii=False),
            sharpe_before,
            sharpe_after,
            improvement,
            status,
            notes
        ))
        
        experiment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"实验记录已保存 (ID: {experiment_id})")
        print(f"  假设: {hypothesis}")
        print(f"  Sharpe: {sharpe_before:.3f} -> {sharpe_after:.3f} ({improvement:+.3f})")
        print(f"  状态: {status}")
        
        return experiment_id
    
    def get_best_result(self, limit: int = 5) -> list:
        """获取最佳回测结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, run_date, strategy_version, sharpe_ratio, 
                   total_return, max_drawdown, win_rate, total_trades
            FROM strategy_backtest_results
            ORDER BY sharpe_ratio DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': r[0],
                'run_date': r[1],
                'version': r[2],
                'sharpe_ratio': r[3],
                'total_return': r[4],
                'max_drawdown': r[5],
                'win_rate': r[6],
                'total_trades': r[7]
            }
            for r in results
        ]
    
    def get_experiment_summary(self) -> Dict:
        """获取实验摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT status, COUNT(*), AVG(improvement)
            FROM strategy_experiments
            GROUP BY status
        ''')
        
        summary = {}
        for row in cursor.fetchall():
            summary[row[0]] = {
                'count': row[1],
                'avg_improvement': row[2]
            }
        
        conn.close()
        return summary
    
    def export_results_to_json(self, backtest_id: int, filepath: str):
        """导出回测结果到JSON文件"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取主记录
        cursor.execute('''
            SELECT * FROM strategy_backtest_results WHERE id = ?
        ''', (backtest_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        # 获取列名
        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))
        
        # 解析JSON字段
        result['config'] = json.loads(result.get('config_json', '{}'))
        result['metrics'] = json.loads(result.get('metrics_json', '{}'))
        del result['config_json']
        del result['metrics_json']
        
        # 获取交易记录
        cursor.execute('''
            SELECT * FROM strategy_trades WHERE backtest_id = ?
        ''', (backtest_id,))
        
        trade_columns = [description[0] for description in cursor.description]
        trades = [dict(zip(trade_columns, r)) for r in cursor.fetchall()]
        result['trades'] = trades
        
        # 获取每日净值
        cursor.execute('''
            SELECT * FROM strategy_daily_values WHERE backtest_id = ?
        ''', (backtest_id,))
        
        dv_columns = [description[0] for description in cursor.description]
        daily_values = [dict(zip(dv_columns, r)) for r in cursor.fetchall()]
        result['daily_values'] = daily_values
        
        conn.close()
        
        # 保存到文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"结果已导出: {filepath}")
        return result

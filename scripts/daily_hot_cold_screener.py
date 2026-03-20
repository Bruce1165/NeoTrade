#!/usr/bin/env python3
"""
每日热冷股筛选器

同时筛选：
- 热股：涨幅≥5%，成交额≥10亿
- 冷股：跌幅≤-5%，成交额≥10亿

输出：
- Dashboard: 分组显示，Tab切换
- Excel: 两个Sheet（热股、冷股）
"""

# 清除代理环境变量，避免网络请求失败
import os
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import sys
import logging
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add workspace to path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))
sys.path.insert(0, str(WORKSPACE_ROOT / "scripts"))

from database import init_db, get_session, Stock, DailyPrice
from sqlalchemy import create_engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = WORKSPACE_ROOT / "data" / "stock_data.db"
OUTPUT_DIR = WORKSPACE_ROOT / "data" / "每日热冷股"

# 涨跌停阈值
LIMIT_UP_THRESHOLDS = {
    '主板': 9.9,
    '创业板': 19.9,
    '科创板': 19.9,
}

LIMIT_DOWN_THRESHOLDS = {
    '主板': -9.9,
    '创业板': -19.9,
    '科创板': -19.9,
}


class DailyHotColdScreener:
    """每日热冷股筛选器"""

    def __init__(self, db_path=None):
        actual_db_path = db_path or DB_PATH
        self.engine = create_engine(f'sqlite:///{actual_db_path}', echo=False)
        init_db(self.engine)
        self.session = get_session(self.engine)

    def get_stock_board(self, code):
        """判断股票所属板块"""
        if code.startswith('68'):
            return '科创板'
        elif code.startswith('30'):
            return '创业板'
        elif code.startswith('00') or code.startswith('60'):
            return '主板'
        else:
            return '其他'

    def get_stock_data(self, code, days=70):
        """获取股票最近N天的数据"""
        query = """
            SELECT trade_date, open, high, low, close, volume, amount, turnover, pct_change
            FROM daily_prices
            WHERE code = ?
            ORDER BY trade_date DESC
            LIMIT ?
        """
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(query, conn, params=(code, days))
        conn.close()

        if df.empty:
            return None

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df = df.sort_values('trade_date').reset_index(drop=True)
        df['code'] = code
        return df

    def calculate_limit_up_stats(self, df, code):
        """计算涨停统计（近20日）"""
        if df is None or len(df) < 5:
            return {'total_limit_up': 0, 'total_limit_down': 0, 'board': self.get_stock_board(code)}

        threshold_up = LIMIT_UP_THRESHOLDS.get(self.get_stock_board(code), 9.9)
        threshold_down = LIMIT_DOWN_THRESHOLDS.get(self.get_stock_board(code), -9.9)
        board = self.get_stock_board(code)

        recent_df = df.tail(20)
        total_limit_up = (recent_df['pct_change'] >= threshold_up).sum()
        total_limit_down = (recent_df['pct_change'] <= threshold_down).sum()

        return {
            'total_limit_up': int(total_limit_up),
            'total_limit_down': int(total_limit_down),
            'board': board
        }

    def calculate_returns(self, df):
        """计算多周期收益率"""
        if df is None or len(df) < 5:
            return {'return_5d': 0, 'return_10d': 0, 'return_20d': 0, 'return_60d': 0}

        latest_close = df.iloc[-1]['close']

        def calc_return(days):
            if len(df) < days + 1:
                return 0
            past_close = df.iloc[-(days+1)]['close']
            if past_close == 0:
                return 0
            return (latest_close - past_close) / past_close * 100

        return {
            'return_5d': round(calc_return(5), 2),
            'return_10d': round(calc_return(10), 2),
            'return_20d': round(calc_return(20), 2),
            'return_60d': round(calc_return(60), 2)
        }

    def detect_anomaly_type(self, row, df, is_hot=True):
        """检测异动类型"""
        anomaly_types = []
        pct_change = row.get('pct_change', 0)

        if is_hot:
            # 热股异动类型
            if row.get('turnover', 0) > 5 and pct_change > 5:
                anomaly_types.append('放量大涨')

            threshold = LIMIT_UP_THRESHOLDS.get(self.get_stock_board(row.get('code', '')), 9.9)
            if pct_change >= threshold:
                anomaly_types.append('涨停')

            if df is not None and len(df) >= 20:
                high_20d = df.tail(20)['high'].max()
                if row.get('high', 0) >= high_20d * 0.99:
                    anomaly_types.append('突破')

            if row.get('turnover', 0) > 15:
                anomaly_types.append('高换手')
        else:
            # 冷股异动类型
            if row.get('turnover', 0) > 5 and pct_change < -5:
                anomaly_types.append('放量大跌')

            threshold = LIMIT_DOWN_THRESHOLDS.get(self.get_stock_board(row.get('code', '')), -9.9)
            if pct_change <= threshold:
                anomaly_types.append('跌停')

            if df is not None and len(df) >= 20:
                low_20d = df.tail(20)['low'].min()
                if row.get('low', 0) <= low_20d * 1.01:
                    anomaly_types.append('破位')

            if row.get('turnover', 0) > 15:
                anomaly_types.append('高换手')

        return ' + '.join(anomaly_types) if anomaly_types else ('异动' if is_hot else '异动下跌')

    def screen_stock(self, stock, latest_date):
        """筛选单只股票，返回热股或冷股或None"""
        code = stock.code
        name = stock.name

        # 排除条件
        if not code or not name:
            return None, None

        if code.startswith('399') or code.startswith('000') or code.startswith('899'):
            return None, None

        if code.startswith('8') or code.startswith('4'):
            return None, None

        if 'ST' in name or '退' in name:
            return None, None

        if stock.list_date:
            try:
                if isinstance(stock.list_date, str):
                    listing = datetime.strptime(stock.list_date, '%Y-%m-%d')
                else:
                    listing = stock.list_date
                if (datetime.now() - listing).days < 60:
                    return None, None
            except:
                pass

        df = self.get_stock_data(code, days=70)
        if df is None or df.empty:
            return None, None

        latest = df.iloc[-1]
        latest_trade_date = latest['trade_date'].strftime('%Y-%m-%d')
        if latest_trade_date != latest_date:
            return None, None

        pct_change = latest.get('pct_change', 0) or 0
        amount = latest.get('amount', 0) or 0

        # 成交额必须≥10亿
        if amount < 1000000000:
            return None, None

        # 判断是热股还是冷股
        is_hot = pct_change >= 5
        is_cold = pct_change <= -5

        if not is_hot and not is_cold:
            return None, None

        limit_stats = self.calculate_limit_up_stats(df, code)
        returns = self.calculate_returns(df)
        anomaly_type = self.detect_anomaly_type({
            'code': code,
            'turnover': latest.get('turnover', 0),
            'pct_change': pct_change,
            'high': latest.get('high', 0),
            'low': latest.get('low', 0)
        }, df, is_hot=True if is_hot else False)

        result = {
            'code': code,
            'name': name,
            'board': limit_stats['board'],
            'close': round(latest['close'], 2),
            'pct_change': round(pct_change, 2),
            'amount': round(amount / 100000000, 2) if amount and not (amount != amount) else 0,
            'turnover': round(latest.get('turnover', 0) or 0, 2),
            'total_market_cap': '-',
            'circulating_cap': '-',
            'industry': stock.industry or '-',
            'pe': '-',
            'pb': '-',
            'total_limit_up': limit_stats['total_limit_up'],
            'total_limit_down': limit_stats['total_limit_down'],
            'return_5d': returns['return_5d'],
            'return_10d': returns['return_10d'],
            'return_20d': returns['return_20d'],
            'return_60d': returns['return_60d'],
            'listing_date': str(stock.list_date) if stock.list_date else '-',
            'anomaly_type': anomaly_type,
            '_type': 'hot' if is_hot else 'cold'
        }

        if is_hot:
            return result, None
        else:
            return None, result

    def check_data_availability(self, trade_date: str) -> bool:
        """检查指定日期的数据是否存在于数据库"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM daily_prices WHERE trade_date = ? LIMIT 1",
            (trade_date,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0

    def run_screening(self, trade_date: str = None):
        """运行筛选，返回热股和冷股"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')

        # 检查数据是否可用（而非简单地检查是否是今天）
        if not self.check_data_availability(trade_date):
            logger.warning(f"⚠️  无可用数据 ({trade_date}) - 市场尚未收盘或数据未下载")
            return {'hot': [], 'cold': [], 'error': 'no_data', 'message': f'无可用数据 ({trade_date})，市场尚未收盘或数据未下载'}

        logger.info("="*60)
        logger.info("每日热冷股筛选器")
        logger.info(f"日期: {trade_date}")
        logger.info("="*60)

        stocks = self.session.query(Stock).all()
        logger.info(f"Total stocks: {len(stocks)}")

        hot_results = []
        cold_results = []
        checked = 0

        for stock in stocks:
            checked += 1
            if checked % 500 == 0:
                logger.info(f"Checked {checked} stocks, hot: {len(hot_results)}, cold: {len(cold_results)}")

            hot, cold = self.screen_stock(stock, trade_date)
            if hot:
                hot_results.append(hot)
                logger.info(f"✓ Hot: {stock.code} {stock.name} - 涨幅{hot['pct_change']:.1f}%")
            elif cold:
                cold_results.append(cold)
                logger.info(f"✓ Cold: {stock.code} {stock.name} - 跌幅{cold['pct_change']:.1f}%")

        logger.info(f"\n{'='*60}")
        logger.info(f"筛选完成!")
        logger.info(f"检查: {checked} 只股票")
        logger.info(f"热股: {len(hot_results)} 只")
        logger.info(f"冷股: {len(cold_results)} 只")
        logger.info(f"{'='*60}")

        return {'hot': hot_results, 'cold': cold_results}

    def save_results(self, results, trade_date: str = None):
        """保存结果到Excel（两个Sheet）和CSV"""
        if not results or (not results.get('hot') and not results.get('cold')):
            logger.warning("没有结果需要保存")
            return None

        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        columns = [
            'code', 'name', 'board', 'industry',
            'close', 'pct_change', 'amount', 'turnover',
            'total_market_cap', 'circulating_cap', 'pe', 'pb',
            'total_limit_up', 'total_limit_down', 'return_5d', 'return_10d', 'return_20d', 'return_60d',
            'listing_date', 'anomaly_type'
        ]

        column_names = [
            '代码', '名称', '板块', '行业',
            '收盘价', '涨幅%', '成交额(亿)', '换手率%',
            '总市值(亿)', '流通市值(亿)', '市盈率', '市净率',
            '累计涨停', '累计跌停', '5日涨幅%', '10日涨幅%', '20日涨幅%', '60日涨幅%',
            '上市日期', '异动类型'
        ]

        # 保存Excel（两个Sheet）
        excel_path = OUTPUT_DIR / f"{trade_date}.xlsx"
        with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
            # 热股Sheet
            if results.get('hot'):
                df_hot = pd.DataFrame(results['hot'])
                df_hot = df_hot[columns]
                df_hot.columns = column_names
                df_hot = df_hot.sort_values(['涨幅%', '成交额(亿)'], ascending=[False, False])
                df_hot.to_excel(writer, sheet_name='热股', index=False)
                logger.info(f"热股已保存到Excel: {len(results['hot'])} 只")

            # 冷股Sheet
            if results.get('cold'):
                df_cold = pd.DataFrame(results['cold'])
                df_cold = df_cold[columns]
                df_cold.columns = column_names
                df_cold = df_cold.sort_values(['涨幅%', '成交额(亿)'], ascending=[True, False])
                df_cold.to_excel(writer, sheet_name='冷股', index=False)
                logger.info(f"冷股已保存到Excel: {len(results['cold'])} 只")

        logger.info(f"Excel结果已保存: {excel_path}")

        # 保存CSV（分开两个文件）
        if results.get('hot'):
            csv_hot_path = OUTPUT_DIR / f"{trade_date}_hot.csv"
            df_hot.to_csv(csv_hot_path, index=False, encoding='utf-8-sig')
            logger.info(f"热股CSV已保存: {csv_hot_path}")

        if results.get('cold'):
            csv_cold_path = OUTPUT_DIR / f"{trade_date}_cold.csv"
            df_cold.to_csv(csv_cold_path, index=False, encoding='utf-8-sig')
            logger.info(f"冷股CSV已保存: {csv_cold_path}")

        return str(excel_path)


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', type=str, help='交易日期 (YYYY-MM-DD)')
    args = parser.parse_args()

    screener = DailyHotColdScreener()
    results = screener.run_screening(args.date)

    if results.get('hot') or results.get('cold'):
        screener.save_results(results, args.date)

        print("\n" + "="*80)
        print("筛选结果:")
        print("="*80)

        if results.get('hot'):
            print(f"\n【热股】共 {len(results['hot'])} 只:")
            for r in results['hot'][:5]:
                print(f"  {r['code']} {r['name']} ({r['board']}): 涨幅{r['pct_change']:.1f}%, 成交额{r['amount']:.1f}亿")
            if len(results['hot']) > 5:
                print(f"  ... 共 {len(results['hot'])} 只")

        if results.get('cold'):
            print(f"\n【冷股】共 {len(results['cold'])} 只:")
            for r in results['cold'][:5]:
                print(f"  {r['code']} {r['name']} ({r['board']}): 跌幅{r['pct_change']:.1f}%, 成交额{r['amount']:.1f}亿")
            if len(results['cold']) > 5:
                print(f"  ... 共 {len(results['cold'])} 只")
        
        # 显示下载链接
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        screener_id = 'daily_hot_cold_screener'
        print(f"\n{'='*60}")
        print(f"📥 下载链接:")
        print(f"  Excel: http://localhost:5003/api/download/{screener_id}/{date_str}")
        print(f"  CSV:   http://localhost:5003/api/download/csv/{screener_id}/{date_str}")
        print(f"{'='*60}")
    else:
        print("\n没有找到符合条件的股票")


if __name__ == '__main__':
    main()

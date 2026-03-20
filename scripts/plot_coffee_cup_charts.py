#!/usr/bin/env python3
"""
咖啡杯形态图表生成器 - Coffee Cup Chart Generator

功能：
- 为筛选出的股票生成杯柄形态K线图
- 支持新目录结构输出
- 批量生成图表
"""

import sys
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
from matplotlib.patches import Rectangle
import os
import logging
import argparse

from output_manager import OutputManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = "data/stock_data.db"


class CoffeeCupChartGenerator:
    """咖啡杯形态图表生成器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.output_manager = OutputManager('coffee_cup')
    
    def get_stock_data(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票日线数据"""
        query = """
            SELECT trade_date, open, high, low, close, volume, amount
            FROM daily_prices
            WHERE code = ? AND trade_date BETWEEN ? AND ?
            ORDER BY trade_date
        """
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(query, conn, params=(code, start_date, end_date))
        conn.close()
        
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        return df
    
    def plot_candlestick(self, ax, df: pd.DataFrame, title: str, 
                         cup_handle_date: str, target_date: str):
        """绘制K线图"""
        cup_handle_dt = pd.to_datetime(cup_handle_date)
        target_dt = pd.to_datetime(target_date)
        
        cup_handle_row = df[df['trade_date'] == cup_handle_dt]
        target_row = df[df['trade_date'] == target_dt]
        
        if cup_handle_row.empty or target_row.empty:
            ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(title)
            return
        
        cup_handle_high = cup_handle_row['high'].values[0]
        target_high = target_row['high'].values[0]
        
        df = df.reset_index(drop=True)
        df['x_pos'] = df.index
        
        cup_handle_idx = df[df['trade_date'] == cup_handle_dt]['x_pos'].values[0]
        target_idx = df[df['trade_date'] == target_dt]['x_pos'].values[0]
        
        between_df = df[(df['x_pos'] >= min(cup_handle_idx, target_idx)) & 
                        (df['x_pos'] <= max(cup_handle_idx, target_idx))]
        
        if not between_df.empty:
            cup_bottom_row = between_df.loc[between_df['low'].idxmin()]
            cup_bottom_price = cup_bottom_row['low']
            cup_bottom_idx = cup_bottom_row['x_pos']
        else:
            cup_bottom_price = df['low'].min()
            cup_bottom_idx = df.loc[df['low'].idxmin(), 'x_pos']
        
        width = 0.6
        
        for idx, row in df.iterrows():
            x = row['x_pos']
            open_p = row['open']
            high = row['high']
            low = row['low']
            close = row['close']
            
            color = 'red' if close >= open_p else 'green'
            
            height = abs(close - open_p)
            bottom = min(open_p, close)
            rect = Rectangle((x - width/2, bottom), width, height, 
                             facecolor=color, edgecolor=color, alpha=0.8)
            ax.add_patch(rect)
            
            ax.plot([x, x], [low, high], color=color, linewidth=0.8)
        
        ax.scatter([cup_handle_idx], [cup_handle_high], 
                  color='blue', s=100, marker='^', zorder=5)
        ax.scatter([target_idx], [target_high], 
                  color='orange', s=100, marker='^', zorder=5)
        
        avg_high = (cup_handle_high + target_high) / 2
        ax.axhline(y=cup_handle_high, color='blue', linestyle='--', alpha=0.7, linewidth=1)
        ax.axhline(y=target_high, color='orange', linestyle='--', alpha=0.7, linewidth=1)
        ax.axhline(y=avg_high, color='purple', linestyle='-', alpha=0.5, linewidth=1.5, 
                   label=f'杯沿均价: {avg_high:.2f}')
        
        ax.axhline(y=cup_bottom_price, color='green', linestyle=':', alpha=0.7, linewidth=1.5)
        ax.scatter([cup_bottom_idx], [cup_bottom_price], 
                  color='green', s=80, marker='v', zorder=5)
        
        cup_depth = (avg_high - cup_bottom_price) / avg_high * 100
        ax.text(0.02, 0.15, f'杯深: {cup_depth:.1f}%', transform=ax.transAxes, 
               fontsize=8, color='green', fontweight='bold',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        ax.axvspan(min(cup_handle_idx, target_idx), max(cup_handle_idx, target_idx), 
                  alpha=0.05, color='gray', label='杯柄区间')
        
        tick_positions = []
        tick_labels = []
        for i in range(0, len(df), max(1, len(df)//6)):
            tick_positions.append(i)
            tick_labels.append(df.iloc[i]['trade_date'].strftime('%m-%d'))
        
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right')
        
        ax.set_title(title, fontsize=10)
        
        price_min = min(df['low'].min(), cup_bottom_price) * 0.97
        price_max = max(df['high'].max(), cup_handle_high, target_high) * 1.03
        ax.set_ylim(price_min, price_max)
        ax.set_xlim(-1, len(df))
        
        ax.legend(loc='upper left', fontsize=7)
        ax.grid(True, alpha=0.3)
    
    def plot_volume(self, ax, df: pd.DataFrame, cup_handle_date: str, target_date: str):
        """绘制成交量图"""
        cup_handle_dt = pd.to_datetime(cup_handle_date)
        target_dt = pd.to_datetime(target_date)
        
        df = df.reset_index(drop=True)
        df['x_pos'] = df.index
        
        cup_handle_idx = df[df['trade_date'] == cup_handle_dt]['x_pos'].values[0] if not df[df['trade_date'] == cup_handle_dt].empty else None
        target_idx = df[df['trade_date'] == target_dt]['x_pos'].values[0] if not df[df['trade_date'] == target_dt].empty else None
        
        colors = ['red' if row['close'] >= row['open'] else 'green' for _, row in df.iterrows()]
        
        ax.bar(df['x_pos'], df['volume']/10000, color=colors, alpha=0.7, width=0.8)
        
        if cup_handle_idx is not None:
            ax.scatter([cup_handle_idx], [df.iloc[cup_handle_idx]['volume']/10000], 
                      color='blue', s=50, marker='^', zorder=5)
        if target_idx is not None:
            ax.scatter([target_idx], [df.iloc[target_idx]['volume']/10000], 
                      color='orange', s=50, marker='^', zorder=5)
        
        ax.set_ylabel('成交量(万股)', fontsize=8)
        
        tick_positions = []
        tick_labels = []
        for i in range(0, len(df), max(1, len(df)//6)):
            tick_positions.append(i)
            tick_labels.append(df.iloc[i]['trade_date'].strftime('%m-%d'))
        
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=45, ha='right')
        ax.set_xlim(-1, len(df))
        ax.grid(True, alpha=0.3)
    
    def generate_chart(self, code: str, name: str, cup_handle_date: str, 
                       target_date: str, volume_multiple: float) -> str:
        """为单只股票生成图表"""
        df = self.get_stock_data(code, cup_handle_date, target_date)
        
        if df.empty:
            logger.warning(f"No data for {code}")
            return ""
        
        fig, (ax_price, ax_vol) = plt.subplots(2, 1, figsize=(10, 8), 
                                                gridspec_kw={'height_ratios': [3, 1]})
        
        title = f"{code} {name} 放量{volume_multiple}x"
        self.plot_candlestick(ax_price, df, title, cup_handle_date, target_date)
        self.plot_volume(ax_vol, df, cup_handle_date, target_date)
        
        plt.tight_layout()
        
        # 保存到图表目录
        charts_dir = self.output_manager.get_charts_dir(target_date)
        output_path = os.path.join(charts_dir, f"{code}.png")
        
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()
        
        logger.info(f"Chart saved: {output_path}")
        return output_path
    
    def generate_charts_from_results(self, date_str: str = None, max_charts: int = 50):
        """
        从筛选结果生成图表
        
        Args:
            date_str: 日期字符串
            max_charts: 最大生成图表数量
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # 读取筛选结果
        results_path = self.output_manager.get_output_path(date_str)
        
        if not os.path.exists(results_path):
            logger.error(f"Results file not found: {results_path}")
            return []
        
        try:
            df = pd.read_excel(results_path)
        except Exception as e:
            logger.error(f"Error reading results: {e}")
            return []
        
        if df.empty:
            logger.warning("No results to generate charts")
            return []
        
        logger.info(f"Generating charts for {len(df)} stocks...")
        
        generated = []
        for idx, row in df.head(max_charts).iterrows():
            try:
                code = str(row.get('股票代码', row.get('code', '')))
                name = row.get('股票名称', row.get('name', ''))
                cup_handle_date = str(row.get('杯柄日期', row.get('handle_date', '')))[:10]
                volume_multiple = row.get('放量倍数', row.get('volume_ratio', 0))
                
                if code and cup_handle_date:
                    chart_path = self.generate_chart(code, name, cup_handle_date, date_str, volume_multiple)
                    if chart_path:
                        generated.append(chart_path)
            except Exception as e:
                logger.error(f"Error generating chart for row {idx}: {e}")
                continue
        
        logger.info(f"Generated {len(generated)} charts")
        return generated
    
    def generate_combined_chart(self, date_str: str = None, stocks_per_page: int = 10):
        """
        生成组合图表（多只股票一页）
        
        Args:
            date_str: 日期字符串
            stocks_per_page: 每页股票数量
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        results_path = self.output_manager.get_output_path(date_str)
        
        if not os.path.exists(results_path):
            logger.error(f"Results file not found: {results_path}")
            return ""
        
        try:
            df = pd.read_excel(results_path)
        except Exception as e:
            logger.error(f"Error reading results: {e}")
            return ""
        
        if df.empty:
            logger.warning("No results to generate charts")
            return ""
        
        # 计算需要的页数
        total_stocks = len(df)
        num_pages = (total_stocks + stocks_per_page - 1) // stocks_per_page
        
        output_paths = []
        
        for page in range(num_pages):
            start_idx = page * stocks_per_page
            end_idx = min(start_idx + stocks_per_page, total_stocks)
            page_df = df.iloc[start_idx:end_idx]
            
            rows = (len(page_df) + 1) // 2
            fig = plt.figure(figsize=(20, rows * 5))
            
            for idx, (_, row) in enumerate(page_df.iterrows()):
                try:
                    code = str(row.get('股票代码', row.get('code', '')))
                    name = row.get('股票名称', row.get('name', ''))
                    cup_handle_date = str(row.get('杯柄日期', row.get('handle_date', '')))[:10]
                    volume_multiple = row.get('放量倍数', row.get('volume_ratio', 0))
                    
                    if not code or not cup_handle_date:
                        continue
                    
                    stock_df = self.get_stock_data(code, cup_handle_date, date_str)
                    
                    if stock_df.empty:
                        continue
                    
                    row_pos = idx // 2
                    col_pos = idx % 2
                    
                    ax_price = plt.subplot2grid((rows * 2, 2), (row_pos * 2, col_pos))
                    title = f"{code} {name} 放量{volume_multiple}x"
                    self.plot_candlestick(ax_price, stock_df, title, cup_handle_date, date_str)
                    
                    ax_vol = plt.subplot2grid((rows * 2, 2), (row_pos * 2 + 1, col_pos), sharex=ax_price)
                    self.plot_volume(ax_vol, stock_df, cup_handle_date, date_str)
                    
                except Exception as e:
                    logger.error(f"Error generating chart for {code}: {e}")
                    continue
            
            plt.tight_layout()
            plt.subplots_adjust(hspace=0.4)
            
            charts_dir = self.output_manager.get_charts_dir(date_str)
            output_path = os.path.join(charts_dir, f"combined_page_{page+1}.png")
            
            plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
            plt.close()
            
            output_paths.append(output_path)
            logger.info(f"Combined chart saved: {output_path}")
        
        return output_paths


def main():
    parser = argparse.ArgumentParser(description='咖啡杯形态图表生成器')
    parser.add_argument('--date', type=str, help='日期 (YYYY-MM-DD)')
    parser.add_argument('--code', type=str, help='单独生成某只股票的图表')
    parser.add_argument('--name', type=str, help='股票名称')
    parser.add_argument('--cup-date', type=str, help='杯柄日期')
    parser.add_argument('--volume-ratio', type=float, default=1.0, help='放量倍数')
    parser.add_argument('--max-charts', type=int, default=50, help='最大生成图表数量')
    parser.add_argument('--combined', action='store_true', help='生成组合图表')
    parser.add_argument('--db-path', type=str, default='data/stock_data.db', help='数据库路径')
    
    args = parser.parse_args()
    
    generator = CoffeeCupChartGenerator(db_path=args.db_path)
    
    if args.code:
        # 生成单只股票图表
        date_str = args.date or datetime.now().strftime('%Y-%m-%d')
        chart_path = generator.generate_chart(
            args.code, 
            args.name or args.code, 
            args.cup_date or date_str,
            date_str,
            args.volume_ratio
        )
        print(f"Chart saved: {chart_path}")
    elif args.combined:
        # 生成组合图表
        output_paths = generator.generate_combined_chart(args.date)
        print(f"Generated {len(output_paths)} combined charts")
    else:
        # 从结果生成图表
        generated = generator.generate_charts_from_results(args.date, args.max_charts)
        print(f"Generated {len(generated)} charts")


if __name__ == '__main__':
    main()

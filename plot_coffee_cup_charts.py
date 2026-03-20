#!/usr/bin/env python3
"""
Coffee Cup Pattern Chart Generator - Metro Style
地铁线路图风格的咖啡杯形态示意图
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime, timedelta
import numpy as np
import os

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

DB_PATH = "/Users/mac/.openclaw/workspace-neo/data/stock_data.db"
OUTPUT_DIR = "/Users/mac/.openclaw/workspace-neo/data/charts"

def get_stocks_from_excel():
    """从咖啡杯筛选结果Excel读取"""
    excel_path = f"/Users/mac/.openclaw/workspace-neo/data/coffee_cup_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        stocks = []
        for _, row in df.iterrows():
            # 格式化股票代码，补齐6位
            code = str(int(row['股票代码'])).zfill(6)
            stocks.append({
                'code': code,
                'name': row['股票名称'],
                'cup_handle_date': str(row['杯柄日期'])[:10],
                'cup_handle_price': row['杯柄价格'],
                'cup_rim_price': row['杯沿价格'],
                'volume_multiple': row['放量倍数'],
                'turnover': row['换手率%'],
                'days_apart': row['间隔天数']
            })
        return stocks
    return []

def get_stock_data(conn, code, start_date, end_date):
    """获取股票日线数据"""
    query = """
    SELECT trade_date, open, high, low, close, volume, amount, turnover
    FROM daily_prices
    WHERE code = ? AND trade_date BETWEEN ? AND ?
    ORDER BY trade_date
    """
    df = pd.read_sql(query, conn, params=(code, start_date, end_date))
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    return df

def get_stock_data_extended(conn, code, cup_handle_date, days_before=60):
    """获取股票日线数据（扩展范围）"""
    handle_dt = pd.to_datetime(cup_handle_date)
    start_dt = handle_dt - timedelta(days=days_before)
    # 查询到最新数据（昨天）
    end_dt = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    
    query = """
    SELECT trade_date, open, high, low, close, volume, amount, turnover
    FROM daily_prices
    WHERE code = ? AND trade_date BETWEEN ? AND ?
    ORDER BY trade_date
    """
    df = pd.read_sql(query, conn, params=(code, start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d')))
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    return df

def plot_coffee_cup(ax, df, stock_info):
    """咖啡杯形态示意图"""
    
    code = stock_info['code']
    name = stock_info['name']
    cup_handle_date = stock_info['cup_handle_date']
    cup_handle_price = stock_info['cup_handle_price']
    cup_rim_price = stock_info['cup_rim_price']
    volume_multiple = stock_info['volume_multiple']
    turnover = stock_info['turnover']
    days_apart = stock_info['days_apart']
    
    cup_handle_dt = pd.to_datetime(cup_handle_date)
    target_dt = df['trade_date'].max()  # 最新日期（昨天）
    
    # 重置索引，用连续的数字作为X轴
    df = df.reset_index(drop=True)
    df['x_pos'] = df.index
    
    # 找到关键点位索引
    cup_handle_idx_list = df[df['trade_date'] == cup_handle_dt]['x_pos'].values
    target_idx_list = df[df['trade_date'] == target_dt]['x_pos'].values
    
    if len(cup_handle_idx_list) == 0 or len(target_idx_list) == 0:
        ax.text(0.5, 0.5, '数据不足', ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f"{code} {name}")
        return
    
    cup_handle_idx = cup_handle_idx_list[0]
    target_idx = target_idx_list[0]
    
    # 找到杯底（杯柄到杯沿之间的最低点）
    between_df = df[(df['x_pos'] >= min(cup_handle_idx, target_idx)) & 
                    (df['x_pos'] <= max(cup_handle_idx, target_idx))]
    if not between_df.empty:
        cup_bottom_row = between_df.loc[between_df['low'].idxmin()]
        cup_bottom_price = cup_bottom_row['low']
        cup_bottom_idx = cup_bottom_row['x_pos']
        cup_bottom_date = cup_bottom_row['trade_date']
    else:
        cup_bottom_price = df['low'].min()
        cup_bottom_idx = df.loc[df['low'].idxmin(), 'x_pos']
        cup_bottom_date = df.loc[df['low'].idxmin(), 'trade_date']
    
    # 计算杯深
    avg_high = (cup_handle_price + cup_rim_price) / 2
    cup_depth = (avg_high - cup_bottom_price) / avg_high * 100
    
    # 创建双Y轴
    ax_price = ax
    ax_volume = ax.twinx()
    
    # 画价格折线（收盘价）- 地铁线路风格
    ax_price.plot(df['x_pos'], df['close'], color='#1f77b4', linewidth=2, label='收盘价')
    
    # 画最高价/最低价线（杯沿轮廓）
    ax_price.plot(df['x_pos'], df['high'], color='#ff7f0e', linewidth=1, alpha=0.4, linestyle='--')
    ax_price.plot(df['x_pos'], df['low'], color='#2ca02c', linewidth=1, alpha=0.4, linestyle='--')
    
    # 画成交量（柱状图）
    if df['volume'].max() > 0:
        price_range = df['high'].max() - df['low'].min()
        volume_normalized = df['volume'] / df['volume'].max() * (price_range * 0.25)
        volume_base = df['low'].min() - price_range * 0.05
        colors = ['#d62728' if c >= o else '#2ca02c' for c, o in zip(df['close'], df['open'])]
        ax_volume.bar(df['x_pos'], volume_normalized, bottom=volume_base, 
                     color=colors, alpha=0.3, width=0.8)
    
    # 标记关键点位
    # 杯柄
    ax_price.scatter([cup_handle_idx], [cup_handle_price], color='blue', s=150, marker='o', 
                    zorder=5, edgecolors='white', linewidths=2)
    ax_price.annotate(f'柄{cup_handle_price:.1f}', 
                     xy=(cup_handle_idx, cup_handle_price),
                     xytext=(cup_handle_idx-5, cup_handle_price*1.03), fontsize=8, color='blue',
                     arrowprops=dict(arrowstyle='->', color='blue', alpha=0.5))
    
    # 杯沿（昨天）
    ax_price.scatter([target_idx], [cup_rim_price], color='orange', s=150, marker='s', 
                    zorder=5, edgecolors='white', linewidths=2)
    ax_price.annotate(f'沿{cup_rim_price:.1f}', 
                     xy=(target_idx, cup_rim_price),
                     xytext=(target_idx+3, cup_rim_price*1.03), fontsize=8, color='orange',
                     arrowprops=dict(arrowstyle='->', color='orange', alpha=0.5))
    
    # 杯底
    ax_price.scatter([cup_bottom_idx], [cup_bottom_price], color='green', s=120, marker='v', 
                    zorder=5, edgecolors='white', linewidths=2)
    ax_price.annotate(f'底{cup_bottom_price:.1f}\n深{cup_depth:.0f}%', 
                     xy=(cup_bottom_idx, cup_bottom_price),
                     xytext=(cup_bottom_idx, cup_bottom_price*0.96), fontsize=7, color='green',
                     ha='center', va='top',
                     bbox=dict(boxstyle='round,pad=0.2', facecolor='lightgreen', alpha=0.6))
    
    # 画杯沿参考线
    ax_price.axhline(y=cup_handle_price, color='blue', linestyle='--', alpha=0.3, linewidth=1)
    ax_price.axhline(y=cup_rim_price, color='orange', linestyle='--', alpha=0.3, linewidth=1)
    
    # 填充杯柄区域
    ax_price.axvspan(min(cup_handle_idx, target_idx), max(cup_handle_idx, target_idx), 
                    alpha=0.08, color='brown')
    
    # 设置标题
    title = f"{code} {name}\n放量{volume_multiple:.1f}x 换手{turnover:.1f}% 间隔{days_apart}天"
    ax_price.set_title(title, fontsize=9, fontweight='bold')
    
    # 设置X轴标签
    tick_positions = []
    tick_labels = []
    step = max(1, len(df) // 5)
    for i in range(0, len(df), step):
        tick_positions.append(i)
        tick_labels.append(df.iloc[i]['trade_date'].strftime('%m-%d'))
    ax_price.set_xticks(tick_positions)
    ax_price.set_xticklabels(tick_labels, rotation=0, fontsize=7)
    
    # 设置Y轴范围
    price_min = min(df['low'].min(), cup_bottom_price) * 0.94
    price_max = max(df['high'].max(), cup_handle_price, cup_rim_price) * 1.06
    ax_price.set_ylim(price_min, price_max)
    ax_price.set_xlim(-1, len(df))
    
    # 隐藏成交量Y轴刻度
    ax_volume.set_yticks([])
    
    # 添加网格
    ax_price.grid(True, alpha=0.2, linestyle='--')

def create_charts():
    """创建所有股票的图表"""
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    STOCKS = get_stocks_from_excel()
    
    if not STOCKS:
        print("没有找到股票数据")
        return
    
    print(f"找到 {len(STOCKS)} 只股票，正在生成图表...")
    
    # 创建大图 (5行3列，支持15只股票)
    n_stocks = len(STOCKS)
    n_rows = (n_stocks + 2) // 3  # 向上取整
    fig, axes = plt.subplots(n_rows, 3, figsize=(16, 3.5 * n_rows))
    
    if n_stocks == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    
    for idx, stock in enumerate(STOCKS):
        code = stock['code']
        cup_handle_date = stock['cup_handle_date']
        
        # 获取数据：从杯柄日期前60天到昨天（扩展范围）
        df = get_stock_data_extended(conn, code, cup_handle_date, days_before=60)
        
        if df.empty or len(df) < 10:
            axes[idx].text(0.5, 0.5, '数据不足', ha='center', va='center', transform=axes[idx].transAxes)
            axes[idx].set_title(f"{code} {stock['name']}")
            continue
        
        plot_coffee_cup(axes[idx], df, stock)
    
    # 隐藏多余的子图
    for idx in range(n_stocks, len(axes)):
        axes[idx].axis('off')
    
    conn.close()
    
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.4, wspace=0.2)
    
    output_path = os.path.join(OUTPUT_DIR, f"coffee_cup_{datetime.now().strftime('%Y-%m-%d')}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"图表已保存至: {output_path}")
    
    plt.close()

if __name__ == "__main__":
    create_charts()

#!/usr/bin/env python3
"""
涨停倍量阴图表生成器
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

def get_stock_data(conn, code, days=30):
    """获取股票数据"""
    query = """
    SELECT trade_date, open, high, low, close, volume
    FROM daily_prices
    WHERE code = ?
    ORDER BY trade_date DESC
    LIMIT ?
    """
    df = pd.read_sql(query, conn, params=(code, days))
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').reset_index(drop=True)
    return df

def get_stocks_from_excel():
    """从Excel读取"""
    excel_path = f"/Users/mac/.openclaw/workspace-neo/data/zhang_ting_bei_liang_yin_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    if os.path.exists(excel_path):
        df = pd.read_excel(excel_path)
        stocks = []
        for _, row in df.iterrows():
            stocks.append({
                'code': str(row['股票代码']).zfill(6),
                'name': row['股票名称'],
                'zt_date': str(row['涨停日期']),
                'bei_liang_date': str(row['倍量阴日期']),
                'di_liang_date': str(row['地量日期']),
                'volume_ratio': row['倍量比例'],
                'di_liang_ratio': row['地量比例']
            })
        return stocks
    return []

def plot_pattern(ax, df, stock_info):
    """绘制涨停倍量阴形态"""
    code = stock_info['code']
    name = stock_info['name']
    zt_date = stock_info['zt_date']
    bei_liang_date = stock_info['bei_liang_date']
    di_liang_date = stock_info['di_liang_date']
    volume_ratio = stock_info['volume_ratio']
    di_liang_ratio = stock_info['di_liang_ratio']
    
    zt_dt = pd.to_datetime(zt_date)
    bei_liang_dt = pd.to_datetime(bei_liang_date)
    di_liang_dt = pd.to_datetime(di_liang_date)
    
    # 重置索引
    df = df.reset_index(drop=True)
    df['x_pos'] = df.index
    
    # 找到关键点位
    zt_idx_list = df[df['trade_date'] == zt_dt]['x_pos'].values
    bei_liang_idx_list = df[df['trade_date'] == bei_liang_dt]['x_pos'].values
    di_liang_idx_list = df[df['trade_date'] == di_liang_dt]['x_pos'].values
    
    # 创建双Y轴
    ax_price = ax
    ax_volume = ax.twinx()
    
    # 画K线（简化版）
    for i, row in df.iterrows():
        color = 'red' if row['close'] >= row['open'] else 'green'
        # 实体
        ax_price.bar(i, row['close'] - row['open'], bottom=row['open'], 
                    color=color, width=0.6, edgecolor=color)
        # 影线
        ax_price.plot([i, i], [row['low'], row['high']], color=color, linewidth=1)
    
    # 画成交量
    max_vol = df['volume'].max()
    price_range = df['high'].max() - df['low'].min()
    for i, row in df.iterrows():
        color = 'red' if row['close'] >= row['open'] else 'green'
        vol_height = row['volume'] / max_vol * (price_range * 0.2)
        ax_volume.bar(i, vol_height, bottom=df['low'].min() - price_range * 0.05,
                     color=color, alpha=0.3, width=0.6)
    
    # 标记关键点位
    if len(zt_idx_list) > 0:
        zt_idx = zt_idx_list[0]
        ax_price.scatter([zt_idx], [df.iloc[zt_idx]['close']], 
                        color='red', s=150, marker='*', zorder=5, edgecolors='white', linewidths=2)
        ax_price.annotate('涨停', xy=(zt_idx, df.iloc[zt_idx]['close']),
                         xytext=(zt_idx-2, df.iloc[zt_idx]['close']*1.02), 
                         fontsize=8, color='red', fontweight='bold')
    
    if len(bei_liang_idx_list) > 0:
        bei_idx = bei_liang_idx_list[0]
        ax_price.scatter([bei_idx], [df.iloc[bei_idx]['close']], 
                        color='green', s=150, marker='v', zorder=5, edgecolors='white', linewidths=2)
        ax_price.annotate(f'倍量\n{volume_ratio:.1f}x', xy=(bei_idx, df.iloc[bei_idx]['close']),
                         xytext=(bei_idx, df.iloc[bei_idx]['low']*0.98), 
                         fontsize=7, color='green', ha='center', va='top')
    
    if len(di_liang_idx_list) > 0:
        di_idx = di_liang_idx_list[0]
        ax_price.scatter([di_idx], [df.iloc[di_idx]['close']], 
                        color='blue', s=120, marker='o', zorder=5, edgecolors='white', linewidths=2)
        ax_price.annotate(f'地量\n{di_liang_ratio:.1f}x', xy=(di_idx, df.iloc[di_idx]['close']),
                         xytext=(di_idx, df.iloc[di_idx]['low']*0.98), 
                         fontsize=7, color='blue', ha='center', va='top')
    
    # 设置标题
    title = f"{code} {name}\n涨停{zt_date[5:]} 倍量阴{bei_liang_date[5:]} 地量{di_liang_date[5:]}"
    ax_price.set_title(title, fontsize=9, fontweight='bold')
    
    # 设置X轴
    tick_positions = []
    tick_labels = []
    step = max(1, len(df) // 5)
    for i in range(0, len(df), step):
        tick_positions.append(i)
        tick_labels.append(df.iloc[i]['trade_date'].strftime('%m-%d'))
    ax_price.set_xticks(tick_positions)
    ax_price.set_xticklabels(tick_labels, rotation=0, fontsize=7)
    
    # 隐藏成交量Y轴
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
    
    # 创建大图 (6行6列，支持36只股票)
    n_stocks = len(STOCKS)
    n_rows = (n_stocks + 5) // 6
    fig, axes = plt.subplots(n_rows, 6, figsize=(20, 3.5 * n_rows))
    
    if n_stocks == 1:
        axes = np.array([axes])
    axes = axes.flatten()
    
    for idx, stock in enumerate(STOCKS):
        code = stock['code']
        zt_date = stock['zt_date']
        
        # 获取数据：从涨停前5天到最新
        start_dt = pd.to_datetime(zt_date) - timedelta(days=15)
        end_dt = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
        
        df = get_stock_data(conn, code, days=30)
        
        if df.empty or len(df) < 5:
            axes[idx].text(0.5, 0.5, '数据不足', ha='center', va='center', transform=axes[idx].transAxes)
            axes[idx].set_title(f"{code} {stock['name']}")
            continue
        
        plot_pattern(axes[idx], df, stock)
    
    # 隐藏多余的子图
    for idx in range(n_stocks, len(axes)):
        axes[idx].axis('off')
    
    conn.close()
    
    plt.tight_layout()
    plt.subplots_adjust(hspace=0.4, wspace=0.2)
    
    output_path = os.path.join(OUTPUT_DIR, f"zhang_ting_bei_liang_yin_{datetime.now().strftime('%Y-%m-%d')}.png")
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"图表已保存至: {output_path}")
    
    plt.close()

if __name__ == "__main__":
    create_charts()

#!/usr/bin/env python3
"""
东方财富涨停原因爬虫
爬取涨停页面的涨停原因字段
"""

import requests
import json
import pandas as pd
from datetime import datetime
from typing import Optional


def fetch_zt_reasons(date: Optional[str] = None) -> pd.DataFrame:
    """
    获取涨停原因数据
    
    Args:
        date: 日期 (YYYYMMDD)，默认今天
        
    Returns:
        DataFrame 包含涨停原因
    """
    if date is None:
        date = datetime.now().strftime('%Y%m%d')
    
    # 东方财富涨停数据API
    url = "http://push2ex.eastmoney.com/getTopicZTPool"
    
    params = {
        'ut': '7eea3edcaed734bea9cbfc24409ed989',
        'dpt': 'wz.ztzt',
        'Pageindex': '0',
        'pagesize': '1000',
        'sort': 'fbt:asc',
        'date': date,
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        data = response.json()
        
        if 'data' not in data or 'pool' not in data['data']:
            print(f"未获取到数据: {data}")
            return pd.DataFrame()
        
        pool = data['data']['pool']
        
        records = []
        for item in pool:
            record = {
                '代码': item.get('c', ''),
                '名称': item.get('n', ''),
                '涨跌幅': item.get('zdp', 0),
                '最新价': item.get('p', 0) / 1000,  # 价格需要除以1000
                '涨停原因': item.get('zttz', ''),  # 涨停特征/原因
                '封单金额': item.get('amount', 0),
                '首次封板时间': item.get('fbt', ''),
                '最后封板时间': item.get('lbt', ''),
                '炸板次数': item.get('zbc', 0),
                '连板数': item.get('lbc', 0),
                '所属行业': item.get('hybk', ''),
            }
            records.append(record)
        
        df = pd.DataFrame(records)
        
        # 过滤有效数据
        df = df[df['代码'] != '']
        
        return df
        
    except Exception as e:
        print(f"获取数据失败: {e}")
        return pd.DataFrame()


if __name__ == '__main__':
    print("="*80)
    print("东方财富涨停原因获取")
    print("="*80)
    
    # 获取今日数据
    df = fetch_zt_reasons('20260311')
    
    if df.empty:
        print("未获取到数据")
    else:
        print(f"\n获取到 {len(df)} 只涨停股")
        print(f"\n数据列: {list(df.columns)}")
        
        # 显示有涨停原因的股票
        df_with_reason = df[df['涨停原因'] != '']
        print(f"\n有涨停原因的股票: {len(df_with_reason)} 只")
        
        if len(df_with_reason) > 0:
            print("\n前10只有涨停原因的股票:")
            print(df_with_reason[['代码', '名称', '涨停原因', '连板数']].head(10).to_string(index=False))
        else:
            print("\n显示所有股票:")
            print(df[['代码', '名称', '所属行业', '连板数']].head(10).to_string(index=False))

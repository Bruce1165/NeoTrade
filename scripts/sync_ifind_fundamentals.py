#!/usr/bin/env python3
"""
iFind 数据同步脚本 - 每日收盘后更新股票基本信息
包括：板块分类、市值、财务指标
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 添加路径
sys.path.insert(0, '/Users/mac/pilot-ifind/src')
sys.path.insert(0, '/Users/mac/.openclaw/workspace-neo/scripts')

from mcp_client import IfindMCPClient

# 配置
DB_PATH = Path('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
BATCH_SIZE = 50  # 每批处理50只，避免API限制

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IfindDataSync:
    """iFind 数据同步器"""
    
    def __init__(self):
        self.client = IfindMCPClient('stock')
        self.db_path = str(DB_PATH)
        
    def get_all_stock_codes(self) -> List[str]:
        """获取所有股票代码"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT code FROM stocks ORDER BY code")
        codes = [row[0] for row in cursor.fetchall()]
        conn.close()
        logger.info(f"📊 数据库中共有 {len(codes)} 只股票")
        return codes
    
    def parse_financial_table(self, answer: str) -> Dict[str, any]:
        """解析 iFind 返回的表格数据"""
        result = {}
        import re
        
        # 找到表格行（包含数据的那一行）
        lines = answer.split('\n')
        header_line = None
        data_line = None
        
        for line in lines:
            if '|证券代码|' in line:
                header_line = line
            elif line.startswith('|') and '---' not in line and header_line and not data_line:
                # 这是数据行（第一行数据）
                if '.SZ' in line or '.SH' in line:
                    data_line = line
        
        if not header_line or not data_line:
            return result
        
        # 解析表头
        headers = [h.strip() for h in header_line.split('|')]
        # 解析数据
        values = [v.strip() for v in data_line.split('|')]
        
        # 创建字段映射
        for i, header in enumerate(headers):
            if i >= len(values):
                break
            value = values[i]
            
            # 映射关键字段
            field_mapping = {
                '所属申万行业': 'sector_lv1',
                '所属同花顺行业': 'sector_lv2',
                '总市值（单位：元）': 'total_market_cap',
                '流通市值（单位：元）': 'circulating_market_cap',
                '市盈率': 'pe_ratio',
                'ROE': 'roe',
                '资产负债率': 'debt_ratio',
                '营业收入': 'revenue',
                '净利润': 'profit',
            }
            
            for key, db_field in field_mapping.items():
                if key in header:
                    # 提取数值（去除单位如"亿"）
                    if '亿' in value:
                        numbers = re.findall(r'[\d.]+', value.replace(',', ''))
                        if numbers:
                            try:
                                result[db_field] = float(numbers[0])
                            except:
                                result[db_field] = value
                    elif value and value not in ['\t', '']:
                        # 尝试转为浮点数
                        try:
                            result[db_field] = float(value.replace(',', ''))
                        except:
                            result[db_field] = value
        
        return result
    
    def fetch_stock_data(self, code: str) -> Optional[Dict]:
        """从 iFind 获取单只股票数据"""
        try:
            # 获取财务数据（包含板块、市值）
            result = self.client.call_tool(
                'get_stock_financials', 
                {'query': f'{code} 所属申万行业 所属同花顺行业 总市值 流通市值 市盈率 ROE'}
            )
            
            if isinstance(result, dict) and result.get('code') == 1:
                answer = result.get('data', {}).get('answer', '')
                return self.parse_financial_table(answer)
            
            return None
            
        except Exception as e:
            logger.warning(f"   获取 {code} 数据失败: {e}")
            return None
    
    def update_stock_in_db(self, code: str, data: Dict):
        """更新数据库中的股票数据"""
        conn = sqlite3.connect(self.db_path)
        
        fields = []
        values = []
        
        field_mapping = {
            'sector_lv1': data.get('sector_lv1'),
            'sector_lv2': data.get('sector_lv2'),
            'total_market_cap': data.get('total_market_cap'),
            'circulating_market_cap': data.get('circulating_market_cap'),
            'pe_ratio': data.get('pe_ratio'),
            'roe': data.get('roe'),
            'debt_ratio': data.get('debt_ratio'),
            'revenue': data.get('revenue'),
            'profit': data.get('profit'),
            'ifind_updated_at': datetime.now().isoformat(),
        }
        
        for field, value in field_mapping.items():
            if value is not None:
                fields.append(f"{field} = ?")
                values.append(value)
        
        if fields:
            values.append(code)
            query = f"UPDATE stocks SET {', '.join(fields)} WHERE code = ?"
            conn.execute(query, values)
            conn.commit()
        
        conn.close()
    
    def sync_all(self, max_stocks: int = None):
        """同步所有股票数据"""
        codes = self.get_all_stock_codes()
        
        if max_stocks:
            codes = codes[:max_stocks]
        
        total = len(codes)
        success = 0
        failed = 0
        
        logger.info(f"🚀 开始同步 {total} 只股票的 iFind 数据")
        logger.info(f"   预计耗时: {total * 0.5 / 60:.1f} 分钟 (约0.5秒/只)")
        
        start_time = datetime.now()
        
        for i, code in enumerate(codes, 1):
            try:
                data = self.fetch_stock_data(code)
                if data:
                    self.update_stock_in_db(code, data)
                    success += 1
                    logger.info(f"   [{i}/{total}] {code} ✅ {data.get('sector_lv1', 'N/A')}")
                else:
                    failed += 1
                    logger.warning(f"   [{i}/{total}] {code} ⚠️  无数据")
                
                # 每50只保存进度
                if i % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = i / elapsed
                    remaining = (total - i) / rate if rate > 0 else 0
                    logger.info(f"📈 进度: {i}/{total} ({i/total*100:.1f}%), "
                              f"预计剩余 {remaining/60:.1f} 分钟")
                
            except Exception as e:
                failed += 1
                logger.error(f"   [{i}/{total}] {code} ❌ 错误: {e}")
                continue
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"\n✅ 同步完成: 成功 {success}, 失败 {failed}, 总计 {total}")
        logger.info(f"   耗时: {elapsed/60:.1f} 分钟, 平均 {elapsed/total:.2f} 秒/只")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='iFind 数据同步')
    parser.add_argument('--max', type=int, help='最多处理多少只股票（测试用）')
    args = parser.parse_args()
    
    sync = IfindDataSync()
    sync.sync_all(max_stocks=args.max)


if __name__ == '__main__':
    main()

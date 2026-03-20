"""
实时行情模块
Real-time quotation
"""
import time
import json
import logging
from typing import List, Dict, Any
import pandas as pd
from ifind_client import IfindClient

logger = logging.getLogger(__name__)


class RealtimeFeed:
    """实时行情订阅"""
    
    ENDPOINT = "real_time_quotation"
    
    # 常用指标
    BASIC_INDICATORS = "latest,change,changeRatio,open,high,low,preClose,volume,amount"
    FULL_INDICATORS = (
        "latest,change,changeRatio,open,high,low,preClose,volume,amount,"
        "turnoverRatio,totalBidVol,totalAskVol,bid1,ask1,bidSize1,askSize1,"
        "mainNetInflow,largeNetInflow,bigNetInflow,middleNetInflow,smallNetInflow"
    )
    
    def __init__(self, client: IfindClient = None):
        self.client = client or IfindClient()
        self.running = False
    
    def fetch(self, codes: List[str], indicators: str = None) -> pd.DataFrame:
        """
        获取实时行情（单次）
        
        Args:
            codes: 股票代码列表，如 ['300033.SZ', '600000.SH']
            indicators: 指标字符串，默认基础指标
            
        Returns:
            DataFrame 格式的行情数据
        """
        if indicators is None:
            indicators = self.BASIC_INDICATORS
        
        # 批量处理（每次最多100只）
        batch_size = 100
        all_data = []
        
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            codes_str = ",".join(batch)
            
            params = {
                "codes": codes_str,
                "indicators": indicators
            }
            
            try:
                data = self.client.post(self.ENDPOINT, params)
                df = self._parse_response(data)
                all_data.append(df)
                logger.info(f"✅ 获取 {len(batch)} 只股票实时行情")
                
            except Exception as e:
                logger.error(f"❌ 获取行情失败: {e}")
                raise
        
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    
    def subscribe(self, codes: List[str], indicators: str = None, 
                  interval: int = 3, callback = None):
        """
        订阅实时行情（循环模式）
        
        Args:
            codes: 股票代码列表
            indicators: 指标字符串
            interval: 轮询间隔（秒）
            callback: 回调函数，接收 DataFrame 参数
        """
        self.running = True
        logger.info(f"🔄 开始订阅实时行情，股票数: {len(codes)}, 间隔: {interval}s")
        
        try:
            while self.running:
                try:
                    df = self.fetch(codes, indicators)
                    
                    if callback:
                        callback(df)
                    else:
                        print(df.to_string(index=False))
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"❌ 订阅错误: {e}")
                    time.sleep(interval)
                    
        except KeyboardInterrupt:
            logger.info("⏹️ 订阅已停止")
            self.running = False
    
    def stop(self):
        """停止订阅"""
        self.running = False
        logger.info("⏹️ 停止订阅")
    
    def _parse_response(self, data: Dict[str, Any]) -> pd.DataFrame:
        """解析 API 响应"""
        tables = data.get('tables', [])
        
        if not tables:
            return pd.DataFrame()
        
        # 转换格式
        records = []
        for table in tables:
            thscode = table.get('thscode', '')
            table_data = table.get('table', {})
            
            record = {'thscode': thscode}
            
            # 提取指标值
            for key, values in table_data.items():
                if key in ['time', 'thscode']:
                    continue
                if values and len(values) > 0:
                    record[key] = values[0]
                else:
                    record[key] = None
            
            records.append(record)
        
        return pd.DataFrame(records)


def demo():
    """演示：获取实时行情"""
    feed = RealtimeFeed()
    
    # 获取单只股票
    print("=== 单只股票 ===")
    df = feed.fetch(['300033.SZ'])
    print(df.to_string(index=False))
    
    # 获取多只股票的完整指标
    print("\n=== 多只股票（完整指标）===")
    df = feed.fetch(['300033.SZ', '600000.SH'], indicators=RealtimeFeed.FULL_INDICATORS)
    print(df.to_string(index=False))


if __name__ == '__main__':
    demo()
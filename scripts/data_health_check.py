#!/usr/bin/env python3
"""
数据健康检查脚本 - Neo股票数据分析系统
检查项:
1. 数据新鲜度 - 最新数据日期是否为最近交易日
2. 股票数量完整性 - 是否包含4663只股票
3. 重复数据检查 - 是否违反唯一约束

Author: SRE Agent
Created: 2026-03-19
"""

import sqlite3
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# 配置
DB_PATH = Path(__file__).parent.parent / "data" / "stock_data.db"
LOGS_DIR = Path(__file__).parent.parent / "logs"
ALERTS_DIR = Path(__file__).parent.parent / "alerts"
EXPECTED_STOCK_COUNT = 4663

# 确保目录存在
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ALERTS_DIR.mkdir(parents=True, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / "data_health.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DataHealthChecker:
    """数据健康检查器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self.conn = None
        self.cursor = None
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "status": "unknown",
            "checks": {},
            "alerts": []
        }
        
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            logger.info(f"数据库连接成功: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            self.report["alerts"].append({
                "severity": "critical",
                "type": "database_connection_error",
                "message": f"无法连接到数据库: {e}"
            })
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.conn:
            self.conn.close()
            logger.debug("数据库连接已关闭")
    
    def get_last_trade_date(self) -> datetime:
        """获取最近交易日（考虑周末和节假日）"""
        now = datetime.now()
        today = now.date()
        
        # 简单逻辑：如果是周一，最近交易日是上周五；否则是昨天
        weekday = today.weekday()  # 周一=0, 周日=6
        
        if weekday == 0:  # 周一
            days_back = 3
        elif weekday == 6:  # 周日
            days_back = 2
        else:
            # 检查是否是节假日（这里简化处理，实际可从数据库或API获取）
            days_back = 1
            
        last_trade_date = today - timedelta(days=days_back)
        
        # 如果是早上8:30之前，使用前一个交易日
        if now.hour < 8 or (now.hour == 8 and now.minute < 30):
            if weekday == 1:  # 周二早上 -> 上周五
                last_trade_date = today - timedelta(days=4)
            else:
                last_trade_date = today - timedelta(days=1)
                
        return last_trade_date
    
    def check_data_freshness(self) -> Dict[str, Any]:
        """检查数据新鲜度"""
        logger.info("检查数据新鲜度...")
        
        try:
            # 获取数据库最新日期
            self.cursor.execute("SELECT MAX(trade_date) as latest_date FROM daily_prices")
            result = self.cursor.fetchone()
            db_latest_date = result['latest_date'] if result and result['latest_date'] else None
            
            if not db_latest_date:
                return {
                    "status": "fail",
                    "latest_date_in_db": None,
                    "expected_date": None,
                    "message": "数据库中没有价格数据"
                }
            
            # 转换日期格式
            db_date = datetime.strptime(db_latest_date, '%Y-%m-%d').date() if isinstance(db_latest_date, str) else db_latest_date
            expected_date = self.get_last_trade_date()
            
            # 计算延迟
            delay_days = (expected_date - db_date).days
            
            check_result = {
                "status": "pass" if delay_days <= 0 else "fail",
                "latest_date_in_db": str(db_date),
                "expected_date": str(expected_date),
                "delay_days": max(0, delay_days),
                "message": f"数据最新日期: {db_date}, 期望日期: {expected_date}, 延迟: {max(0, delay_days)}天"
            }
            
            if delay_days > 0:
                alert = {
                    "severity": "warning" if delay_days <= 1 else "critical",
                    "type": "data_stale",
                    "message": f"数据延迟 {delay_days} 天，最新数据日期: {db_date}"
                }
                self.report["alerts"].append(alert)
                logger.warning(alert["message"])
            else:
                logger.info(f"数据新鲜度正常，最新日期: {db_date}")
                
            return check_result
            
        except Exception as e:
            logger.error(f"检查数据新鲜度时出错: {e}")
            return {
                "status": "error",
                "message": f"检查失败: {e}"
            }
    
    def check_stock_completeness(self) -> Dict[str, Any]:
        """检查股票数量完整性"""
        logger.info("检查股票数量完整性...")
        
        try:
            # 获取最新日期的股票数量
            self.cursor.execute("""
                SELECT COUNT(DISTINCT code) as count 
                FROM daily_prices 
                WHERE trade_date = (SELECT MAX(trade_date) FROM daily_prices)
            """)
            result = self.cursor.fetchone()
            actual_count = result['count'] if result else 0
            
            # 获取stocks表中的总数
            self.cursor.execute("SELECT COUNT(*) as count FROM stocks")
            total_stocks = self.cursor.fetchone()['count']
            
            missing_count = EXPECTED_STOCK_COUNT - actual_count
            
            check_result = {
                "status": "pass" if missing_count == 0 else "warning" if missing_count < 10 else "fail",
                "actual_count": actual_count,
                "expected_count": EXPECTED_STOCK_COUNT,
                "total_stocks_in_db": total_stocks,
                "missing_count": missing_count,
                "message": f"最新日期股票数量: {actual_count}/{EXPECTED_STOCK_COUNT}, 缺失: {missing_count}"
            }
            
            if missing_count > 0:
                # 获取缺失的股票列表
                self.cursor.execute("""
                    SELECT s.code, s.name 
                    FROM stocks s
                    WHERE s.code NOT IN (
                        SELECT DISTINCT code 
                        FROM daily_prices 
                        WHERE trade_date = (SELECT MAX(trade_date) FROM daily_prices)
                    )
                    LIMIT 20
                """)
                missing_stocks = [dict(row) for row in self.cursor.fetchall()]
                check_result["missing_stocks_sample"] = missing_stocks
                
                alert = {
                    "severity": "warning" if missing_count < 50 else "critical",
                    "type": "incomplete_data",
                    "message": f"股票数据不完整，缺失 {missing_count} 只",
                    "details": {"missing_count": missing_count, "sample": missing_stocks}
                }
                self.report["alerts"].append(alert)
                logger.warning(alert["message"])
            else:
                logger.info(f"股票数量完整: {actual_count} 只")
                
            return check_result
            
        except Exception as e:
            logger.error(f"检查股票完整性时出错: {e}")
            return {
                "status": "error",
                "message": f"检查失败: {e}"
            }
    
    def check_duplicate_data(self) -> Dict[str, Any]:
        """检查重复数据"""
        logger.info("检查重复数据...")
        
        try:
            # 检查违反唯一约束的数据
            self.cursor.execute("""
                SELECT code, trade_date, COUNT(*) as cnt
                FROM daily_prices
                GROUP BY code, trade_date
                HAVING cnt > 1
            """)
            duplicates = self.cursor.fetchall()
            duplicate_count = len(duplicates)
            
            # 计算重复记录总数
            total_duplicate_records = sum(row['cnt'] for row in duplicates) if duplicates else 0
            
            check_result = {
                "status": "pass" if duplicate_count == 0 else "fail",
                "duplicate_groups": duplicate_count,
                "total_duplicate_records": total_duplicate_records,
                "message": f"发现 {duplicate_count} 组重复数据，共 {total_duplicate_records} 条记录"
            }
            
            if duplicate_count > 0:
                # 获取重复数据样本
                duplicate_samples = [
                    {"code": row['code'], "trade_date": row['trade_date'], "count": row['cnt']}
                    for row in duplicates[:10]
                ]
                check_result["samples"] = duplicate_samples
                
                alert = {
                    "severity": "critical",
                    "type": "duplicate_data",
                    "message": f"发现 {duplicate_count} 组重复数据",
                    "details": {"duplicate_groups": duplicate_count, "samples": duplicate_samples}
                }
                self.report["alerts"].append(alert)
                logger.error(alert["message"])
            else:
                logger.info("无重复数据")
                
            return check_result
            
        except Exception as e:
            logger.error(f"检查重复数据时出错: {e}")
            return {
                "status": "error",
                "message": f"检查失败: {e}"
            }
    
    def check_data_quality(self) -> Dict[str, Any]:
        """检查数据质量（扩展检查）"""
        logger.info("检查数据质量...")
        
        quality_issues = []
        
        try:
            # 检查异常价格数据（涨跌幅超过20%）
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM daily_prices 
                WHERE ABS(pct_change) > 20
            """)
            extreme_changes = self.cursor.fetchone()['count']
            
            if extreme_changes > 0:
                quality_issues.append({
                    "type": "extreme_price_change",
                    "count": extreme_changes,
                    "message": f"发现 {extreme_changes} 条涨跌幅超过20%的记录"
                })
            
            # 检查零成交量数据
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM daily_prices 
                WHERE volume = 0 OR volume IS NULL
            """)
            zero_volume = self.cursor.fetchone()['count']
            
            if zero_volume > 0:
                quality_issues.append({
                    "type": "zero_volume",
                    "count": zero_volume,
                    "message": f"发现 {zero_volume} 条零成交量记录"
                })
            
            # 检查价格为空的数据
            self.cursor.execute("""
                SELECT COUNT(*) as count 
                FROM daily_prices 
                WHERE close IS NULL OR open IS NULL OR high IS NULL OR low IS NULL
            """)
            missing_prices = self.cursor.fetchone()['count']
            
            if missing_prices > 0:
                quality_issues.append({
                    "type": "missing_prices",
                    "count": missing_prices,
                    "message": f"发现 {missing_prices} 条价格数据缺失的记录"
                })
            
            check_result = {
                "status": "pass" if not quality_issues else "warning",
                "issues": quality_issues,
                "message": f"发现 {len(quality_issues)} 类数据质量问题" if quality_issues else "数据质量正常"
            }
            
            if quality_issues:
                for issue in quality_issues:
                    logger.warning(issue["message"])
            else:
                logger.info("数据质量检查通过")
                
            return check_result
            
        except Exception as e:
            logger.error(f"检查数据质量时出错: {e}")
            return {
                "status": "error",
                "message": f"检查失败: {e}"
            }
    
    def save_alert(self):
        """保存告警文件"""
        if self.report["alerts"]:
            today = datetime.now().strftime('%Y-%m-%d')
            alert_file = ALERTS_DIR / f"{today}_alert.json"
            
            # 如果文件已存在，读取并追加
            existing_alerts = []
            if alert_file.exists():
                try:
                    with open(alert_file, 'r', encoding='utf-8') as f:
                        existing_alerts = json.load(f)
                        if not isinstance(existing_alerts, list):
                            existing_alerts = [existing_alerts]
                except:
                    existing_alerts = []
            
            existing_alerts.append(self.report)
            
            with open(alert_file, 'w', encoding='utf-8') as f:
                json.dump(existing_alerts, f, ensure_ascii=False, indent=2)
            
            logger.info(f"告警已保存到: {alert_file}")
            return str(alert_file)
        return None
    
    def run_all_checks(self) -> Dict[str, Any]:
        """运行所有检查"""
        logger.info("="*50)
        logger.info("开始数据健康检查")
        logger.info("="*50)
        
        if not self.connect():
            self.report["status"] = "critical"
            return self.report
        
        try:
            # 执行各项检查
            self.report["checks"]["data_freshness"] = self.check_data_freshness()
            self.report["checks"]["stock_completeness"] = self.check_stock_completeness()
            self.report["checks"]["duplicate_data"] = self.check_duplicate_data()
            self.report["checks"]["data_quality"] = self.check_data_quality()
            
            # 确定总体状态
            statuses = [check["status"] for check in self.report["checks"].values()]
            
            if "critical" in statuses or "error" in statuses:
                self.report["status"] = "critical"
            elif "fail" in statuses:
                self.report["status"] = "fail"
            elif "warning" in statuses:
                self.report["status"] = "warning"
            else:
                self.report["status"] = "healthy"
            
            # 保存告警
            alert_file = self.save_alert()
            if alert_file:
                self.report["alert_file"] = alert_file
            
            logger.info("="*50)
            logger.info(f"检查完成，总体状态: {self.report['status']}")
            logger.info("="*50)
            
        finally:
            self.disconnect()
        
        return self.report


def check_data_health(db_path: str = None) -> Dict[str, Any]:
    """
    主函数：执行数据健康检查
    
    Args:
        db_path: 数据库路径，默认为项目data目录下的stock_data.db
        
    Returns:
        检查报告字典
    """
    checker = DataHealthChecker(db_path)
    return checker.run_all_checks()


if __name__ == "__main__":
    # 命令行执行
    import argparse
    
    parser = argparse.ArgumentParser(description='数据健康检查脚本')
    parser.add_argument('--db', help='数据库路径', default=None)
    parser.add_argument('--output', '-o', help='输出JSON报告到文件', default=None)
    parser.add_argument('--quiet', '-q', action='store_true', help='静默模式，只输出结果')
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    report = check_data_health(args.db)
    
    # 输出JSON报告
    output_json = json.dumps(report, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"报告已保存到: {args.output}")
    else:
        print(output_json)
    
    # 根据状态返回退出码
    exit_code = 0 if report["status"] == "healthy" else 1
    sys.exit(exit_code)

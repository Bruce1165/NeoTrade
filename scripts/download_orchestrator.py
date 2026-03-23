#!/usr/bin/env python3
"""
Download Orchestrator - 数据下载编排器

Master script for daily data pipeline:
1. Check trading calendar (skip weekends/holidays)
2. Download today's data via iFind Realtime
3. Verify data integrity
4. Auto-backfill gaps via Baostock
5. Report results

Exit codes:
    0 - Success (all operations completed)
    1 - Configuration/data error
    2 - Download failed
    3 - Verification failed
    4 - Backfill failed
    5 - Not a trading day (skipped)

Usage:
    python3 scripts/download_orchestrator.py
    python3 scripts/download_orchestrator.py --full-verify  # Full integrity check
    python3 scripts/download_orchestrator.py --no-backfill # Skip backfill
"""

import os
import sys
import sqlite3
import json
import argparse
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

# Setup paths
WORKSPACE = Path('/Users/mac/.openclaw/workspace-neo')
SCRIPTS_DIR = WORKSPACE / 'scripts'
DATA_DIR = WORKSPACE / 'data'
LOGS_DIR = WORKSPACE / 'logs'

# Ensure logs directory exists
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Logging setup
LOG_FILE = LOGS_DIR / f"orchestrator_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class OrchestratorResult:
    """执行结果"""
    success: bool
    exit_code: int
    stage: str
    message: str
    details: Dict
    
    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'exit_code': self.exit_code,
            'stage': self.stage,
            'message': self.message,
            'details': self.details,
            'timestamp': datetime.now().isoformat()
        }


class DownloadOrchestrator:
    """数据下载编排器"""
    
    def __init__(self, db_path: str = None, full_verify: bool = False, 
                 no_backfill: bool = False, dry_run: bool = False):
        self.db_path = db_path or str(DATA_DIR / 'stock_data.db')
        self.full_verify = full_verify
        self.no_backfill = no_backfill
        self.dry_run = dry_run
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.report_path: Optional[Path] = None
        
    def is_trading_day(self, date_str: str = None) -> bool:
        """检查是否为交易日"""
        date_str = date_str or self.today
        
        # Try to use trading_calendar module
        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            from trading_calendar import TradingCalendar
            calendar = TradingCalendar(self.db_path)
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return calendar.is_trading_day(dt)
        except Exception as e:
            logger.warning(f"无法加载交易日历: {e}, 使用简单判断")
            # Fallback: skip weekends
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.weekday() < 5  # Monday=0, Friday=4
    
    def run_script(self, script_name: str, args: List[str] = None, 
                   timeout: int = 1800) -> Tuple[bool, str, int]:
        """运行脚本并返回结果"""
        script_path = SCRIPTS_DIR / script_name
        
        if not script_path.exists():
            return False, f"脚本不存在: {script_path}", 1
        
        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)
        
        logger.info(f"▶️  运行: {' '.join(cmd)}")
        
        if self.dry_run:
            logger.info("[DRY RUN] 跳过实际执行")
            return True, "Dry run - skipped", 0
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(WORKSPACE)
            )
            
            output = result.stdout + "\n" + result.stderr
            success = result.returncode == 0
            
            if success:
                logger.info(f"✅ {script_name} 成功")
            else:
                logger.error(f"❌ {script_name} 失败 (exit {result.returncode})")
                logger.error(f"输出: {output[:500]}")
            
            return success, output, result.returncode
            
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️  {script_name} 超时")
            return False, "Timeout", 1
        except Exception as e:
            logger.error(f"💥 {script_name} 异常: {e}")
            return False, str(e), 1
    
    def step1_download_today(self) -> OrchestratorResult:
        """步骤1: 下载今日数据"""
        logger.info("\n" + "="*60)
        logger.info("📥 步骤1: 下载今日数据 (iFind Realtime)")
        logger.info("="*60)
        
        success, output, code = self.run_script(
            'download_today_ifind.py',
            timeout=600  # 10 min for download
        )
        
        # Parse download count from output
        downloaded = 0
        if success:
            for line in output.split('\n'):
                if 'Inserted/Updated' in line or 'Downloaded' in line:
                    try:
                        downloaded = int(''.join(filter(str.isdigit, line.split()[-2] if len(line.split()) > 1 else line)))
                    except:
                        pass
                    break
        
        if not success:
            return OrchestratorResult(
                success=False,
                exit_code=2,
                stage='download',
                message='数据下载失败',
                details={'output': output[:1000], 'exit_code': code}
            )
        
        return OrchestratorResult(
            success=True,
            exit_code=0,
            stage='download',
            message=f'成功下载 {downloaded} 只股票数据',
            details={'downloaded': downloaded, 'date': self.today}
        )
    
    def step2_verify_integrity(self) -> OrchestratorResult:
        """步骤2: 验证数据完整性"""
        logger.info("\n" + "="*60)
        logger.info("🔍 步骤2: 验证数据完整性")
        logger.info("="*60)
        
        # Determine verification mode
        if self.full_verify:
            args = ['--full']
            mode = 'full'
        else:
            args = ['--sample', '500']  # Sample 500 stocks for speed
            mode = 'sample'
        
        success, output, code = self.run_script(
            'verify_data_integrity.py',
            args=args,
            timeout=300  # 5 min for verification
        )
        
        if not success:
            return OrchestratorResult(
                success=False,
                exit_code=3,
                stage='verify',
                message='完整性检查失败',
                details={'output': output[:1000], 'exit_code': code}
            )
        
        # Parse report path from output
        report_path = None
        for line in output.split('\n'):
            if '报告已保存' in line or 'report saved' in line.lower():
                # Extract path
                parts = line.split(':')
                if len(parts) > 1:
                    report_path = parts[-1].strip()
                    break
        
        # Also check the logs directory for latest report
        if not report_path:
            reports = sorted(LOGS_DIR.glob('integrity_report_*.json'), 
                           key=lambda x: x.stat().st_mtime, reverse=True)
            if reports:
                report_path = str(reports[0])
        
        self.report_path = Path(report_path) if report_path else None
        
        # Parse statistics
        stats = self._parse_integrity_output(output)
        
        return OrchestratorResult(
            success=True,
            exit_code=0,
            stage='verify',
            message=f'完整性检查完成: {stats.get("stocks_complete", 0)} 只完整, {stats.get("stocks_with_gaps", 0)} 只有缺口',
            details={
                'mode': mode,
                'report_path': str(self.report_path) if self.report_path else None,
                'stats': stats
            }
        )
    
    def _parse_integrity_output(self, output: str) -> Dict:
        """解析完整性检查输出"""
        stats = {}
        for line in output.split('\n'):
            if '数据完整:' in line:
                stats['stocks_complete'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
            elif '存在缺口:' in line:
                stats['stocks_with_gaps'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
            elif '总计缺失记录:' in line:
                stats['total_missing'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
        return stats
    
    def step3_backfill_gaps(self, verify_result: Dict) -> OrchestratorResult:
        """步骤3: 回填数据缺口"""
        logger.info("\n" + "="*60)
        logger.info("📦 步骤3: 回填数据缺口 (Baostock)")
        logger.info("="*60)
        
        if self.no_backfill:
            return OrchestratorResult(
                success=True,
                exit_code=0,
                stage='backfill',
                message='跳过回填 (--no-backfill)',
                details={'skipped': True}
            )
        
        stats = verify_result.get('stats', {})
        stocks_with_gaps = stats.get('stocks_with_gaps', 0)
        
        if stocks_with_gaps == 0:
            return OrchestratorResult(
                success=True,
                exit_code=0,
                stage='backfill',
                message='无数据缺口，跳过回填',
                details={'skipped': True, 'reason': 'no_gaps'}
            )
        
        if not self.report_path or not self.report_path.exists():
            return OrchestratorResult(
                success=False,
                exit_code=4,
                stage='backfill',
                message='无法找到完整性报告',
                details={'report_path': str(self.report_path)}
            )
        
        # Run backfill
        args = ['--report', str(self.report_path)]
        
        # For sample mode, limit backfill to avoid long runs
        if not self.full_verify:
            args.extend(['--max-stocks', '50'])
        
        success, output, code = self.run_script(
            'backfill_baostock.py',
            args=args,
            timeout=1800  # 30 min for backfill
        )
        
        # Parse backfill stats
        backfill_stats = self._parse_backfill_output(output)
        
        if not success:
            return OrchestratorResult(
                success=False,
                exit_code=4,
                stage='backfill',
                message='数据回填失败',
                details={'output': output[:1000], 'exit_code': code, 'stats': backfill_stats}
            )
        
        return OrchestratorResult(
            success=True,
            exit_code=0,
            stage='backfill',
            message=f'回填完成: {backfill_stats.get("records_inserted", 0)} 条插入, {backfill_stats.get("records_skipped", 0)} 条更新',
            details={'stats': backfill_stats}
        )
    
    def _parse_backfill_output(self, output: str) -> Dict:
        """解析回填输出"""
        stats = {}
        for line in output.split('\n'):
            if '处理股票:' in line:
                stats['stocks_processed'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
            elif '成功回填:' in line:
                stats['stocks_success'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
            elif '插入记录:' in line:
                stats['records_inserted'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
            elif '更新记录:' in line:
                stats['records_skipped'] = int(''.join(filter(str.isdigit, line.split(':')[-1])))
        return stats
    
    def step4_run_screeners(self) -> OrchestratorResult:
        """步骤4: 运行所有筛选器"""
        logger.info("\n" + "="*60)
        logger.info("🎯 步骤4: 运行所有筛选器")
        logger.info("="*60)
        
        if self.dry_run:
            return OrchestratorResult(
                success=True,
                exit_code=0,
                stage='screeners',
                message='跳过筛选器运行 (dry-run)',
                details={'skipped': True}
            )
        
        # Import and run all screeners
        try:
            sys.path.insert(0, str(SCRIPTS_DIR))
            from run_all_screeners import run_all_screeners
            
            report = run_all_screeners(date_str=self.today, dry_run=False)
            
            summary = report.get('summary', {})
            total = summary.get('total', 0)
            success = summary.get('success', 0)
            failed = summary.get('failed', 0)
            total_picks = summary.get('total_picks', 0)
            
            if failed == 0:
                return OrchestratorResult(
                    success=True,
                    exit_code=0,
                    stage='screeners',
                    message=f'所有筛选器运行完成: {success}/{total} 成功, 共 {total_picks} 个pick',
                    details={
                        'total': total,
                        'success': success,
                        'failed': failed,
                        'total_picks': total_picks,
                        'results': report.get('results', [])
                    }
                )
            else:
                # Partial failure is still ok - some screeners may fail but others work
                return OrchestratorResult(
                    success=True,  # Still consider overall success
                    exit_code=0,
                    stage='screeners',
                    message=f'筛选器运行完成: {success}/{total} 成功, {failed} 失败, 共 {total_picks} 个pick',
                    details={
                        'total': total,
                        'success': success,
                        'failed': failed,
                        'total_picks': total_picks,
                        'results': report.get('results', [])
                    }
                )
                
        except Exception as e:
            logger.error(f"❌ 运行筛选器失败: {e}")
            return OrchestratorResult(
                success=False,
                exit_code=6,
                stage='screeners',
                message=f'运行筛选器失败: {e}',
                details={'error': str(e)}
            )
    
    def run(self) -> OrchestratorResult:
        """运行完整编排流程"""
        start_time = datetime.now()
        logger.info("\n" + "🚀"*30)
        logger.info("🚀 数据下载编排器启动")
        logger.info(f"🚀 日期: {self.today}")
        logger.info(f"🚀 模式: {'完整验证' if self.full_verify else '抽样验证'}")
        logger.info("🚀"*30)
        
        # Check if trading day
        if not self.is_trading_day():
            msg = f"{self.today} 不是交易日，跳过执行"
            logger.info(msg)
            return OrchestratorResult(
                success=True,
                exit_code=5,
                stage='skip',
                message=msg,
                details={'reason': 'not_trading_day'}
            )
        
        # Step 1: Download
        result = self.step1_download_today()
        if not result.success:
            self._save_report(result, start_time)
            return result
        
        download_result = result
        
        # Step 2: Verify
        result = self.step2_verify_integrity()
        if not result.success:
            self._save_report(result, start_time, download_result=download_result)
            return result
        
        verify_result = result
        
        # Step 3: Backfill (if needed)
        result = self.step3_backfill_gaps(verify_result.details)
        if not result.success:
            self._save_report(result, start_time, 
                            download_result=download_result,
                            verify_result=verify_result)
            return result
        
        backfill_result = result
        
        # Step 4: Run all screeners
        result = self.step4_run_screeners()
        if not result.success:
            # Screener failure is not fatal - data pipeline is still complete
            logger.warning(f"⚠️ 筛选器运行失败，但数据流程已完成: {result.message}")
        
        screeners_result = result
        
        # Compile final result
        final_result = OrchestratorResult(
            success=download_result.success and verify_result.success,
            exit_code=0,
            stage='complete',
            message='数据下载与筛选流程完成',
            details={
                'download': download_result.details,
                'verify': verify_result.details,
                'backfill': backfill_result.details,
                'screeners': screeners_result.details,
                'duration_seconds': (datetime.now() - start_time).total_seconds()
            }
        )
        
        self._save_report(final_result, start_time, download_result=download_result)
        return final_result
    
    def _save_report(self, result: OrchestratorResult, start_time: datetime, 
                     download_result: OrchestratorResult = None,
                     verify_result: OrchestratorResult = None):
        """保存执行报告"""
        report_file = LOGS_DIR / f"orchestrator_report_{self.today}.json"
        
        report = {
            'date': self.today,
            'start_time': start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': (datetime.now() - start_time).total_seconds(),
            'result': result.to_dict()
        }
        
        if download_result:
            report['download_stage'] = download_result.to_dict()
        if verify_result:
            report['verify_stage'] = verify_result.to_dict()
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"📄 执行报告已保存: {report_file}")


def print_summary(result: OrchestratorResult):
    """打印执行摘要"""
    print("\n" + "="*60)
    print("📊 数据下载编排器 - 执行摘要")
    print("="*60)
    
    if result.exit_code == 5:
        print(f"⏭️  {result.message}")
        print("="*60)
        return
    
    status = "✅ 成功" if result.success else "❌ 失败"
    print(f"状态: {status}")
    print(f"消息: {result.message}")
    print("-"*60)
    
    details = result.details
    
    # Download stage
    if 'download' in details:
        d = details['download']
        print(f"📥 下载: {d.get('downloaded', 0)} 只股票 ({d.get('date', 'N/A')})")
    
    # Verify stage
    if 'verify' in details:
        v = details['verify']
        stats = v.get('stats', {})
        print(f"🔍 验证: {stats.get('stocks_complete', 0)} 只完整 / {stats.get('stocks_with_gaps', 0)} 只有缺口")
        if v.get('report_path'):
            print(f"   报告: {v['report_path']}")
    
    # Backfill stage
    if 'backfill' in details:
        b = details['backfill']
        if b.get('skipped'):
            print(f"📦 回填: 跳过 ({b.get('reason', 'no_gaps')})")
        else:
            stats = b.get('stats', {})
            print(f"📦 回填: {stats.get('records_inserted', 0)} 条插入, {stats.get('records_skipped', 0)} 条更新")
    
    # Screeners stage
    if 'screeners' in details:
        s = details['screeners']
        if s.get('skipped'):
            print(f"🎯 筛选器: 跳过 (dry-run)")
        else:
            print(f"🎯 筛选器: {s.get('success', 0)}/{s.get('total', 0)} 成功, "
                  f"{s.get('failed', 0)} 失败, 共 {s.get('total_picks', 0)} 个pick")
    
    # Duration
    if 'duration_seconds' in details:
        mins = details['duration_seconds'] / 60
        print(f"⏱️  耗时: {mins:.1f} 分钟")
    
    print("="*60)
    print(f"📄 详细日志: {LOG_FILE}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='数据下载编排器 - 自动化数据管道',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python3 scripts/download_orchestrator.py                    # 标准运行（抽样验证）
    python3 scripts/download_orchestrator.py --full-verify      # 完整验证（较慢）
    python3 scripts/download_orchestrator.py --no-backfill      # 跳过回填
    python3 scripts/download_orchestrator.py --dry-run          # 测试模式（不执行）
        """
    )
    parser.add_argument('--full-verify', action='store_true', 
                       help='全量验证所有股票（默认抽样500只）')
    parser.add_argument('--no-backfill', action='store_true',
                       help='跳过Baostock回填')
    parser.add_argument('--dry-run', action='store_true',
                       help='测试模式，只显示会执行的操作')
    parser.add_argument('--force', action='store_true',
                       help='强制运行（跳过交易日检查）')
    
    args = parser.parse_args()
    
    # Create orchestrator
    orchestrator = DownloadOrchestrator(
        full_verify=args.full_verify,
        no_backfill=args.no_backfill,
        dry_run=args.dry_run
    )
    
    # Override trading day check if forced
    if args.force:
        orchestrator.is_trading_day = lambda x=None: True
    
    # Run
    result = orchestrator.run()
    
    # Print summary
    print_summary(result)
    
    # Exit with appropriate code
    sys.exit(result.exit_code)


if __name__ == '__main__':
    main()

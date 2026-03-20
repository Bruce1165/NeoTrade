#!/usr/bin/env python3
"""
Ngrok & Flask 服务监控脚本
==========================
监控 ngrok 隧道和 Flask 服务状态，自动重启故障服务

错误代码:
- ERR_NGROK_3200: ngrok 离线/隧道过期
- ERR_NGROK_334: 会话冲突
- ERR_NGROK_502: 后端服务不可达

作者: SRE Agent
版本: 1.0.0
"""

import os
import sys
import time
import json
import signal
import logging
import subprocess
import requests
import psutil
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

# ============ 配置 ============
class Config:
    """监控配置"""
    # 服务配置
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5004))  # Flask 端口
    NGROK_API_PORT = int(os.getenv('NGROK_API_PORT', 4040))  # ngrok API 端口
    NGROK_DOMAIN = os.getenv('NGROK_DOMAIN', 'chariest-nancy-nonincidentally.ngrok-free.dev')
    
    # 路径配置
    WORKSPACE = Path(os.getenv('WORKSPACE', '/Users/mac/.openclaw/workspace-neo'))
    LOG_DIR = WORKSPACE / 'logs'
    ALERT_DIR = WORKSPACE / 'alerts'
    DASHBOARD_DIR = WORKSPACE / 'dashboard'
    
    # 监控配置
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 60))  # 检查间隔(秒)
    FLASK_STARTUP_WAIT = int(os.getenv('FLASK_STARTUP_WAIT', 5))  # Flask启动等待时间
    NGROK_STARTUP_WAIT = int(os.getenv('NGROK_STARTUP_WAIT', 3))  # ngrok启动等待时间
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))  # 最大重试次数
    
    # Flask 配置
    FLASK_APP = 'app.py'
    FLASK_HOST = '127.0.0.1'
    
    # ngrok 配置
    NGROK_CMD = ['ngrok', 'http', str(FLASK_PORT), '--domain', NGROK_DOMAIN]
    
    @classmethod
    def ensure_dirs(cls):
        """确保日志目录存在"""
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.ALERT_DIR.mkdir(parents=True, exist_ok=True)

# ============ 数据类 ============
@dataclass
class AlertEvent:
    """告警事件"""
    timestamp: str
    level: str  # ERROR, WARNING, INFO
    error_code: Optional[str]
    message: str
    service: str  # ngrok, flask, both
    action_taken: str
    resolved: bool = False
    resolved_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class ServiceStatus:
    """服务状态"""
    timestamp: str
    ngrok_running: bool
    ngrok_tunnel_active: bool
    ngrok_public_url: Optional[str]
    flask_running: bool
    flask_port_open: bool
    flask_health_ok: bool
    errors: List[str]

# ============ 日志配置 ============
def setup_logging() -> logging.Logger:
    """配置日志记录"""
    Config.ensure_dirs()
    
    logger = logging.getLogger('ngrok_monitor')
    logger.setLevel(logging.DEBUG)
    
    # 文件处理器
    log_file = Config.LOG_DIR / 'ngrok_monitor.log'
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ============ 告警管理 ============
class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.today = date.today().isoformat()
        self.alert_file = Config.ALERT_DIR / f'ngrok_{self.today}.json'
        self.alerts: List[Dict[str, Any]] = self._load_alerts()
    
    def _load_alerts(self) -> List[Dict[str, Any]]:
        """加载今日告警"""
        if self.alert_file.exists():
            try:
                with open(self.alert_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载告警文件失败: {e}")
        return []
    
    def _save_alerts(self):
        """保存告警"""
        try:
            with open(self.alert_file, 'w', encoding='utf-8') as f:
                json.dump(self.alerts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存告警文件失败: {e}")
    
    def add_alert(self, event: AlertEvent):
        """添加告警"""
        self.alerts.append(event.to_dict())
        self._save_alerts()
        
        # 同时记录到日志
        log_msg = f"[{event.level}] [{event.service}] {event.message}"
        if event.error_code:
            log_msg += f" (Error: {event.error_code})"
        log_msg += f" - Action: {event.action_taken}"
        
        if event.level == 'ERROR':
            logger.error(log_msg)
        elif event.level == 'WARNING':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
    
    def get_unresolved(self) -> List[Dict[str, Any]]:
        """获取未解决的告警"""
        return [a for a in self.alerts if not a.get('resolved', False)]

# ============ 服务检查 ============
class ServiceChecker:
    """服务检查器"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
    
    def is_port_open(self, port: int, host: str = '127.0.0.1') -> bool:
        """检查端口是否开放"""
        import socket
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except:
            return False
    
    def is_process_running(self, name: str) -> bool:
        """检查进程是否运行"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if name in proc.info['name'] or name in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def get_ngrok_pid(self) -> Optional[int]:
        """获取 ngrok 进程 PID"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'ngrok' in proc.info['name'] and 'http' in cmdline:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def get_flask_pid(self) -> Optional[int]:
        """获取 Flask 进程 PID"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline)
                # 匹配 python app.py 或 flask run
                if 'app.py' in cmdline_str or ('flask' in cmdline_str and 'run' in cmdline_str):
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def check_ngrok_api(self) -> Dict[str, Any]:
        """检查 ngrok API 状态"""
        result = {
            'success': False,
            'tunnels': [],
            'public_url': None,
            'error': None
        }
        
        try:
            response = requests.get(
                f'http://127.0.0.1:{Config.NGROK_API_PORT}/api/tunnels',
                timeout=5
            )
            data = response.json()
            
            result['success'] = True
            result['tunnels'] = data.get('tunnels', [])
            
            # 获取公网 URL
            for tunnel in result['tunnels']:
                if tunnel.get('public_url', '').startswith('https://'):
                    result['public_url'] = tunnel['public_url']
                    break
                    
        except requests.exceptions.ConnectionError:
            result['error'] = 'ERR_NGROK_3200'  # ngrok API 不可达（离线）
        except requests.exceptions.Timeout:
            result['error'] = 'ERR_NGROK_334'  # 会话超时/冲突
        except Exception as e:
            result['error'] = f'UNKNOWN: {str(e)}'
        
        return result
    
    def check_flask_health(self) -> Dict[str, Any]:
        """检查 Flask 健康状态"""
        result = {
            'success': False,
            'response_time_ms': 0,
            'error': None
        }
        
        if not self.is_port_open(Config.FLASK_PORT):
            result['error'] = f'Port {Config.FLASK_PORT} not open'
            return result
        
        try:
            start = time.time()
            response = requests.get(
                f'http://{Config.FLASK_HOST}:{Config.FLASK_PORT}/api/health',
                timeout=5
            )
            result['response_time_ms'] = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                result['success'] = True
            else:
                result['error'] = f'HTTP {response.status_code}'
                
        except requests.exceptions.ConnectionError:
            result['error'] = 'Connection refused'
        except requests.exceptions.Timeout:
            result['error'] = 'Request timeout'
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def get_full_status(self) -> ServiceStatus:
        """获取完整服务状态"""
        ngrok_api = self.check_ngrok_api()
        flask_health = self.check_flask_health()
        
        errors = []
        if ngrok_api.get('error'):
            errors.append(f"ngrok: {ngrok_api['error']}")
        if flask_health.get('error'):
            errors.append(f"flask: {flask_health['error']}")
        
        return ServiceStatus(
            timestamp=datetime.now().isoformat(),
            ngrok_running=self.is_process_running('ngrok'),
            ngrok_tunnel_active=ngrok_api['success'] and len(ngrok_api['tunnels']) > 0,
            ngrok_public_url=ngrok_api.get('public_url'),
            flask_running=self.is_process_running('python') and self.is_port_open(Config.FLASK_PORT),
            flask_port_open=self.is_port_open(Config.FLASK_PORT),
            flask_health_ok=flask_health['success'],
            errors=errors
        )

# ============ 服务管理 ============
class ServiceManager:
    """服务管理器"""
    
    def __init__(self):
        self.checker = ServiceChecker()
        self.alert_manager = AlertManager()
    
    def kill_process_by_port(self, port: int) -> bool:
        """通过端口终止进程"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        logger.info(f"终止占用端口 {port} 的进程: {proc.name()} (PID: {conn.pid})")
                        proc.terminate()
                        proc.wait(timeout=5)
                        return True
                    except psutil.NoSuchProcess:
                        pass
        except Exception as e:
            logger.error(f"终止端口 {port} 进程失败: {e}")
        return False
    
    def kill_ngrok(self) -> bool:
        """终止 ngrok 进程"""
        pid = self.checker.get_ngrok_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                logger.info(f"终止 ngrok 进程 (PID: {pid})")
                proc.terminate()
                proc.wait(timeout=5)
                return True
            except Exception as e:
                logger.error(f"终止 ngrok 失败: {e}")
                try:
                    proc.kill()
                except:
                    pass
        return False
    
    def kill_flask(self) -> bool:
        """终止 Flask 进程"""
        pid = self.checker.get_flask_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                logger.info(f"终止 Flask 进程 (PID: {pid})")
                proc.terminate()
                proc.wait(timeout=5)
                return True
            except Exception as e:
                logger.error(f"终止 Flask 失败: {e}")
                try:
                    proc.kill()
                except:
                    pass
        return False
    
    def start_flask(self) -> bool:
        """启动 Flask 服务"""
        try:
            logger.info(f"启动 Flask 服务 (端口: {Config.FLASK_PORT})...")
            
            # 切换到 dashboard 目录
            os.chdir(Config.DASHBOARD_DIR)
            
            # 设置环境变量
            env = os.environ.copy()
            env['FLASK_APP'] = Config.FLASK_APP
            env['FLASK_RUN_PORT'] = str(Config.FLASK_PORT)
            env['FLASK_RUN_HOST'] = Config.FLASK_HOST
            
            # 启动 Flask
            subprocess.Popen(
                [sys.executable, Config.FLASK_APP],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=Config.DASHBOARD_DIR
            )
            
            # 等待启动
            time.sleep(Config.FLASK_STARTUP_WAIT)
            
            # 验证启动
            if self.checker.is_port_open(Config.FLASK_PORT):
                logger.info("✅ Flask 启动成功")
                return True
            else:
                logger.error("❌ Flask 启动失败 - 端口未开放")
                return False
                
        except Exception as e:
            logger.error(f"启动 Flask 失败: {e}")
            return False
    
    def start_ngrok(self) -> bool:
        """启动 ngrok"""
        try:
            logger.info(f"启动 ngrok (指向端口: {Config.FLASK_PORT})...")
            
            subprocess.Popen(
                Config.NGROK_CMD,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # 等待启动
            time.sleep(Config.NGROK_STARTUP_WAIT)
            
            # 验证启动
            ngrok_api = self.checker.check_ngrok_api()
            if ngrok_api['success']:
                logger.info(f"✅ ngrok 启动成功 - URL: {ngrok_api.get('public_url', 'unknown')}")
                return True
            else:
                logger.error(f"❌ ngrok 启动失败 - {ngrok_api.get('error', 'unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"启动 ngrok 失败: {e}")
            return False
    
    def restart_flask(self) -> bool:
        """重启 Flask"""
        self.kill_flask()
        time.sleep(1)
        
        # 确保端口释放
        if self.checker.is_port_open(Config.FLASK_PORT):
            self.kill_process_by_port(Config.FLASK_PORT)
            time.sleep(1)
        
        return self.start_flask()
    
    def restart_ngrok(self) -> bool:
        """重启 ngrok"""
        self.kill_ngrok()
        time.sleep(2)
        return self.start_ngrok()
    
    def restart_all(self) -> bool:
        """重启所有服务"""
        logger.info("🔄 重启所有服务...")
        
        # 先停 ngrok
        self.kill_ngrok()
        time.sleep(1)
        
        # 重启 Flask
        if not self.restart_flask():
            return False
        
        time.sleep(2)
        
        # 启动 ngrok
        if not self.start_ngrok():
            return False
        
        logger.info("✅ 所有服务重启完成")
        return True

# ============ 主监控循环 ============
class NgrokMonitor:
    """Ngrok 监控器"""
    
    def __init__(self):
        self.checker = ServiceChecker()
        self.manager = ServiceManager()
        self.alert_manager = AlertManager()
        self.running = False
        self.retry_count = 0
        
        # 信号处理
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        logger.info(f"收到信号 {signum}, 正在停止监控...")
        self.running = False
    
    def check_and_restart(self) -> bool:
        """
        检查服务状态并自动重启
        返回: True = 一切正常, False = 需要重启
        """
        status = self.checker.get_full_status()
        
        # 记录状态日志（每10次检查记录一次正常状态）
        if not status.errors or self.retry_count == 0:
            logger.debug(f"状态检查: ngrok={status.ngrok_running}, flask={status.flask_running}, "
                        f"health={status.flask_health_ok}, tunnels={status.ngrok_tunnel_active}")
        
        issues = []
        error_code = None
        
        # 1. 检查 Flask
        if not status.flask_running or not status.flask_health_ok:
            if not status.flask_port_open:
                issues.append(f"Flask 端口 {Config.FLASK_PORT} 未开放")
            elif not status.flask_health_ok:
                issues.append("Flask 健康检查失败")
            else:
                issues.append("Flask 进程未运行")
        
        # 2. 检查 ngrok
        if status.errors:
            for error in status.errors:
                if 'ERR_NGROK_3200' in error:
                    error_code = 'ERR_NGROK_3200'
                    issues.append("ngrok 离线 (ERR_NGROK_3200)")
                elif 'ERR_NGROK_334' in error:
                    error_code = 'ERR_NGROK_334'
                    issues.append("ngrok 会话冲突 (ERR_NGROK_334)")
                elif 'ngrok:' in error:
                    issues.append(f"ngrok 错误: {error}")
        
        if not status.ngrok_running:
            issues.append("ngrok 进程未运行")
        elif not status.ngrok_tunnel_active:
            issues.append("ngrok 隧道未激活")
        
        # 3. 检查 URL 是否匹配
        if status.ngrok_public_url and Config.NGROK_DOMAIN not in status.ngrok_public_url:
            logger.warning(f"ngrok URL 不匹配: {status.ngrok_public_url} != {Config.NGROK_DOMAIN}")
        
        # 如果有问题，执行恢复
        if issues:
            issue_msg = "; ".join(issues)
            logger.warning(f"检测到问题: {issue_msg}")
            
            # 决定恢复策略
            if not status.flask_health_ok:
                # Flask 问题，重启 Flask
                action = "重启 Flask"
                self.alert_manager.add_alert(AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    level='ERROR',
                    error_code=error_code,
                    message=issue_msg,
                    service='flask',
                    action_taken=action
                ))
                
                success = self.manager.restart_flask()
                if success:
                    time.sleep(2)
                    # 如果 ngrok 也停了，重新启动
                    ngrok_status = self.checker.check_ngrok_api()
                    if not ngrok_status['success']:
                        self.manager.start_ngrok()
                
            elif error_code in ['ERR_NGROK_3200', 'ERR_NGROK_334'] or not status.ngrok_running:
                # ngrok 问题，重启 ngrok
                action = "重启 ngrok"
                self.alert_manager.add_alert(AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    level='ERROR',
                    error_code=error_code,
                    message=issue_msg,
                    service='ngrok',
                    action_taken=action
                ))
                
                success = self.manager.restart_ngrok()
                
            else:
                # 未知问题，全量重启
                action = "重启所有服务"
                self.alert_manager.add_alert(AlertEvent(
                    timestamp=datetime.now().isoformat(),
                    level='ERROR',
                    error_code=error_code,
                    message=issue_msg,
                    service='both',
                    action_taken=action
                ))
                
                success = self.manager.restart_all()
            
            if success:
                logger.info(f"✅ {action} 成功")
                self.retry_count = 0
                return True
            else:
                logger.error(f"❌ {action} 失败")
                self.retry_count += 1
                return False
        
        # 一切正常
        self.retry_count = 0
        return True
    
    def run(self):
        """运行监控循环"""
        logger.info("=" * 60)
        logger.info("🚀 Ngrok & Flask 监控服务启动")
        logger.info("=" * 60)
        logger.info(f"配置: Flask端口={Config.FLASK_PORT}, 检查间隔={Config.CHECK_INTERVAL}s")
        logger.info(f"日志: {Config.LOG_DIR / 'ngrok_monitor.log'}")
        logger.info(f"告警: {Config.ALERT_DIR}/ngrok_YYYY-MM-DD.json")
        logger.info("=" * 60)
        
        self.running = True
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                
                # 执行检查
                healthy = self.check_and_restart()
                
                if not healthy and self.retry_count >= Config.MAX_RETRIES:
                    logger.error(f"❌ 连续 {Config.MAX_RETRIES} 次恢复失败，等待手动干预")
                    self.alert_manager.add_alert(AlertEvent(
                        timestamp=datetime.now().isoformat(),
                        level='ERROR',
                        error_code=None,
                        message=f"连续 {Config.MAX_RETRIES} 次自动恢复失败",
                        service='both',
                        action_taken='等待手动干预'
                    ))
                    self.retry_count = 0  # 重置计数，继续尝试
                
                # 定期输出心跳（每30分钟）
                if check_count % 30 == 0:
                    status = self.checker.get_full_status()
                    logger.info(f"💓 监控心跳 #{check_count} - 状态: {'✅ 健康' if not status.errors else '⚠️ 有问题'}")
                
                # 等待下一次检查
                for _ in range(Config.CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.exception(f"监控循环异常: {e}")
                time.sleep(5)
        
        logger.info("👋 监控服务已停止")

# ============ 命令行接口 ============
def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ngrok & Flask 监控服务')
    parser.add_argument('--status', action='store_true', help='查看当前状态')
    parser.add_argument('--restart', action='store_true', help='重启所有服务')
    parser.add_argument('--once', action='store_true', help='执行一次检查并退出')
    parser.add_argument('--daemon', '-d', action='store_true', help='后台运行')
    
    args = parser.parse_args()
    
    if args.status:
        # 显示状态
        checker = ServiceChecker()
        status = checker.get_full_status()
        
        print("\n📊 服务状态")
        print("=" * 40)
        print(f"时间: {status.timestamp}")
        print(f"\n🌐 ngrok:")
        print(f"   进程运行: {'✅' if status.ngrok_running else '❌'}")
        print(f"   隧道激活: {'✅' if status.ngrok_tunnel_active else '❌'}")
        print(f"   公网地址: {status.ngrok_public_url or 'N/A'}")
        print(f"\n🐍 Flask:")
        print(f"   进程运行: {'✅' if status.flask_running else '❌'}")
        print(f"   端口开放: {'✅' if status.flask_port_open else '❌'}")
        print(f"   健康检查: {'✅' if status.flask_health_ok else '❌'}")
        print(f"\n⚠️  问题: {', '.join(status.errors) if status.errors else '无'}")
        print("=" * 40)
        
    elif args.restart:
        # 重启服务
        manager = ServiceManager()
        success = manager.restart_all()
        sys.exit(0 if success else 1)
        
    elif args.once:
        # 执行一次检查
        monitor = NgrokMonitor()
        healthy = monitor.check_and_restart()
        sys.exit(0 if healthy else 1)
        
    else:
        # 启动监控
        monitor = NgrokMonitor()
        monitor.run()

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Ngrok High Availability Monitor
==============================
Monitors ngrok tunnel and Flask service, auto-restarts on failure.
Detects ERR_NGROK_3200/334 errors and recovers automatically.

Author: SRE Agent
Version: 2.0.0
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

# ============ Configuration ============
class Config:
    """Monitor configuration"""
    # Service settings
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5003))  # Flask port
    NGROK_API_PORT = int(os.getenv('NGROK_API_PORT', 4040))  # ngrok API port
    NGROK_DOMAIN = os.getenv('NGROK_DOMAIN', 'chariest-nancy-nonincidentally.ngrok-free.dev')
    DASHBOARD_PASSWORD = os.getenv('DASHBOARD_PASSWORD', 'neiltrade123')
    
    # Paths
    WORKSPACE = Path(os.getenv('WORKSPACE', '/Users/mac/.openclaw/workspace-neo'))
    LOG_DIR = WORKSPACE / 'logs'
    ALERT_DIR = WORKSPACE / 'alerts'
    DASHBOARD_DIR = WORKSPACE / 'dashboard'
    
    # Monitoring settings
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 60))  # Check interval (seconds)
    FLASK_STARTUP_WAIT = int(os.getenv('FLASK_STARTUP_WAIT', 8))  # Flask startup wait
    NGROK_STARTUP_WAIT = int(os.getenv('NGROK_STARTUP_WAIT', 5))  # ngrok startup wait
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))  # Max retry attempts
    
    # Flask settings
    FLASK_APP = 'app.py'
    FLASK_HOST = '127.0.0.1'
    
    # ngrok settings
    NGROK_CMD = ['ngrok', 'http', str(FLASK_PORT), '--domain', NGROK_DOMAIN]
    
    @classmethod
    def ensure_dirs(cls):
        """Ensure log directories exist"""
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)
        cls.ALERT_DIR.mkdir(parents=True, exist_ok=True)

# ============ Data Classes ============
@dataclass
class AlertEvent:
    """Alert event"""
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
    """Service status"""
    timestamp: str
    ngrok_running: bool
    ngrok_tunnel_active: bool
    ngrok_public_url: Optional[str]
    flask_running: bool
    flask_port_open: bool
    flask_health_ok: bool
    errors: List[str]

# ============ Logging Setup ============
def setup_logging() -> logging.Logger:
    """Configure logging"""
    Config.ensure_dirs()
    
    logger = logging.getLogger('ngrok_monitor')
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates on reload
    logger.handlers.clear()
    
    # File handler
    log_file = Config.LOG_DIR / 'ngrok_monitor.log'
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formatter
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

# ============ Alert Manager ============
class AlertManager:
    """Alert manager"""
    
    def __init__(self):
        self.today = date.today().isoformat()
        self.alert_file = Config.ALERT_DIR / f'ngrok_{self.today}.json'
        self.alerts: List[Dict[str, Any]] = self._load_alerts()
    
    def _load_alerts(self) -> List[Dict[str, Any]]:
        """Load today's alerts"""
        if self.alert_file.exists():
            try:
                with open(self.alert_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load alert file: {e}")
        return []
    
    def _save_alerts(self):
        """Save alerts"""
        try:
            with open(self.alert_file, 'w', encoding='utf-8') as f:
                json.dump(self.alerts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save alert file: {e}")
    
    def add_alert(self, event: AlertEvent):
        """Add alert"""
        self.alerts.append(event.to_dict())
        self._save_alerts()
        
        # Also log
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
        """Get unresolved alerts"""
        return [a for a in self.alerts if not a.get('resolved', False)]

# ============ Service Checker ============
class ServiceChecker:
    """Service checker"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
    
    def is_port_open(self, port: int, host: str = '127.0.0.1') -> bool:
        """Check if port is open"""
        import socket
        try:
            with socket.create_connection((host, port), timeout=3):
                return True
        except:
            return False
    
    def is_process_running(self, name: str) -> bool:
        """Check if process is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if name in proc.info['name'] or name in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def get_ngrok_pid(self) -> Optional[int]:
        """Get ngrok process PID"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'ngrok' in proc.info['name'] and 'http' in cmdline:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def get_flask_pid(self) -> Optional[int]:
        """Get Flask process PID"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline'] or []
                cmdline_str = ' '.join(cmdline)
                # Match python app.py or flask run
                if 'app.py' in cmdline_str or ('flask' in cmdline_str and 'run' in cmdline_str):
                    # Make sure it's the dashboard app.py
                    if str(Config.DASHBOARD_DIR) in cmdline_str or 'dashboard' in cmdline_str:
                        return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return None
    
    def check_ngrok_api(self) -> Dict[str, Any]:
        """Check ngrok API status"""
        result = {
            'success': False,
            'tunnels': [],
            'public_url': None,
            'error': None,
            'error_code': None
        }
        
        try:
            response = requests.get(
                f'http://127.0.0.1:{Config.NGROK_API_PORT}/api/tunnels',
                timeout=5
            )
            data = response.json()
            
            result['success'] = True
            result['tunnels'] = data.get('tunnels', [])
            
            # Get public URL
            for tunnel in result['tunnels']:
                if tunnel.get('public_url', '').startswith('https://'):
                    result['public_url'] = tunnel['public_url']
                    break
                    
        except requests.exceptions.ConnectionError:
            result['error'] = 'ngrok API unreachable'
            result['error_code'] = 'ERR_NGROK_3200'  # ngrok offline
        except requests.exceptions.Timeout:
            result['error'] = 'ngrok API timeout'
            result['error_code'] = 'ERR_NGROK_334'  # Session timeout/conflict
        except Exception as e:
            result['error'] = f'Unknown: {str(e)}'
            result['error_code'] = 'UNKNOWN'
        
        return result
    
    def check_external_tunnel(self) -> Dict[str, Any]:
        """Check tunnel from external perspective"""
        result = {
            'success': False,
            'error': None,
            'error_code': None
        }
        
        try:
            # Try to access the tunnel URL
            response = requests.get(
                f'https://{Config.NGROK_DOMAIN}/api/health',
                timeout=10,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                result['success'] = True
            elif response.status_code in [502, 503]:
                result['error'] = 'ngrok tunnel error'
                result['error_code'] = 'ERR_NGROK_502'
            else:
                result['error'] = f'HTTP {response.status_code}'
                
        except requests.exceptions.ConnectionError as e:
            error_str = str(e).lower()
            if 'err_ngrok_3200' in error_str:
                result['error'] = 'ngrok tunnel offline'
                result['error_code'] = 'ERR_NGROK_3200'
            elif 'err_ngrok_334' in error_str:
                result['error'] = 'ngrok session conflict'
                result['error_code'] = 'ERR_NGROK_334'
            else:
                result['error'] = 'Connection failed'
                result['error_code'] = 'CONNECTION_ERROR'
        except requests.exceptions.Timeout:
            result['error'] = 'Request timeout'
            result['error_code'] = 'TIMEOUT'
        except Exception as e:
            result['error'] = str(e)
            result['error_code'] = 'UNKNOWN'
        
        return result
    
    def check_flask_health(self) -> Dict[str, Any]:
        """Check Flask health"""
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
        """Get full service status"""
        ngrok_api = self.check_ngrok_api()
        external_check = self.check_external_tunnel()
        flask_health = self.check_flask_health()
        
        errors = []
        if ngrok_api.get('error'):
            errors.append(f"ngrok: {ngrok_api['error']}")
        if external_check.get('error') and not external_check.get('success'):
            errors.append(f"external: {external_check['error']}")
        if flask_health.get('error'):
            errors.append(f"flask: {flask_health['error']}")
        
        # ngrok tunnel is active if both API says so AND we can reach it externally
        tunnel_active = (
            ngrok_api['success'] and 
            len(ngrok_api['tunnels']) > 0 and
            external_check['success']
        )
        
        return ServiceStatus(
            timestamp=datetime.now().isoformat(),
            ngrok_running=self.is_process_running('ngrok'),
            ngrok_tunnel_active=tunnel_active,
            ngrok_public_url=ngrok_api.get('public_url'),
            flask_running=self.is_process_running('python') and self.is_port_open(Config.FLASK_PORT),
            flask_port_open=self.is_port_open(Config.FLASK_PORT),
            flask_health_ok=flask_health['success'],
            errors=errors
        )

# ============ Service Manager ============
class ServiceManager:
    """Service manager"""
    
    def __init__(self):
        self.checker = ServiceChecker()
        self.alert_manager = AlertManager()
    
    def kill_process_by_port(self, port: int) -> bool:
        """Kill process by port"""
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.pid:
                    try:
                        proc = psutil.Process(conn.pid)
                        logger.info(f"Killing process on port {port}: {proc.name()} (PID: {conn.pid})")
                        proc.terminate()
                        proc.wait(timeout=5)
                        return True
                    except psutil.NoSuchProcess:
                        pass
        except Exception as e:
            logger.error(f"Failed to kill process on port {port}: {e}")
        return False
    
    def kill_ngrok(self) -> bool:
        """Kill ngrok process"""
        pid = self.checker.get_ngrok_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                logger.info(f"Killing ngrok (PID: {pid})")
                proc.terminate()
                proc.wait(timeout=5)
                return True
            except Exception as e:
                logger.error(f"Failed to kill ngrok: {e}")
                try:
                    proc.kill()
                except:
                    pass
        # Also kill any remaining ngrok processes
        subprocess.run(['pkill', '-f', 'ngrok'], capture_output=True)
        return True
    
    def kill_flask(self) -> bool:
        """Kill Flask process"""
        pid = self.checker.get_flask_pid()
        if pid:
            try:
                proc = psutil.Process(pid)
                logger.info(f"Killing Flask (PID: {pid})")
                proc.terminate()
                proc.wait(timeout=5)
                return True
            except Exception as e:
                logger.error(f"Failed to kill Flask: {e}")
                try:
                    proc.kill()
                except:
                    pass
        # Also kill any dashboard app.py processes
        subprocess.run(['pkill', '-f', 'dashboard/app.py'], capture_output=True)
        return True
    
    def start_flask(self) -> bool:
        """Start Flask service"""
        try:
            logger.info(f"Starting Flask (port: {Config.FLASK_PORT})...")
            
            # Change to dashboard directory
            os.chdir(Config.DASHBOARD_DIR)
            
            # Set environment variables
            env = os.environ.copy()
            env['FLASK_APP'] = Config.FLASK_APP
            env['FLASK_RUN_PORT'] = str(Config.FLASK_PORT)
            env['FLASK_RUN_HOST'] = Config.FLASK_HOST
            env['DASHBOARD_PASSWORD'] = Config.DASHBOARD_PASSWORD  # Critical: set password
            
            # Start Flask
            subprocess.Popen(
                [sys.executable, Config.FLASK_APP],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=Config.DASHBOARD_DIR
            )
            
            # Wait for startup
            time.sleep(Config.FLASK_STARTUP_WAIT)
            
            # Verify startup
            if self.checker.is_port_open(Config.FLASK_PORT):
                logger.info("✅ Flask started successfully")
                return True
            else:
                logger.error("❌ Flask failed to start - port not open")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start Flask: {e}")
            return False
    
    def start_ngrok(self) -> bool:
        """Start ngrok"""
        try:
            logger.info(f"Starting ngrok (pointing to port: {Config.FLASK_PORT})...")
            
            subprocess.Popen(
                Config.NGROK_CMD,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Wait for startup
            time.sleep(Config.NGROK_STARTUP_WAIT)
            
            # Verify startup
            ngrok_api = self.checker.check_ngrok_api()
            if ngrok_api['success']:
                logger.info(f"✅ ngrok started - URL: {ngrok_api.get('public_url', 'unknown')}")
                return True
            else:
                logger.error(f"❌ ngrok failed to start - {ngrok_api.get('error', 'unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start ngrok: {e}")
            return False
    
    def restart_flask(self) -> bool:
        """Restart Flask"""
        self.kill_flask()
        time.sleep(1)
        
        # Ensure port is released
        if self.checker.is_port_open(Config.FLASK_PORT):
            self.kill_process_by_port(Config.FLASK_PORT)
            time.sleep(1)
        
        return self.start_flask()
    
    def restart_ngrok(self) -> bool:
        """Restart ngrok"""
        self.kill_ngrok()
        time.sleep(2)
        return self.start_ngrok()
    
    def restart_all(self) -> bool:
        """Restart all services"""
        logger.info("🔄 Restarting all services...")
        
        # Stop ngrok first
        self.kill_ngrok()
        time.sleep(1)
        
        # Restart Flask
        if not self.restart_flask():
            logger.error("❌ Flask restart failed")
            return False
        
        time.sleep(3)
        
        # Start ngrok
        if not self.start_ngrok():
            logger.error("❌ ngrok start failed")
            return False
        
        # Wait for external connectivity
        for i in range(10):
            external = self.checker.check_external_tunnel()
            if external['success']:
                logger.info("✅ All services restarted successfully")
                return True
            time.sleep(2)
        
        logger.warning("⚠️ Services restarted but external check failed")
        return True  # Still consider it success if API check passes

# ============ Main Monitor Loop ============
class NgrokMonitor:
    """Ngrok monitor"""
    
    def __init__(self):
        self.checker = ServiceChecker()
        self.manager = ServiceManager()
        self.alert_manager = AlertManager()
        self.running = False
        self.retry_count = 0
        self.consecutive_failures = 0
        
        # Signal handling
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Signal handler"""
        logger.info(f"Received signal {signum}, stopping monitor...")
        self.running = False
    
    def check_and_recover(self) -> bool:
        """
        Check service status and auto-recover
        Returns: True = all good, False = recovery needed but failed
        """
        status = self.checker.get_full_status()
        
        # Log status (every 10th check or when there are errors)
        if status.errors or self.retry_count == 0:
            logger.debug(f"Status check: ngrok={status.ngrok_running}, flask={status.flask_running}, "
                        f"health={status.flask_health_ok}, tunnel={status.ngrok_tunnel_active}")
        
        issues = []
        error_code = None
        
        # 1. Check Flask
        if not status.flask_running or not status.flask_health_ok:
            if not status.flask_port_open:
                issues.append(f"Flask port {Config.FLASK_PORT} not open")
            elif not status.flask_health_ok:
                issues.append("Flask health check failed")
            else:
                issues.append("Flask process not running")
        
        # 2. Check ngrok
        for error in status.errors:
            if 'ERR_NGROK_3200' in error:
                error_code = 'ERR_NGROK_3200'
                issues.append("ngrok offline (ERR_NGROK_3200)")
            elif 'ERR_NGROK_334' in error:
                error_code = 'ERR_NGROK_334'
                issues.append("ngrok session conflict (ERR_NGROK_334)")
            elif 'ERR_NGROK_502' in error:
                error_code = 'ERR_NGROK_502'
                issues.append("ngrok backend unreachable (ERR_NGROK_502)")
        
        if not status.ngrok_running:
            issues.append("ngrok process not running")
        elif not status.ngrok_tunnel_active:
            issues.append("ngrok tunnel not active")
        
        # Check URL match
        if status.ngrok_public_url and Config.NGROK_DOMAIN not in status.ngrok_public_url:
            logger.warning(f"ngrok URL mismatch: {status.ngrok_public_url} != {Config.NGROK_DOMAIN}")
        
        # If issues found, perform recovery
        if issues:
            issue_msg = "; ".join(issues)
            logger.warning(f"Issues detected: {issue_msg}")
            self.consecutive_failures += 1
            
            # Decide recovery strategy
            flask_issue = not status.flask_health_ok or not status.flask_port_open
            ngrok_issue = error_code in ['ERR_NGROK_3200', 'ERR_NGROK_334'] or not status.ngrok_running
            
            if flask_issue and ngrok_issue:
                # Both have issues - full restart
                action = "restart all services"
                service = "both"
                success = self.manager.restart_all()
                
            elif flask_issue:
                # Flask problem - restart Flask
                action = "restart Flask"
                service = "flask"
                success = self.manager.restart_flask()
                if success:
                    time.sleep(2)
                    # If ngrok also stopped, restart it
                    ngrok_status = self.checker.check_ngrok_api()
                    if not ngrok_status['success']:
                        self.manager.start_ngrok()
                        
            elif ngrok_issue:
                # ngrok problem - restart ngrok
                action = "restart ngrok"
                service = "ngrok"
                success = self.manager.restart_ngrok()
                
            else:
                # Unknown issue - full restart
                action = "restart all services"
                service = "both"
                success = self.manager.restart_all()
            
            # Log the alert
            self.alert_manager.add_alert(AlertEvent(
                timestamp=datetime.now().isoformat(),
                level='ERROR' if self.consecutive_failures < 3 else 'CRITICAL',
                error_code=error_code,
                message=issue_msg,
                service=service,
                action_taken=action,
                resolved=success
            ))
            
            if success:
                logger.info(f"✅ {action} successful")
                self.retry_count = 0
                self.consecutive_failures = 0
                return True
            else:
                logger.error(f"❌ {action} failed")
                self.retry_count += 1
                return False
        
        # All good
        self.retry_count = 0
        self.consecutive_failures = 0
        return True
    
    def run(self):
        """Run monitor loop"""
        logger.info("=" * 60)
        logger.info("🚀 Ngrok High Availability Monitor Started")
        logger.info("=" * 60)
        logger.info(f"Config: Flask port={Config.FLASK_PORT}, Check interval={Config.CHECK_INTERVAL}s")
        logger.info(f"Domain: {Config.NGROK_DOMAIN}")
        logger.info(f"Log: {Config.LOG_DIR / 'ngrok_monitor.log'}")
        logger.info(f"Alerts: {Config.ALERT_DIR}/ngrok_YYYY-MM-DD.json")
        logger.info("=" * 60)
        
        self.running = True
        check_count = 0
        
        # Initial check and recover if needed
        logger.info("Performing initial health check...")
        self.check_and_recover()
        
        while self.running:
            try:
                check_count += 1
                
                # Perform check
                healthy = self.check_and_recover()
                
                if not healthy and self.retry_count >= Config.MAX_RETRIES:
                    logger.error(f"❌ Failed to recover after {Config.MAX_RETRIES} attempts")
                    self.alert_manager.add_alert(AlertEvent(
                        timestamp=datetime.now().isoformat(),
                        level='CRITICAL',
                        error_code=None,
                        message=f"Failed to recover after {Config.MAX_RETRIES} attempts",
                        service='both',
                        action_taken='waiting for manual intervention'
                    ))
                    self.retry_count = 0  # Reset and keep trying
                
                # Periodic heartbeat (every 30 minutes)
                if check_count % 30 == 0:
                    status = self.checker.get_full_status()
                    logger.info(f"💓 Heartbeat #{check_count} - Status: {'✅ Healthy' if not status.errors else '⚠️ Issues'}")
                
                # Wait for next check
                for _ in range(Config.CHECK_INTERVAL):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.exception(f"Monitor loop error: {e}")
                time.sleep(5)
        
        logger.info("👋 Monitor stopped")

# ============ CLI ============
def main():
    """Main entry"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ngrok High Availability Monitor')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--restart', action='store_true', help='Restart all services')
    parser.add_argument('--once', action='store_true', help='Run one check and exit')
    parser.add_argument('--test-alert', action='store_true', help='Test alert logging')
    
    args = parser.parse_args()
    
    if args.status:
        # Show status
        checker = ServiceChecker()
        status = checker.get_full_status()
        
        print("\n📊 Service Status")
        print("=" * 50)
        print(f"Time: {status.timestamp}")
        print(f"\n🌐 ngrok:")
        print(f"   Process: {'✅ Running' if status.ngrok_running else '❌ Not running'}")
        print(f"   Tunnel:  {'✅ Active' if status.ngrok_tunnel_active else '❌ Inactive'}")
        print(f"   URL:     {status.ngrok_public_url or 'N/A'}")
        print(f"\n🐍 Flask:")
        print(f"   Process: {'✅ Running' if status.flask_running else '❌ Not running'}")
        print(f"   Port {Config.FLASK_PORT}: {'✅ Open' if status.flask_port_open else '❌ Closed'}")
        print(f"   Health:  {'✅ OK' if status.flask_health_ok else '❌ Failed'}")
        print(f"\n⚠️  Issues: {', '.join(status.errors) if status.errors else 'None'}")
        print("=" * 50)
        
    elif args.restart:
        # Restart services
        manager = ServiceManager()
        success = manager.restart_all()
        sys.exit(0 if success else 1)
        
    elif args.once:
        # Run one check
        monitor = NgrokMonitor()
        healthy = monitor.check_and_recover()
        sys.exit(0 if healthy else 1)
        
    elif args.test_alert:
        # Test alert
        alert_mgr = AlertManager()
        alert_mgr.add_alert(AlertEvent(
            timestamp=datetime.now().isoformat(),
            level='INFO',
            error_code='TEST',
            message='Test alert from ngrok_monitor.py',
            service='test',
            action_taken='none'
        ))
        print("✅ Test alert logged")
        
    else:
        # Start monitor
        monitor = NgrokMonitor()
        monitor.run()

if __name__ == '__main__':
    main()

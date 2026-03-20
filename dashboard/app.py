#!/usr/bin/env python3
"""
Flask Backend API for Trading Screener Dashboard
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, date
from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS
from functools import wraps

logger = logging.getLogger(__name__)

# Add dashboard to path
DASHBOARD_DIR = Path(__file__).parent
sys.path.insert(0, str(DASHBOARD_DIR))
os.chdir(DASHBOARD_DIR)  # Change to dashboard directory

from models import (
    init_db, get_all_screeners, get_screener, get_runs, get_run,
    get_results, get_results_by_date, get_db_connection
)
from screeners import (
    register_discovered_screeners, run_screener_subprocess,
    get_stock_data_for_chart, create_screener_file, update_screener_file,
    delete_screener_file
)
from ifind_realtime import RealtimeFeed
from ifind_client import IfindClient
import sqlite3
import pandas as pd
from pathlib import Path

# 简单密码配置 - 从环境变量读取，无默认值
DASHBOARD_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')
if not DASHBOARD_PASSWORD:
    raise ValueError("DASHBOARD_PASSWORD environment variable is required")

def check_auth(username, password):
    """验证密码（只验证密码，用户名随意）"""
    return password == DASHBOARD_PASSWORD

def authenticate():
    """返回 401 响应要求认证"""
    return Response(
        '请输入密码访问 Dashboard',
        401,
        {'WWW-Authenticate': 'Basic realm="Neo Dashboard"'}
    )

def require_auth(f):
    """装饰器：要求认证"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

app = Flask(__name__, static_folder=str(DASHBOARD_DIR / 'static'), static_url_path='')
CORS(app)  # Enable CORS for all routes

# 添加禁用缓存的响应头
@app.after_request
def add_header(response):
    """禁用浏览器缓存，避免认证问题"""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

# 为所有路由添加认证（除了健康检查和静态文件）
@app.before_request
def before_request():
    # 健康检查端点不需要认证
    if request.path == '/api/health':
        return None
    # 静态文件不需要认证
    if request.path.startswith('/assets/') or request.path.startswith('/favicon'):
        return None
    # API 和页面需要认证 - 临时禁用测试
    # auth = request.authorization
    # if not auth or not check_auth(auth.username, auth.password):
    #     return authenticate()
    return None  # 临时禁用认证

# Serve index.html at root
@app.route('/')
def index():
    return send_from_directory(DASHBOARD_DIR / 'static', 'index.html')

# Initialize database on startup
init_db()
register_discovered_screeners()

# Auto-initialize default screeners if none exist
try:
    from models import get_all_screeners
    if len(get_all_screeners()) == 0:
        print("No screeners found, initializing defaults...")
        # Import and run init
        import subprocess
        subprocess.run([sys.executable, str(DASHBOARD_DIR / 'init_db.py')], check=False)
        print("Default screeners initialized")
except Exception as e:
    print(f"Auto-init error: {e}")

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.route('/api/init', methods=['POST'])
def init_screeners():
    """Initialize default screeners in database"""
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(DASHBOARD_DIR / 'init_db.py')],
            capture_output=True,
            text=True,
            check=False
        )
        return jsonify({
            'success': True,
            'output': result.stdout,
            'error': result.stderr if result.stderr else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Module definitions for categorization
MODULES = {
    'screeners': {
        'title': 'Technical Screeners',
        'items': [
            'coffee_cup_screener',
            'jin_feng_huang_screener',
            'er_ban_hui_tiao_screener',
            'zhang_ting_bei_liang_yin_screener',
            'yin_feng_huang_screener',
            'shi_pan_xian_screener',
            'breakout_20day_screener',
            'breakout_main_screener',
            'daily_hot_cold_screener',
            'ashare_21_screener'
        ]
    },
    'cron': {
        'title': 'Cron Tasks',
        'items': [
            'intraday_screener',
            'postmarket_screener',
            'keyword_expander_screener'
        ],
        'schedules': {
            'intraday_screener': '09:35, 09:45, 10:00, 15:00',
            'postmarket_screener': '15:30 daily',
            'keyword_expander_screener': '16:00 daily'
        }
    },
    'jobs': {
        'title': 'Manual Jobs',
        'items': [],
        'dependencies': {}
    }
}

# Screener endpoints
@app.route('/api/screeners', methods=['GET'])
def list_screeners():
    """List all available screeners with categories"""
    screeners = get_all_screeners()
    
    # Add category to each screener
    for s in screeners:
        name = s['name']
        if name in MODULES['screeners']['items']:
            s['category'] = 'screener'
            s['category_label'] = 'Technical'
            s['schedule'] = 'On-demand'
        elif name in MODULES['cron']['items']:
            s['category'] = 'cron'
            s['category_label'] = 'Cron Task'
            s['schedule'] = MODULES['cron']['schedules'].get(name, 'Scheduled')
        elif name in MODULES['jobs']['items']:
            s['category'] = 'job'
            s['category_label'] = 'Manual Job'
            s['schedule'] = 'Manual'
            s['dependency'] = MODULES['jobs']['dependencies'].get(name)
        else:
            s['category'] = 'other'
            s['category_label'] = 'Other'
            s['schedule'] = 'Unknown'
    
    return jsonify({'screeners': screeners, 'modules': MODULES})

@app.route('/api/screeners/<name>', methods=['GET'])
def get_screener_detail(name):
    """Get screener details"""
    screener = get_screener(name)
    if not screener:
        return jsonify({'error': 'Screener not found'}), 404
    
    # Read the source file for display
    try:
        with open(screener['file_path'], 'r') as f:
            source_code = f.read()
    except Exception as e:
        source_code = f"Error reading file: {e}"
    
    return jsonify({
        'screener': screener,
        'source_code': source_code
    })

@app.route('/api/screeners/<name>/run', methods=['POST'])
def run_screener(name):
    """Run a screener"""
    data = request.get_json() or {}
    run_date = data.get('date', date.today().isoformat())
    
    # 标准化日期格式 - 确保是 YYYY-MM-DD
    if '/' in run_date:
        run_date = run_date.replace('/', '-')
    
    # 验证日期格式
    from datetime import datetime
    try:
        check_date = datetime.strptime(run_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({
            'success': False,
            'error': 'DATE_FORMAT_INVALID',
            'message': f'日期格式无效: {run_date}，请使用 YYYY-MM-DD 格式'
        }), 400
    
    # 检查数据库是否有该日期数据
    try:
        latest_data_date = get_latest_data_date()
        if run_date > latest_data_date:
            return jsonify({
                'success': False,
                'error': 'DATE_NO_DATA',
                'message': f'该日期暂无数据，最新数据日期为：{latest_data_date}'
            }), 400
    except Exception as e:
        logger.error(f"Error checking data date: {e}")
    
    screener = get_screener(name)
    if not screener:
        return jsonify({'error': 'Screener not found'}), 404
    
    # Run the screener
    result = run_screener_subprocess(name, run_date)
    
    if result['success']:
        return jsonify({
            'success': True,
            'run_id': result['run_id'],
            'stocks_found': result['stocks_found'],
            'message': f"Screener completed. Found {result['stocks_found']} stocks."
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error'],
            'message': f"Screener failed: {result['error']}"
        }), 500


def get_latest_data_date():
    """获取数据库中最新的数据日期"""
    try:
        import sqlite3
        conn = sqlite3.connect('/Users/mac/.openclaw/workspace-neo/data/stock_data.db')
        cursor = conn.execute("SELECT MAX(trade_date) FROM daily_prices")
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else date.today().isoformat()
    except:
        return date.today().isoformat()

# Results endpoints
@app.route('/api/runs', methods=['GET'])
def list_runs():
    """List historical runs"""
    screener_name = request.args.get('screener')
    limit = request.args.get('limit', 50, type=int)
    
    runs = get_runs(screener_name=screener_name, limit=limit)
    return jsonify({'runs': runs})

@app.route('/api/results', methods=['GET'])
def get_results_endpoint():
    """Get results by screener and date"""
    screener_name = request.args.get('screener')
    run_date = request.args.get('date')
    
    if not screener_name or not run_date:
        return jsonify({'error': 'Missing screener or date parameter'}), 400
    
    results = get_results_by_date(screener_name, run_date)
    
    if results is None:
        return jsonify({'error': 'No run found for this screener and date'}), 404
    
    return jsonify({
        'screener': screener_name,
        'date': run_date,
        'count': len(results),
        'results': results
    })

@app.route('/api/stock/<code>/chart', methods=['GET'])
def get_stock_chart(code):
    """Get stock price data for K-line chart"""
    days = request.args.get('days', 60, type=int)
    
    data = get_stock_data_for_chart(code, days)
    
    if data is None:
        return jsonify({'error': 'Stock data not found'}), 404
    
    return jsonify({
        'code': code,
        'days': len(data),
        'data': data
    })

@app.route('/api/calendar', methods=['GET'])
def get_calendar_data():
    """Get calendar view data - runs grouped by date"""
    runs = get_runs(limit=365)  # Last year
    
    # Group by date
    calendar = {}
    for run in runs:
        date_str = run['run_date']
        if date_str not in calendar:
            calendar[date_str] = {
                'date': date_str,
                'screeners': [],
                'total_stocks': 0
            }
        calendar[date_str]['screeners'].append({
            'name': run['screener_name'],
            'status': run['status'],
            'stocks_found': run['stocks_found']
        })
        calendar[date_str]['total_stocks'] += run['stocks_found']
    
    return jsonify({
        'calendar': list(calendar.values())
    })

# CRUD Operations for Screeners/Tasks/Jobs
@app.route('/api/screeners', methods=['POST'])
def create_screener():
    """Create a new screener/task/job"""
    data = request.get_json() or {}
    
    name = data.get('name', '').strip()
    display_name = data.get('display_name', '').strip()
    description = data.get('description', '').strip()
    category = data.get('category', 'screener')  # screener, cron, job
    code_content = data.get('code')
    
    if not name or not display_name:
        return jsonify({'error': 'Name and display_name are required'}), 400
    
    # Validate name (alphanumeric and underscore only)
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return jsonify({'error': 'Name must start with letter and contain only letters, numbers, and underscores'}), 400
    
    try:
        screener = create_screener_file(name, display_name, description, category, code_content)
        return jsonify({
            'success': True,
            'screener': screener,
            'message': f'{category.title()} "{display_name}" created successfully'
        })
    except FileExistsError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>', methods=['PUT'])
def update_screener_endpoint(name):
    """Update an existing screener/task/job"""
    data = request.get_json() or {}
    
    code_content = data.get('code')
    display_name = data.get('display_name')
    description = data.get('description')
    
    if not code_content:
        return jsonify({'error': 'Code content is required'}), 400
    
    try:
        result = update_screener_file(name, code_content, display_name, description)
        return jsonify({
            'success': True,
            'message': f'"{name}" updated successfully'
        })
    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/screeners/<name>', methods=['DELETE'])
def delete_screener_endpoint(name):
    """Delete a screener/task/job"""
    try:
        result = delete_screener_file(name)
        return jsonify({
            'success': True,
            'message': f'"{name}" deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<name>/<date>', methods=['GET'])
def download_screener_file(name, date):
    """Download screener result file directly - supports realtime results"""
    from flask import send_file
    from pathlib import Path
    
    workspace_root = Path('/Users/mac/.openclaw/workspace-neo')
    dir_name = name.replace('_screener', '')
    possible_paths = []
    
    # Check for realtime results first
    if date.startswith('realtime-'):
        possible_paths.append(workspace_root / 'data' / 'screeners' / dir_name / f'{date}.xlsx')
    else:
        # Standard paths
        possible_paths.append(workspace_root / 'data' / 'screeners' / dir_name / f'{date}.xlsx')
        possible_paths.append(workspace_root / 'data' / f'{name}_{date}.xlsx')
        
        if name == 'daily_hot_cold_screener':
            possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}.xlsx')
            possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}_hot.xlsx')
            possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}_cold.xlsx')
    
    file_path = None
    for path in possible_paths:
        if path.exists():
            file_path = path
            break
    
    if not file_path:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        short_names = {
            'coffee_cup_screener': 'coffee_cup',
            'jin_feng_huang_screener': 'jinfenghuang',
            'yin_feng_huang_screener': 'yinfenghuang',
            'shi_pan_xian_screener': 'shipanxian',
            'er_ban_hui_tiao_screener': 'erbanhuitiao',
            'zhang_ting_bei_liang_yin_screener': 'zhangtingbeiliangyin',
            'breakout_20day_screener': 'breakout20day',
            'breakout_main_screener': 'breakoutmain',
            'daily_hot_cold_screener': 'dailyhotcold',
            'shuang_shou_ban_screener': 'shuangshouban',
            'ashare_21_screener': 'ashare21',
            'intraday_screener': 'intraday',
            'postmarket_screener': 'postmarket'
        }
        short_name = short_names.get(name, name.replace('_screener', ''))
        download_filename = f"{short_name}_{date}.xlsx"
        
        return send_file(file_path, as_attachment=True, download_name=download_filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/csv/<name>/<date>', methods=['GET'])
def download_screener_csv(name, date):
    """Download screener result as CSV - supports realtime results"""
    from flask import send_file
    from pathlib import Path
    import pandas as pd
    import io
    
    workspace_root = Path('/Users/mac/.openclaw/workspace-neo')
    dir_name = name.replace('_screener', '')
    
    # Check for realtime CSV files first
    if date.startswith('realtime-'):
        csv_path = workspace_root / 'data' / 'screeners' / dir_name / f'{date}.csv'
        if csv_path.exists():
            short_name = name.replace('_screener', '')
            csv_filename = f"{short_name}_{date}.csv"
            return send_file(
                csv_path,
                mimetype='text/csv',
                as_attachment=True,
                download_name=csv_filename
            )
        return jsonify({'error': 'Realtime result not found'}), 404
    
    # Standard: convert Excel to CSV
    possible_paths = []
    possible_paths.append(workspace_root / 'data' / 'screeners' / dir_name / f'{date}.xlsx')
    possible_paths.append(workspace_root / 'data' / f'{name}_{date}.xlsx')
    
    if name == 'daily_hot_cold_screener':
        possible_paths.append(workspace_root / 'data' / '每日热冷股' / f'{date}.xlsx')
    
    excel_path = None
    for path in possible_paths:
        if path.exists():
            excel_path = path
            break
    
    if not excel_path:
        return jsonify({'error': 'Source file not found'}), 404
    
    try:
        output = io.StringIO()
        df = pd.read_excel(excel_path)
        df.to_csv(output, index=False, encoding='utf-8-sig')
        output.seek(0)
        
        short_names = {
            'coffee_cup_screener': 'coffee_cup',
            'jin_feng_huang_screener': 'jinfenghuang',
            'yin_feng_huang_screener': 'yinfenghuang',
            'shi_pan_xian_screener': 'shipanxian',
            'er_ban_hui_tiao_screener': 'erbanhuitiao',
            'zhang_ting_bei_liang_yin_screener': 'zhangtingbeiliangyin',
            'breakout_20day_screener': 'breakout20day',
            'breakout_main_screener': 'breakoutmain',
            'daily_hot_cold_screener': 'dailyhotcold',
            'shuang_shou_ban_screener': 'shuangshouban',
            'ashare_21_screener': 'ashare21',
            'intraday_screener': 'intraday',
            'postmarket_screener': 'postmarket'
        }
        short_name = short_names.get(name, name.replace('_screener', ''))
        csv_filename = f"{short_name}_{date}.csv"
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=csv_filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 检查单个股票是否符合筛选条件
@app.route('/api/check-stock', methods=['POST'])
def check_stock():
    """检查单个股票是否符合筛选条件"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    screener_name = data.get('screener')
    stock_code = data.get('code')
    date = data.get('date')
    
    if not screener_name or not stock_code:
        return jsonify({'error': 'Screener name and stock code are required'}), 400
    
    # 标准化股票代码
    code = stock_code.strip()
    if '.' in code:
        # 如果是 sh.600000 格式，提取纯数字部分
        code = code.split('.')[-1]
    
    try:
        # 导入对应的筛选器
        import sys
        sys.path.insert(0, str(DASHBOARD_DIR.parent / 'scripts'))
        
        # 获取筛选器模块和类名
        module_map = {
            'coffee_cup_screener': ('coffee_cup_screener', 'CoffeeCupScreener'),
            'double_bottom_screener': ('double_bottom_screener', 'DoubleBottomScreener'),
            'flat_base_screener': ('flat_base_screener', 'FlatBaseScreener'),
            'high_tight_flag_screener': ('high_tight_flag_screener', 'HighTightFlagScreener'),
            'ascending_triangle_screener': ('ascending_triangle_screener', 'AscendingTriangleScreener'),
            'jin_feng_huang_screener': ('jin_feng_huang_screener', 'JinFengHuangScreener'),
            'er_ban_hui_tiao_screener': ('er_ban_hui_tiao_screener', 'ErBanHuiTiaoScreener'),
            'zhang_ting_bei_liang_yin_screener': ('zhang_ting_bei_liang_yin_screener', 'ZhangTingBeiLiangYinScreener'),
            'yin_feng_huang_screener': ('yin_feng_huang_screener', 'YinFengHuangScreener'),
            'shi_pan_xian_screener': ('shi_pan_xian_screener', 'ShiPanXianScreener'),
            'breakout_20day_screener': ('breakout_20day_screener', 'Breakout20DayScreener'),
            'breakout_main_screener': ('breakout_main_screener', 'BreakoutMainScreener'),
            'shuang_shou_ban_screener': ('shuang_shou_ban_screener', 'ShuangShouBanScreener'),
            'daily_hot_cold_screener': ('daily_hot_cold_screener', 'DailyHotColdScreener'),
        }
        
        if screener_name not in module_map:
            return jsonify({
                'match': False,
                'code': code,
                'name': '',
                'date': date or '',
                'reasons': ['该筛选器暂不支持单个股票检查功能']
            })
        
        module_name, class_name = module_map[screener_name]
        module = __import__(module_name)
        screener_class = getattr(module, class_name)
        
        # 实例化筛选器，使用正确的数据库路径
        db_path = str(DASHBOARD_DIR.parent / 'data' / 'stock_data.db')
        if screener_name == 'coffee_cup_screener':
            screener = screener_class(db_path=db_path, check_data_update=False)
        else:
            screener = screener_class(db_path=db_path)
        
        # 检查单个股票
        result = screener.check_single_stock(code, date)
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'match': False,
            'code': code,
            'name': '',
            'date': date or '',
            'reasons': [f'检查出错: {str(e)}']
        })


# ========== Realtime iFinD Integration ==========

@app.route('/api/screener/<name>/realtime-run', methods=['POST'])
def run_screener_realtime(name):
    """Run screener with realtime iFinD data - Full screener logic with history"""
    from datetime import datetime, timedelta
    from ifind_history import IfindHistory
    import importlib
    import sys
    
    screener = get_screener(name)
    if not screener:
        return jsonify({'error': 'Screener not found'}), 404
    
    try:
        # Get all stock codes
        db_path = Path(__file__).parent.parent / 'data' / 'stock_data.db'
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT DISTINCT code FROM daily_prices")
        all_codes = [row[0] for row in cursor.fetchall()]
        stock_names = {row[0]: row[1] for row in conn.execute("SELECT code, name FROM stocks")}
        conn.close()
        
        # Initialize iFinD history
        history = IfindHistory()
        
        # Fetch history data (for coffee cup: need 250 days)
        # Batch processing for all stocks
        all_history_data = []
        batch_size = 100
        
        # Calculate date range
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=300)).strftime('%Y-%m-%d')
        
        print(f"📊 Fetching history data for {len(all_codes)} stocks...")
        
        for i in range(0, len(all_codes), batch_size):
            batch = all_codes[i:i+batch_size]
            try:
                df = history.fetch_history(batch, start_date, end_date)
                if not df.empty:
                    all_history_data.append(df)
                print(f"  Batch {i//batch_size + 1}/{(len(all_codes)-1)//batch_size + 1}: {len(batch)} stocks")
            except Exception as e:
                print(f"  Batch failed: {e}")
                continue
        
        if not all_history_data:
            return jsonify({'success': False, 'error': 'No history data received'}), 500
        
        # Combine all history data
        history_df = pd.concat(all_history_data, ignore_index=True)
        history_df['code'] = history_df['code'].apply(lambda x: x.split('.')[0] if '.' in str(x) else x)
        
        # Get today's realtime data
        feed = RealtimeFeed()
        ifind_codes = [f"{c}.SH" if c.startswith('6') else f"{c}.SZ" for c in all_codes]
        
        print("⚡ Fetching realtime data...")
        realtime_df = feed.fetch(ifind_codes, indicators="latest,change,changeRatio,volume,amount")
        
        if not realtime_df.empty:
            realtime_df['code'] = realtime_df['thscode'].apply(lambda x: x.split('.')[0] if '.' in str(x) else x)
            realtime_df['trade_date'] = datetime.now().strftime('%Y-%m-%d')
            realtime_df['close'] = pd.to_numeric(realtime_df['latest'], errors='coerce')
            realtime_df['pct_change'] = pd.to_numeric(realtime_df['changeRatio'], errors='coerce')
            realtime_df['volume'] = pd.to_numeric(realtime_df['volume'], errors='coerce')
            realtime_df['amount'] = pd.to_numeric(realtime_df['amount'], errors='coerce')
        
        # Combine history + realtime
        combined_df = pd.concat([history_df, realtime_df], ignore_index=True)
        
        # Run screener logic
        # Import screener dynamically
        screener_module = name.replace('_screener', '')
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
            module = importlib.import_module(f'{screener_module}_screener')
            
            # Get screener class
            screener_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and 'Screener' in attr_name and attr_name != 'BaseScreener':
                    screener_class = attr
                    break
            
            if screener_class is None:
                raise ImportError(f"No screener class found in {screener_module}_screener")
            
            # Initialize with in-memory data
            screener_instance = screener_class(enable_progress=False)
            screener_instance.data_df = combined_df  # Inject data
            
            # Run screening for today
            today = datetime.now().strftime('%Y-%m-%d')
            results = screener_instance.run_screening(today)
            
            # Format results
            formatted_results = []
            for r in results:
                code = r.get('code', '')
                formatted_results.append({
                    'code': code,
                    'name': stock_names.get(code, ''),
                    'latest': r.get('close', 0),
                    'pct_change': r.get('pct_change', 0),
                    **{k: v for k, v in r.items() if k not in ['code', 'close', 'pct_change']}
                })
            
            # Save results
            timestamp = datetime.now()
            date_str = f"realtime-{timestamp.strftime('%Y%m%d-%H%M%S')}"
            output_dir = Path(__file__).parent.parent / 'data' / 'screeners' / name.replace('_screener', '')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            results_df = pd.DataFrame(formatted_results)
            excel_file = output_dir / f'{date_str}.xlsx'
            csv_file = output_dir / f'{date_str}.csv'
            results_df.to_excel(str(excel_file), index=False, engine='xlsxwriter')
            results_df.to_csv(str(csv_file), index=False, encoding='utf-8-sig')
            
            return jsonify({
                'success': True,
                'screener': name,
                'date': date_str,
                'timestamp': timestamp.isoformat(),
                'count': len(formatted_results),
                'total_checked': len(all_codes),
                'results': formatted_results[:100],
                'file_paths': {'excel': str(excel_file), 'csv': str(csv_file)}
            })
            
        except Exception as e:
            print(f"Screener execution failed: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': f'Screener execution failed: {str(e)}'}), 500
        
    except Exception as e:
        print(f"Realtime run failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/results/realtime', methods=['GET'])
def get_realtime_results():
    """Get the latest realtime results for a screener"""
    screener_name = request.args.get('screener')
    if not screener_name:
        return jsonify({'error': 'Missing screener parameter'}), 400
    
    # Find the most recent realtime file
    output_dir = Path(__file__).parent.parent / 'data' / 'screeners' / screener_name.replace('_screener', '')
    
    if not output_dir.exists():
        return jsonify({'error': 'No realtime results found'}), 404
    
    # Get most recent realtime CSV file
    realtime_files = sorted(output_dir.glob('realtime-*.csv'), reverse=True)
    if not realtime_files:
        return jsonify({'error': 'No realtime results found'}), 404
    
    latest_file = realtime_files[0]
    date_str = latest_file.stem  # e.g., "realtime-20250319-190730"
    
    try:
        df = pd.read_csv(str(latest_file), encoding='utf-8-sig')
        results = df.to_dict('records')
        
        return jsonify({
            'screener': screener_name,
            'date': date_str,
            'count': len(results),
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=5003, help='Port to run on')
    args = parser.parse_args()
    
    print("Starting Trading Screener Dashboard API...")
    print(f"Database: {DASHBOARD_DIR / 'data' / 'dashboard.db'}")
    print(f"Port: {args.port}")
    print(f"Multi-threading enabled for concurrent users")
    app.run(host='0.0.0.0', port=args.port, debug=False, threaded=True)

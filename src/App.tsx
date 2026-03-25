import { useState, useEffect, useRef } from 'react';
import './App.css';
import * as echarts from 'echarts';
import { formatDate, formatStockCode, isValidDate, isValidStockCode, toISODate } from './utils/format';
import Monitor from './pages/MonitorV2';
import { CalendarWithButton } from './components/Calendar';

// Backend API configuration
// Use proxy in development, auto-detect in production
const API_BASE = import.meta.env.DEV ? '/api' : `${window.location.origin}/api`;
const AUTH_HEADER = 'Basic ' + btoa('user:NeoTrade2025');

// Get today's date in YYYY-MM-DD format
const getTodayString = () => {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

interface Screener {
  id: number;
  name: string;
  display_name: string;
  description: string;
  category: string;
}

interface CheckResult {
  match: boolean;
  code: string;
  name: string;
  date: string;
  details: Record<string, any>;
  reasons: string[];
}

function App() {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [loading, setLoading] = useState(true);

  // 读取 URL 参数初始化 activeTab
  const getInitialTab = () => {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    return tab || 'screeners';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab());

  // Update URL when tab changes
  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    const url = new URL(window.location.href);
    url.searchParams.set('tab', tabId);
    window.history.replaceState({}, '', url.toString());
  };

  useEffect(() => {
    fetch(`${API_BASE}/screeners`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(data => { setScreeners(data.screeners || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'screeners', label: 'Screeners', icon: '🔍' },
    { id: 'results', label: 'Results', icon: '📈' },
    { id: 'strategy', label: 'Strategy', icon: '🧬' },
    { id: 'monitor', label: 'Monitor', icon: '👁️' },
  ];

  const renderContent = () => {
    switch(activeTab) {
      case 'dashboard': return <DashboardView />;
      case 'screeners': return <ScreenersView screeners={screeners} loading={loading} />;
      case 'results': return <ResultsView screeners={screeners} />;
      case 'strategy': return <StrategyView />;
      case 'monitor': return <Monitor />;
      default: return <ScreenersView screeners={screeners} loading={loading} />;
    }
  };

  return (
    <div className="wsj-dashboard">
      <header className="market-bar">
        <div className="market-ticker">
          <span className="index">上证指数 <span className="up">+0.85%</span></span>
          <span className="index">深证成指 <span className="up">+1.12%</span></span>
          <span className="index">创业板指 <span className="down">-0.23%</span></span>
          <span className="time">{new Date().toLocaleTimeString()}</span>
        </div>
        <h1 className="logo">NEO TERMINAL</h1>
      </header>

      <div className="main-layout">
        <nav className="sidebar">
          {menuItems.map(item => (
            <div key={item.id} className={`menu-item ${activeTab === item.id ? 'active' : ''}`} onClick={() => handleTabChange(item.id)}>
              <span className="icon">{item.icon}</span>
              <span className="label">{item.label}</span>
            </div>
          ))}
        </nav>

        <main className="content">{renderContent()}</main>
      </div>
    </div>
  );
}

// Dashboard
function DashboardView() {
  const [stats, setStats] = useState({ screeners: 18, oneil: 5, lastUpdate: 'Loading...' });
  const [accessStats, setAccessStats] = useState<{today: {date: string, unique_visitors: number}, this_month: {start_date: string, end_date: string, unique_visitors: number}} | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(d => {
      if (d.data_date) setStats(s => ({ ...s, lastUpdate: d.data_date }));
    }).catch(() => setStats(s => ({ ...s, lastUpdate: 'N/A' })));
    
    // Fetch access statistics
    fetch(`${API_BASE}/stats/access`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(d => {
        if (d.success && d.data) {
          setAccessStats(d.data);
        }
      })
      .catch(() => {});
  }, []);

  return (
    <div>
      <div className="page-header">
        <h2>Market Dashboard</h2>
        <span className="subtitle">Real-time market overview</span>
      </div>
      <div className="dashboard-stats">
        <div className="stat-card"><div className="stat-value">{stats.screeners}</div><div className="stat-label">Active Screeners</div></div>
        <div className="stat-card"><div className="stat-value">{stats.oneil}</div><div className="stat-label">O'Neil Patterns</div></div>
        <div className="stat-card"><div className="stat-value">{stats.lastUpdate}</div><div className="stat-label">Data Date</div></div>
      </div>
      
      {/* Access Statistics */}
      {accessStats && (
        <div style={{ marginTop: '32px' }}>
          <div className="page-header">
            <h3>👁️ Unique Visitors</h3>
            <span className="subtitle">Distinct IP count (excluding local access)</span>
          </div>
          <div className="dashboard-stats">
            <div className="stat-card" style={{ borderLeft: '4px solid #28a745' }}>
              <div className="stat-value" style={{ fontSize: '32px', color: '#28a745' }}>{accessStats.today.unique_visitors}</div>
              <div className="stat-label">Today's Visitors</div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid #007bff' }}>
              <div className="stat-value" style={{ fontSize: '32px', color: '#007bff' }}>{accessStats.this_month.unique_visitors}</div>
              <div className="stat-label">This Month</div>
            </div>
            <div className="stat-card" style={{ borderLeft: '4px solid #6c757d' }}>
              <div className="stat-value" style={{ fontSize: '20px', color: '#6c757d' }}>{accessStats.today.date}</div>
              <div className="stat-label">Last Updated</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Screeners with real functionality
function ScreenersView({ screeners, loading }: { screeners: Screener[], loading: boolean }) {
  const [checkModal, setCheckModal] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });
  const [runModal, setRunModal] = useState<{open: boolean, screener: Screener | null}>({ open: false, screener: null });

  return (
    <div>
      <div className="page-header">
        <h2>Stock Screeners</h2>
        <span className="count">{screeners.length} Strategies Available</span>
      </div>

      {loading ? <div className="loading">Loading screeners...</div> : (
        <div className="screener-grid">
          {screeners.map(s => (
            <div key={s.id} className="screener-card">
              <div className="card-header">
                <h3>{s.display_name || s.name}</h3>
                <span className="category">{s.category}</span>
              </div>
              <p className="description">{s.description?.substring(0, 120) || 'Technical analysis screener'}...</p>
              <div className="card-actions">
                <button className="btn-primary" onClick={() => setRunModal({ open: true, screener: s })}>Run Screener</button>
                <button className="btn-secondary" onClick={() => setCheckModal({ open: true, screener: s })}>Check Stock</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {checkModal.open && checkModal.screener && (
        <CheckStockModal screener={checkModal.screener} onClose={() => setCheckModal({ open: false, screener: null })} />
      )}
      {runModal.open && runModal.screener && (
        <RunScreenerModal screener={runModal.screener} onClose={() => setRunModal({ open: false, screener: null })} />
      )}
    </div>
  );
}

// Check Stock Modal - REAL FUNCTIONALITY
function CheckStockModal({ screener, onClose }: { screener: Screener, onClose: () => void }) {
  const [code, setCode] = useState('');
  // Initialize with today's date
  const [date, setDate] = useState(getTodayString());
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState('');

  const handleCheck = async () => {
    if (!code) return;

    // 格式化输入
    const formattedCode = formatStockCode(code);
    const formattedDate = formatDate(date);

    // 验证
    if (!isValidStockCode(formattedCode)) {
      setError('股票代码格式无效，请输入6位数字');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/check-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: JSON.stringify({ screener: screener.name, code: formattedCode, date: formattedDate })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Failed to check stock');
    }
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>🔍 Check Single Stock</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label>Screener: <strong>{screener.display_name}</strong></label>
          </div>
          <div className="form-row" onSubmit={(e) => e.preventDefault()}>
            <input type="text" placeholder="Stock Code (e.g. 600000)" value={code} onChange={e => setCode(e.target.value)} className="wsj-input" autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck="false" />
            <CalendarWithButton
              value={date}
              onChange={setDate}
              maxDate={new Date().toISOString().split('T')[0]}
              showPicker={showCalendar}
              onTogglePicker={() => setShowCalendar(!showCalendar)}
              onSelectDate={(d) => { setDate(d); setShowCalendar(false); }}
            />
            <button className="btn-primary" onClick={handleCheck} disabled={loading}>
              {loading ? 'Checking...' : 'Check'}
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}

          {result && (
            <div className={`result-box ${result.match ? 'success' : 'fail'}`}>
              <div className="result-header">
                <span className="result-icon">{result.match ? '✅' : '❌'}</span>
                <span className="result-text">{result.match ? 'MATCH' : 'NO MATCH'}</span>
              </div>
              <div className="result-details">
                <div><strong>Code:</strong> {result.code}</div>
                <div><strong>Name:</strong> {result.name}</div>
                <div><strong>Date:</strong> {result.date}</div>
              </div>
              {!result.match && result.reasons?.length > 0 && (
                <div className="fail-reasons">
                  <strong>Reasons:</strong>
                  <ul>{result.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
                </div>
              )}
              {result.match && Object.keys(result.details).length > 0 && (
                <div className="match-details">
                  <strong>Details:</strong>
                  <pre>{JSON.stringify(result.details, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Run Screener Modal - REAL FUNCTIONALITY
function RunScreenerModal({ screener, onClose }: { screener: Screener, onClose: () => void }) {
  // Initialize with today's date
  const [date, setDate] = useState(getTodayString());
  const [showCalendar, setShowCalendar] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [stocks, setStocks] = useState<any[]>([]);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Final validation and formatting
      const formattedDate = toISODate(date);

      if (!isValidDate(formattedDate)) {
        setError('日期格式无效，请使用 YYYY-MM-DD 格式 (例如: 2026-03-20)');
        setLoading(false);
        return;
      }

      console.log('Making fetch request with date:', formattedDate);
      
      const body = JSON.stringify({ date: formattedDate });
      console.log('Request body:', body);
      
      const res = await fetch(`${API_BASE}/screeners/${screener.name}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: body
      });
      
      console.log('Got response, status:', res.status);
      
      // Debug: log the raw response
      const rawText = await res.text();
      console.log('Raw response:', rawText.substring(0, 200));
      
      let data;
      try {
        data = JSON.parse(rawText);
      } catch (parseErr: any) {
        console.error('JSON parse error:', parseErr);
        console.error('Raw text was:', rawText);
        setError('Parse error: ' + rawText.substring(0, 50));
        setLoading(false);
        return;
      }
      
      console.log('Parsed data:', data);
      
      if (data.error) throw new Error(data.message || data.error);
      setResult(data);

      // Fetch results for download
      if (data.success) {
        console.log('Fetching results...');
        try {
          const resultsUrl = `${API_BASE}/results?screener=${encodeURIComponent(screener.name)}&date=${encodeURIComponent(formattedDate)}`;
          console.log('Results URL:', resultsUrl);
          const resultsRes = await fetch(resultsUrl, {
            headers: { 'Authorization': AUTH_HEADER }
          });
          console.log('Got results response, status:', resultsRes.status);
          
          if (!resultsRes.ok) {
            const errorText = await resultsRes.text();
            console.error('Results fetch failed:', errorText);
            setError(`Failed to fetch results: ${resultsRes.status} - ${errorText.substring(0, 100)}`);
            setLoading(false);
            return;
          }
          
          // Read raw text first to debug any JSON issues
          const resultsText = await resultsRes.text();
          console.log('Raw results response:', resultsText.substring(0, 500));
          
          let resultsData;
          try {
            resultsData = JSON.parse(resultsText);
          } catch (parseErr: any) {
            console.error('JSON parse error:', parseErr);
            console.error('Full response text:', resultsText);
            setError(`JSON parse error: ${parseErr.message}. Response: ${resultsText.substring(0, 200)}`);
            setLoading(false);
            return;
          }
          console.log('Parsed results data:', resultsData);

          // Handle daily_hot_cold_screener which returns {hot: [], cold: []}
          if (screener.name === 'daily_hot_cold_screener' && (resultsData.hot !== undefined || resultsData.cold !== undefined)) {
            // Combine hot and cold with type marker
            const hotStocks = (resultsData.hot || []).map((s: any) => ({ ...s, _type: 'hot', _category: '热股' }));
            const coldStocks = (resultsData.cold || []).map((s: any) => ({ ...s, _type: 'cold', _category: '冷股' }));
            console.log('Setting stocks:', hotStocks.length + coldStocks.length);
            setStocks([...hotStocks, ...coldStocks]);
          } else {
            setStocks(resultsData.results || []);
          }
        } catch (fetchErr: any) {
          console.error('Error fetching results:', fetchErr);
          setError(`Error fetching results: ${fetchErr.message}`);
        }
      }
      console.log('Success!');
    } catch (e: any) {
      console.error('Run screener error:', e);
      console.error('Error stack:', e.stack);
      setError(e.message || 'Failed to run screener');
    }
    setLoading(false);
  };

  // Download handlers for screener results
  const downloadCSV = () => {
    if (stocks.length === 0) return;

    // Get all columns
    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    // Priority columns first
    const priorityCols = ['stock_code', 'stock_name', 'code', 'name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    // Header translations
    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'code': '代码',
      'stock_name': '名称', 'name': '名称',
      'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pe': '市盈率',
      'pb_ratio': '市净率', 'pb': '市净率',
      'listing_date': '上市日期'
    };

    const headers = columns.map(col => headerMap[col] || col).join(',');
    const rows = stocks.map(row => {
      const flatData = flattenObject(row);
      return columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '';
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',');
    });

    const csvContent = '\uFEFF' + [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const downloadExcel = () => {
    if (stocks.length === 0) return;

    const flatRow = flattenObject(stocks[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    const priorityCols = ['stock_code', 'stock_name', 'code', 'name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    const headerMap: Record<string, string> = {
      'stock_code': '代码', 'code': '代码',
      'stock_name': '名称', 'name': '名称',
      'close_price': '收盘价', 'close': '收盘价',
      'pct_change': '涨幅%', 'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值', 'circulating_cap': '流通市值',
      'pe_ratio': '市盈率', 'pe': '市盈率',
      'pb_ratio': '市净率', 'pb': '市净率',
      'listing_date': '上市日期'
    };

    let html = '<table border="1">';
    html += '<tr>' + columns.map(col => `<th>${headerMap[col] || col}</th>`).join('') + '</tr>';
    stocks.forEach(row => {
      const flatData = flattenObject(row);
      html += '<tr>' + columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '<td></td>';
        return `<td>${val}</td>`;
      }).join('') + '</tr>';
    });
    html += '</table>';

    const blob = new Blob([`
      <html xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:x="urn:schemas-microsoft-com:office:excel"
            xmlns="http://www.w3.org/TR/REC-html40">
        <head><meta charset="UTF-8"></head>
        <body>${html}</body>
      </html>
    `], { type: 'application/vnd.ms-excel;charset=utf-8' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screener.name}_${date}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>▶ Run Screener</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row" onSubmit={(e) => e.preventDefault()}>
            <label>Screener: <strong>{screener.display_name}</strong></label>
            <CalendarWithButton
              value={date}
              onChange={setDate}
              maxDate={new Date().toISOString().split('T')[0]}
              showPicker={showCalendar}
              onTogglePicker={() => setShowCalendar(!showCalendar)}
              onSelectDate={(d) => { setDate(d); setShowCalendar(false); }}
            />
            <button className="btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? 'Running...' : 'Run'}
            </button>
          </div>
          {error && <div className="error-message">{error}</div>}
          {result && (
            <div className={`result-box ${result.success ? 'success' : 'fail'}`}>
              <div className="result-header">
                <span className="result-icon">{result.success ? '✅' : '❌'}</span>
                <span className="result-text">{result.success ? 'SUCCESS' : 'FAILED'}</span>
              </div>
              <div className="result-details">
                <div><strong>Run ID:</strong> {result.run_id}</div>
                <div><strong>Stocks Found:</strong> {result.stocks_found || 0}</div>
                <div><strong>Message:</strong> {result.message}</div>
              </div>
              {result.success && (
                <div className="download-actions" style={{
                  marginTop: '16px',
                  paddingTop: '16px',
                  borderTop: '1px solid var(--border-color)',
                  backgroundColor: '#f0f9ff',
                  padding: '12px',
                  borderRadius: '8px'
                }}>
                  <div style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                    Loaded {stocks.length} stocks for download
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                    <button 
                      className="btn-csv-primary" 
                      onClick={() => {
                        console.log('CSV click - stocks:', stocks.length, stocks);
                        downloadCSV();
                      }}
                      disabled={stocks.length === 0}
                      title={stocks.length === 0 ? 'No data to download' : 'Download CSV'}
                    >
                      📄 Download CSV {stocks.length > 0 && `(${stocks.length})`}
                    </button>
                    <button 
                      className="btn-excel-secondary" 
                      onClick={() => {
                        console.log('Excel click - stocks:', stocks.length, stocks);
                        downloadExcel();
                      }}
                      disabled={stocks.length === 0}
                      title={stocks.length === 0 ? 'No data to download' : 'Download Excel'}
                    >
                      📊 Excel {stocks.length > 0 && `(${stocks.length})`}
                    </button>
                    <button
                      className="btn-view-results"
                      onClick={() => {
                        window.location.href = `?tab=results&screener=${screener.name}&date=${formatDate(date)}`;
                      }}
                      style={{ backgroundColor: '#3b82f6', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
                    >
                      👁️ View Results
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Tooltip component
function Tooltip({ text, children }: { text: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}
         onMouseEnter={() => setShow(true)}
         onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <div style={{
          position: 'absolute',
          bottom: '100%',
          left: '50%',
          transform: 'translateX(-50%)',
          background: 'var(--um-blue)',
          color: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          fontSize: '12px',
          whiteSpace: 'nowrap',
          zIndex: 1000,
          marginBottom: '8px',
          boxShadow: '0 4px 12px rgba(0,39,76,0.3)',
        }}>
          {text}
          <div style={{
            position: 'absolute',
            top: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            border: '6px solid transparent',
            borderTopColor: 'var(--um-blue)',
          }} />
        </div>
      )}
    </div>
  );
}

// Helper function to flatten nested objects
function flattenObject(obj: any, prefix = ''): any {
  let result: any = {};
  for (const key in obj) {
    if (obj.hasOwnProperty(key)) {
      const newKey = prefix ? `${prefix}.${key}` : key;
      if (obj[key] !== null && typeof obj[key] === 'object' && !Array.isArray(obj[key])) {
        Object.assign(result, flattenObject(obj[key], newKey));
      } else {
        result[newKey] = obj[key];
      }
    }
  }
  return result;
}

// Stock Chart Modal Component - ECharts Candlestick
function StockChartModal({ code, name, onClose }: { code: string, name: string, onClose: () => void }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    // 延迟初始化，确保弹窗完全显示且有尺寸
    const timer = setTimeout(() => {
      fetch(`${API_BASE}/stock/${code}/chart?days=60`, {
        headers: { 'Authorization': AUTH_HEADER }
      })
        .then(r => r.json())
        .then(data => {
          if (data.error) throw new Error(data.error);
          if (data.data && data.data.length > 0) {
            // 再等待一下确保容器渲染完成
            setTimeout(() => renderChart(data.data), 200);
          } else {
            setError('无K线数据');
            setLoading(false);
          }
        })
        .catch(e => {
          setError(e.message);
          setLoading(false);
        });
    }, 300); // 等待弹窗动画完成

    return () => {
      clearTimeout(timer);
      if (chartInstance.current) {
        chartInstance.current.dispose();
      }
    };
  }, [code]);

  const renderChart = (data: any[]) => {
    if (!chartRef.current) {
      console.error('Chart container ref not available');
      setError('图表容器加载失败');
      setLoading(false);
      return;
    }

    // 强制使用固定尺寸渲染，不依赖容器实际尺寸
    forceRenderChart(data);
  };

  const forceRenderChart = (data: any[]) => {
    if (!chartRef.current) return;

    const dates = data.map(d => d.date);
    const values = data.map(d => [d.open, d.close, d.low, d.high]);
    const volumes = data.map(d => d.volume);

    console.log('Initializing chart with', dates.length, 'data points');

    // 如果已有实例，先销毁
    if (chartInstance.current) {
      chartInstance.current.dispose();
    }

    try {
      chartInstance.current = echarts.init(chartRef.current);

      const option: echarts.EChartsOption = {
        backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' }
      },
      grid: [
        { left: '10%', right: '8%', height: '50%' },
        { left: '10%', right: '8%', top: '68%', height: '16%' }
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          type: 'category',
          gridIndex: 1,
          data: dates,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8' }
        },
        {
          scale: true,
          gridIndex: 1,
          axisLine: { lineStyle: { color: '#94a3b8' } },
          splitLine: { lineStyle: { color: '#334155' } },
          axisLabel: { color: '#94a3b8' }
        }
      ],
      dataZoom: [
        { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
        { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100, bottom: 10 }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: values,
          itemStyle: {
            color: '#ef4444',
            color0: '#10b981',
            borderColor: '#ef4444',
            borderColor0: '#10b981'
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: volumes,
          itemStyle: {
            color: (params: any) => {
              const dataIndex = params.dataIndex;
              const close = values[dataIndex][1];
              const open = values[dataIndex][0];
              return close >= open ? '#ef4444' : '#10b981';
            }
          }
        }
      ]
    };

    chartInstance.current.setOption(option);

    // 图表渲染完成后再关闭 loading
    requestAnimationFrame(() => {
      setLoading(false);
    });

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
    } catch (e: any) {
      console.error('Chart initialization error:', e);
      setError('图表渲染失败: ' + (e.message || 'Unknown error'));
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()} style={{ maxWidth: '900px' }}>
        <div className="modal-header">
          <h3>📈 {code} {name} - K线图</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body" style={{ minHeight: '540px' }}>
          {loading && <div className="loading">加载K线数据中...</div>}
          {error && <div className="error-message">{error}</div>}
          <div
            ref={chartRef}
            style={{
              width: '100%',
              height: '500px',
              minHeight: '500px',
              visibility: loading || error ? 'hidden' : 'visible'
            }}
          />
        </div>
      </div>
    </div>
  );
}

// Results Table Component - dynamically renders any data structure
function ResultsTable({ data, onStockClick }: { data: any[], onStockClick?: (code: string, name: string) => void }) {
  if (!data || data.length === 0) return null;

  const flatRow = flattenObject(data[0]);
  const columns = Object.keys(flatRow);

  let displayColumns = columns.filter(col =>
    !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
  );

  const priorityCols = ['stock_code', 'stock_name'];
  displayColumns = [
    ...priorityCols.filter(c => displayColumns.includes(c)),
    ...displayColumns.filter(c => !priorityCols.includes(c))
  ];

  const formatHeader = (col: string) => {
    const translations: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'preclose': '昨收',
      'open': '开盘',
      'high': '最高',
      'low': '最低',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'industry': '行业',
      'sector': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'listing_date': '上市日期',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pe': '市盈率',
      'pb_ratio': '市净率',
      'pb': '市净率',
      'extra_data.cup_depth_pct': '杯深%',
      'extra_data.handle_date': '柄部日期',
      'extra_data.days_apart': '间隔天数',
      'extra_data.days_since_handle': '距柄部天数',
      'extra_data.volume_ratio': '量比',
      'extra_data.handle_price': '柄部价格',
      'extra_data.cup_rim_price': '杯沿价格',
      'extra_data.price_diff_pct': '价格差异%',
      'extra_data.breakout_price': '突破价',
      'extra_data.breakout_pct': '突破%',
      'extra_data.total_limit_up': '累计涨停',
      'extra_data.total_limit_down': '累计跌停',
      'extra_data.pe': '市盈率',
      'extra_data.pb': '市净率',
      'extra_data.market_cap': '市值',
      'extra_data.industry': '行业',
      'extra_data.anomaly_type': '异动类型',
      'extra_data.board': '板块',
      'extra_data.anomaly_reason': '异动原因',
      'extra_data.limit_up_days': '涨停天数',
      'extra_data.return_5d': '5日涨幅%',
      'extra_data.return_10d': '10日涨幅%',
      'extra_data.return_20d': '20日涨幅%',
      'extra_data.return_60d': '60日涨幅%',
      // 每日热冷股特有字段
      'extra_data._category': '类别',
      'extra_data._type': '类型',
      'extra_data.amount': '成交额',
      'extra_data.circulating_cap': '流通市值',
      'extra_data.total_market_cap': '总市值',
      'extra_data.listing_date': '上市日期',
      'created_at': '创建时间',
      'updated_at': '更新时间',
      // 全大写版本（后端返回的格式）
      'CATEGORY': '类别',
      'TYPE': '类型',
      'BOARD': '板块',
      'INDUSTRY': '行业',
      'SECTOR': '板块',
      'REASON': '原因',
      'SIGNAL': '信号',
      'STATUS': '状态',
      'SCORE': '评分',
      'RANK': '排名',
      'NOTE': '备注',
      'AMOUNT': '成交额',
      'VOLUME': '成交量',
      'CLOSE_PRICE': '收盘价',
      'CLOSE': '收盘价',
      'PCT_CHANGE': '涨幅%',
      'CHANGE': '涨幅%',
      'TURNOVER': '换手率%',
      'OPEN': '开盘',
      'HIGH': '最高',
      'LOW': '最低',
      'PRE_CLOSE': '昨收',
      'LISTING_DATE': '上市日期',
      'TOTAL_MARKET_CAP': '总市值',
      'CIRCULATING_MARKET_CAP': '流通市值',
      'CIRCULATING_CAP': '流通市值',
      'PE_RATIO': '市盈率',
      'PE': '市盈率',
      'PB_RATIO': '市净率',
      'PB': '市净率',
      'STOCK_CODE': '代码',
      'STOCK_NAME': '名称'
    };
    return translations[col] || translations[col.toLowerCase()] || translations[col.toUpperCase()] || col.replace(/_/g, ' ').replace(/\./g, ' ').replace(/^extra data/, '');
  };

  const formatValue = (val: any, col: string): string => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      if (col.includes('pct') || col.includes('ratio') || col.includes('change')) {
        return val.toFixed(2) + '%';
      }
      if (!Number.isInteger(val)) {
        return val.toFixed(2);
      }
      return val.toLocaleString();
    }
    return String(val);
  };

  const isStockCode = (col: string) => col === 'stock_code' || col === 'code';

  return (
    <table className="result-table">
      <thead>
        <tr>
          {displayColumns.map(col => (
            <th key={col}>{formatHeader(col)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => {
          const flatData = flattenObject(row);
          const stockCode = flatData['stock_code'] || flatData['code'];
          const stockName = flatData['stock_name'] || flatData['name'];
          return (
            <tr key={i}>
              {displayColumns.map(col => (
                <td key={col}>
                  {isStockCode(col) && onStockClick ? (
                    <span
                      className="stock-code-link"
                      onClick={() => onStockClick(stockCode, stockName)}
                      style={{ cursor: 'pointer', color: '#00274C', fontWeight: 600, textDecoration: 'underline' }}
                    >
                      {formatValue(flatData[col], col)}
                    </span>
                  ) : (
                    formatValue(flatData[col], col)
                  )}
                </td>
              ))}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// Results View with real query
function ResultsView({ screeners }: { screeners: Screener[] }) {
  // Initialize with today's date or URL param
  const [date, setDate] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const urlDate = params.get('date');
    return (urlDate && isValidDate(urlDate)) ? urlDate : getTodayString();
  });
  const [showCalendar, setShowCalendar] = useState(false);
  const [screenerName, setScreenerName] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const urlScreener = params.get('screener');
    return urlScreener || (screeners[0]?.name || '');
  });
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState('');
  const [selectedStock, setSelectedStock] = useState<{code: string, name: string} | null>(null);
  const [autoQueried, setAutoQueried] = useState(false);

  // 如果有 URL 参数，自动查询
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('tab') === 'results' && params.get('screener') && !autoQueried) {
      setAutoQueried(true);
      handleQuery();
    }
  }, []);

  const handleQuery = async () => {
    if (!screenerName) {
      setError('请选择一个筛选器');
      return;
    }
    setLoading(true);
    setError('');
    try {
      // 统一格式化日期
      console.log('ResultsView - date before format:', date);
      let formattedDate;
      try {
        formattedDate = formatDate(date);
      } catch (fmtErr: any) {
        console.error('Format error:', fmtErr);
        setError('日期格式化错误: ' + fmtErr.message);
        setLoading(false);
        return;
      }
      console.log('ResultsView - formatted date:', formattedDate);
      
      const params = new URLSearchParams({ screener: screenerName, date: formattedDate });
      const res = await fetch(`${API_BASE}/results?${params}`, { headers: { 'Authorization': AUTH_HEADER }});
      const data = await res.json();
      if (data.error) throw new Error(data.error);

      // Handle daily_hot_cold_screener which returns {hot: [], cold: []}
      if (screenerName === 'daily_hot_cold_screener' && (data.hot !== undefined || data.cold !== undefined)) {
        try {
          const hotArr = data.hot || [];
          const coldArr = data.cold || [];
          console.log('Processing hot/cold data:', hotArr.length, coldArr.length);
          const hotResults = hotArr.map((s: any) => ({ ...s, _type: 'hot', _category: '热股' }));
          const coldResults = coldArr.map((s: any) => ({ ...s, _type: 'cold', _category: '冷股' }));
          console.log('Mapped results:', hotResults.length + coldResults.length);
          setResults([...hotResults, ...coldResults]);
        } catch (mapErr: any) {
          console.error('Hot/Cold mapping error:', mapErr);
          setError('数据处理错误: ' + mapErr.message);
          setResults([]);
        }
      } else {
        setResults(data.results || []);
      }
    } catch (e: any) {
      setError(e.message || '获取结果失败');
      setResults([]);
    }
    setLoading(false);
  };

  // 下载 CSV 功能 - Primary option
  const downloadCSV = () => {
    if (results.length === 0) return;

    // 获取所有列
    const flatRow = flattenObject(results[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    // 股票代码和名称放最前面
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    // 表头翻译
    const headerMap: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pb_ratio': '市净率',
      'listing_date': '上市日期'
    };

    // 构建 CSV 内容
    const headers = columns.map(col => headerMap[col] || col).join(',');
    const rows = results.map(row => {
      const flatData = flattenObject(row);
      return columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '';
        // Escape values with commas or quotes
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',');
    });

    const csvContent = '\uFEFF' + [headers, ...rows].join('\n'); // Add BOM for Excel Chinese support

    // 下载
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screenerName}_${date}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 下载 Excel 功能 - Secondary option
  const downloadExcel = () => {
    if (results.length === 0) return;

    // 获取所有列
    const flatRow = flattenObject(results[0]);
    let columns = Object.keys(flatRow).filter(col =>
      !['id', 'run_id', 'created_at', 'updated_at', 'is_deleted'].includes(col)
    );

    // 股票代码和名称放最前面
    const priorityCols = ['stock_code', 'stock_name'];
    columns = [
      ...priorityCols.filter(c => columns.includes(c)),
      ...columns.filter(c => !priorityCols.includes(c))
    ];

    // 表头翻译
    const headerMap: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'close': '收盘价',
      'pct_change': '涨幅%',
      'change': '涨幅%',
      'turnover': '换手率%',
      'volume': '成交量',
      'amount': '成交额',
      'industry': '行业',
      'category': '类别',
      'type': '类型',
      'board': '板块',
      'reason': '原因',
      'signal': '信号',
      'status': '状态',
      'score': '评分',
      'rank': '排名',
      'note': '备注',
      'total_market_cap': '总市值',
      'circulating_market_cap': '流通市值',
      'circulating_cap': '流通市值',
      'pe_ratio': '市盈率',
      'pb_ratio': '市净率',
      'listing_date': '上市日期'
    };

    // 构建 HTML table (Excel 可以打开)
    let html = '<table border="1">';
    html += '<tr>' + columns.map(col => `<th>${headerMap[col] || col}</th>`).join('') + '</tr>';

    results.forEach(row => {
      const flatData = flattenObject(row);
      html += '<tr>' + columns.map(col => {
        const val = flatData[col];
        if (val === null || val === undefined) return '<td></td>';
        return `<td>${val}</td>`;
      }).join('') + '</tr>';
    });

    html += '</table>';

    // 下载为 Excel (正确的 MIME 类型)
    const blob = new Blob([`
      <html xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:x="urn:schemas-microsoft-com:office:excel"
            xmlns="http://www.w3.org/TR/REC-html40">
        <head>
          <meta charset="UTF-8">
          <!--[if gte mso 9]>
          <xml>
            <x:ExcelWorkbook>
              <x:ExcelWorksheets>
                <x:ExcelWorksheet>
                  <x:Name>筛选结果</x:Name>
                  <x:WorksheetOptions>
                    <x:DisplayGridlines/>
                  </x:WorksheetOptions>
                </x:ExcelWorksheet>
              </x:ExcelWorksheets>
            </x:ExcelWorkbook>
          </xml>
          <![endif]-->
        </head>
        <body>${html}</body>
      </html>
    `], { type: 'application/vnd.ms-excel;charset=utf-8' });

    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${screenerName}_${date}.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <div className="page-header">
        <h2>筛选结果</h2>
        <span className="subtitle">查看历史筛选结果</span>
      </div>

      <div className="query-form" onSubmit={(e) => e.preventDefault()}>
        <CalendarWithButton
          value={date}
          onChange={setDate}
          maxDate={new Date().toISOString().split('T')[0]}
          showPicker={showCalendar}
          onTogglePicker={() => setShowCalendar(!showCalendar)}
          onSelectDate={(d) => { setDate(d); setShowCalendar(false); }}
        />
        <select value={screenerName} onChange={e => setScreenerName(e.target.value)} className="wsj-select">
          <option value="" disabled>选择筛选器...</option>
          {screeners.map(s => <option key={s.id} value={s.name}>{s.display_name}</option>)}
        </select>
        <button className="btn-primary" onClick={handleQuery} disabled={loading || !screenerName}>
          {loading ? '查询中...' : '查看结果'}
        </button>
      </div>

      {error && <div className="error-message" style={{ marginBottom: '16px' }}>{error}</div>}

      {results.length > 0 ? (
        <>
          <div className="download-bar">
            <span className="record-count">共 {results.length} 条记录</span>
            <div className="download-buttons">
              <Tooltip text="CSV works with all Excel versions">
                <button className="btn-csv-primary" onClick={downloadCSV}>
                  📄 Download CSV (Recommended)
                </button>
              </Tooltip>
              <button className="btn-excel-secondary" onClick={downloadExcel}>
                📊 Download Excel
              </button>
            </div>
          </div>
          <div className="results-table-container">
            <ResultsTable data={results} onStockClick={(code, name) => setSelectedStock({code, name})} />
          </div>
        </>
      ) : (
        <div className="placeholder">{loading ? '加载中...' : '无结果。选择日期并点击查看结果。'}</div>
      )}

      {selectedStock && (
        <StockChartModal
          code={selectedStock.code}
          name={selectedStock.name}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  );
}
// Strategy Evolution View - Lab Dashboard Style
function StrategyView() {
  const [backtests, setBacktests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedBacktest, setSelectedBacktest] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [tradeSummary, setTradeSummary] = useState<any>(null);
  const [loadingTrades, setLoadingTrades] = useState(false);
  const [activePhase, setActivePhase] = useState<'idle' | 'running' | 'analyzing'>('idle');

  useEffect(() => {
    fetch(`${API_BASE}/strategy/backtests`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(data => {
        setBacktests(data.backtests || []);
        setLoading(false);
        // Check if autoresearch is running
        if ((data.backtests || []).length > 0) {
          const latest = data.backtests[data.backtests.length - 1];
          const latestTime = new Date(latest.created_at).getTime();
          const now = new Date().getTime();
          // If latest result is within last 5 minutes, consider it running
          if (now - latestTime < 5 * 60 * 1000) {
            setActivePhase('running');
          }
        }
      })
      .catch(() => setLoading(false));
    
    // Poll every 30 seconds
    const interval = setInterval(() => {
      fetch(`${API_BASE}/strategy/backtests`, { headers: { 'Authorization': AUTH_HEADER }})
        .then(r => r.json())
        .then(data => {
          setBacktests(data.backtests || []);
        });
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const loadTrades = (backtestId: number, backtest: any) => {
    setLoadingTrades(true);
    setSelectedBacktest(backtest);
    fetch(`${API_BASE}/strategy/trades/${backtestId}`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(data => {
        setTrades(data.trades || []);
        setTradeSummary(data.summary || null);
        setLoadingTrades(false);
      })
      .catch(() => setLoadingTrades(false));
  };

  // Calculate metrics
  const bestSharpe = backtests.length > 0 ? Math.max(...backtests.map(b => b.sharpe_ratio)) : 0;
  const bestReturn = backtests.length > 0 ? Math.max(...backtests.map(b => b.total_return)) : 0;
  
  // Progress to profitability (from -2 to 0)
  const progressToProfit = Math.min(100, Math.max(0, ((bestSharpe + 2) / 2) * 100));
  
  // Current generation
  const currentGen = backtests.length;
  
  // Phase determination
  const getPhase = () => {
    if (currentGen === 0) return { name: 'INITIALIZING', color: '#6c757d', step: 0 };
    if (bestSharpe > 0) return { name: 'PROFITABLE', color: '#28a745', step: 4 };
    if (bestSharpe > -0.5) return { name: 'OPTIMIZING', color: '#ffc107', step: 3 };
    if (currentGen > 50) return { name: 'ITERATING', color: '#17a2b8', step: 2 };
    return { name: 'BASELINE', color: '#007bff', step: 1 };
  };
  
  const phase = getPhase();

  // Chart data
  const chartData = backtests.map((b, idx) => ({
    generation: b.strategy_version,
    sharpe: b.sharpe_ratio,
    return: b.total_return * 100,
    drawdown: b.max_drawdown * 100,
    trades: b.total_trades,
    idx: idx + 1
  }));

  useEffect(() => {
    if (chartData.length === 0) return;

    const chartDom = document.getElementById('strategy-evolution-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom, 'dark');
    const option = {
      backgroundColor: 'transparent',
      title: { 
        text: 'EVOLUTION TRAJECTORY', 
        left: 'center',
        textStyle: { color: '#00274C', fontSize: 14, fontWeight: 'bold' }
      },
      tooltip: { 
        trigger: 'axis',
        backgroundColor: 'rgba(0,39,76,0.9)',
        borderColor: '#FFCB05',
        textStyle: { color: '#fff' }
      },
      legend: { 
        data: ['Sharpe Ratio', 'Return %', 'Max Drawdown %'], 
        bottom: 0,
        textStyle: { color: '#00274C' }
      },
      grid: { left: '10%', right: '10%', bottom: '15%', top: '15%' },
      xAxis: { 
        type: 'category', 
        data: chartData.map(d => d.generation),
        axisLabel: { color: '#666', fontSize: 10, rotate: 45 },
        axisLine: { lineStyle: { color: '#dee2e6' } }
      },
      yAxis: [
        { 
          type: 'value', 
          name: 'Sharpe',
          position: 'left',
          nameTextStyle: { color: '#00274C' },
          axisLabel: { color: '#666' },
          splitLine: { lineStyle: { color: '#f0f0f0' } }
        },
        { 
          type: 'value', 
          name: '%',
          position: 'right',
          nameTextStyle: { color: '#00274C' },
          axisLabel: { color: '#666' },
          splitLine: { show: false }
        }
      ],
      series: [
        {
          name: 'Sharpe Ratio',
          type: 'line',
          data: chartData.map(d => d.sharpe),
          smooth: true,
          itemStyle: { color: '#00274C' },
          lineStyle: { width: 3 },
          markLine: { 
            silent: true,
            data: [{ yAxis: 0, label: { formatter: 'PROFIT LINE', color: '#28a745' }, lineStyle: { type: 'dashed', color: '#28a745', width: 2 } }] 
          }
        },
        {
          name: 'Return %',
          type: 'line',
          yAxisIndex: 1,
          data: chartData.map(d => d.return),
          smooth: true,
          itemStyle: { color: '#28a745' },
          lineStyle: { width: 2 }
        },
        {
          name: 'Max Drawdown %',
          type: 'line',
          yAxisIndex: 1,
          data: chartData.map(d => d.drawdown),
          smooth: true,
          itemStyle: { color: '#dc3545' },
          lineStyle: { width: 2, type: 'dashed' }
        }
      ]
    };
    chart.setOption(option);

    return () => chart.dispose();
  }, [backtests]);

  if (loading) return <div className="placeholder">INITIALIZING LAB...</div>;

  return (
    <div style={{ background: '#f8f9fa', minHeight: '100%' }}>
      {/* Lab Header */}
      <div style={{ 
        background: 'linear-gradient(135deg, #00274C 0%, #1a3a6b 100%)', 
        padding: '24px', 
        color: 'white',
        borderBottom: '4px solid #FFCB05'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '24px', fontWeight: 'bold', letterSpacing: '2px' }}>
              🧬 AUTORESEARCH LAB
            </h2>
            <div style={{ fontSize: '12px', opacity: 0.8, marginTop: '4px' }}>
              AI-DRIVEN STRATEGY EVOLUTION PROTOCOL v1.0
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ 
              display: 'inline-block',
              padding: '8px 16px', 
              background: phase.color, 
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 'bold',
              color: phase.step >= 3 ? '#00274C' : 'white'
            }}>
              PHASE: {phase.name}
            </div>
            <div style={{ fontSize: '11px', marginTop: '8px', opacity: 0.7 }}>
              GEN {currentGen} | SHARPE {bestSharpe.toFixed(3)}
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        {/* Phase Progress */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px', 
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
            {['BASELINE', 'ITERATING', 'OPTIMIZING', 'PROFITABLE'].map((p, i) => (
              <div key={p} style={{ 
                textAlign: 'center', 
                flex: 1,
                opacity: i <= phase.step ? 1 : 0.3
              }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  background: i <= phase.step ? phase.color : '#dee2e6',
                  color: i <= phase.step ? 'white' : '#666',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 8px',
                  fontWeight: 'bold',
                  fontSize: '14px'
                }}>
                  {i < phase.step ? '✓' : i + 1}
                </div>
                <div style={{ fontSize: '11px', fontWeight: 'bold', color: '#00274C' }}>{p}</div>
              </div>
            ))}
          </div>
          <div style={{ height: '4px', background: '#e9ecef', borderRadius: '2px' }}>
            <div style={{
              height: '100%',
              width: `${(phase.step / 3) * 100}%`,
              background: `linear-gradient(90deg, ${phase.color} 0%, #28a745 100%)`,
              borderRadius: '2px',
              transition: 'width 0.5s ease'
            }} />
          </div>
        </div>

        {/* Key Metrics Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
          {/* Sharpe Gauge */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>SHARPE RATIO</div>
            <div style={{ 
              fontSize: '32px', 
              fontWeight: 'bold', 
              color: bestSharpe > 0 ? '#28a745' : bestSharpe > -1 ? '#ffc107' : '#dc3545',
              fontFamily: 'SF Mono, monospace'
            }}>
              {bestSharpe.toFixed(3)}
            </div>
            <div style={{ marginTop: '8px', height: '6px', background: '#e9ecef', borderRadius: '3px' }}>
              <div style={{
                height: '100%',
                width: `${progressToProfit}%`,
                background: bestSharpe > 0 ? '#28a745' : '#ffc107',
                borderRadius: '3px'
              }} />
            </div>
            <div style={{ fontSize: '10px', color: '#666', marginTop: '4px' }}>
              {bestSharpe > 0 ? '✓ PROFITABLE' : `▼ ${(0 - bestSharpe).toFixed(3)} to break-even`}
            </div>
          </div>

          {/* Total Return */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>BEST RETURN</div>
            <div style={{ 
              fontSize: '32px', 
              fontWeight: 'bold', 
              color: bestReturn > 0 ? '#28a745' : '#dc3545',
              fontFamily: 'SF Mono, monospace'
            }}>
              {(bestReturn * 100).toFixed(2)}%
            </div>
            <div style={{ fontSize: '10px', color: '#666', marginTop: '8px' }}>
              {bestReturn > 0 ? '↑ ABOVE WATER' : '↓ UNDER WATER'}
            </div>
          </div>

          {/* Generations */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>GENERATIONS</div>
            <div style={{ fontSize: '32px', fontWeight: 'bold', color: '#00274C', fontFamily: 'SF Mono, monospace' }}>
              {currentGen}
            </div>
            <div style={{ fontSize: '10px', color: '#666', marginTop: '8px' }}>
              EXPERIMENTS RUN
            </div>
          </div>

          {/* Status */}
          <div style={{ background: 'white', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,39,76,0.08)' }}>
            <div style={{ fontSize: '11px', color: '#666', marginBottom: '8px', fontWeight: 'bold' }}>STATUS</div>
            <div style={{ 
              display: 'inline-block',
              padding: '8px 16px',
              background: activePhase === 'running' ? '#28a745' : '#6c757d',
              color: 'white',
              borderRadius: '4px',
              fontSize: '14px',
              fontWeight: 'bold'
            }}>
              {activePhase === 'running' ? '● RUNNING' : '○ IDLE'}
            </div>
            <div style={{ fontSize: '10px', color: '#666', marginTop: '8px' }}>
              {activePhase === 'running' ? 'Iterating...' : 'Waiting for next run'}
            </div>
          </div>
        </div>

        {/* Research Info Panel */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px', 
          marginBottom: '24px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)',
          borderLeft: '4px solid #00274C'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
            <div>
              <div style={{ fontSize: '10px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>TRAINING SET</div>
              <div style={{ fontSize: '14px', color: '#00274C' }}>2024-09-02 → 2025-08-31</div>
              <div style={{ fontSize: '11px', color: '#28a745', marginTop: '4px' }}>✓ 12 months for training</div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>VALIDATION SET</div>
              <div style={{ fontSize: '14px', color: '#00274C' }}>2025-09-01 → 2026-02-28</div>
              <div style={{ fontSize: '11px', color: '#dc3545', marginTop: '4px' }}>🔒 LOCKED (no peeking)</div>
            </div>
            <div>
              <div style={{ fontSize: '10px', color: '#666', fontWeight: 'bold', marginBottom: '8px' }}>METHODOLOGY</div>
              <div style={{ fontSize: '14px', color: '#00274C' }}>Single Variable Testing</div>
              <div style={{ fontSize: '11px', color: '#666', marginTop: '4px' }}>Git-based experiment tracking</div>
            </div>
          </div>
        </div>

        {/* Evolution Chart */}
        {chartData.length > 0 && (
          <div style={{ 
            background: 'white', 
            padding: '20px', 
            borderRadius: '12px', 
            marginBottom: '24px',
            boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
          }}>
            <div id="strategy-evolution-chart" style={{ width: '100%', height: '400px' }}></div>
          </div>
        )}

        {/* Experiments Table */}
        <div style={{ 
          background: 'white', 
          padding: '20px', 
          borderRadius: '12px',
          boxShadow: '0 2px 8px rgba(0,39,76,0.08)'
        }}>
          <h4 style={{ marginBottom: '16px', color: '#00274C', fontSize: '14px' }}>
            EXPERIMENT LOG (Click to view trades)
          </h4>
          <div style={{ maxHeight: '400px', overflow: 'auto' }}>
            <table style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                  <th style={{ padding: '12px', textAlign: 'left', fontWeight: 'bold', color: '#00274C' }}>GEN</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>SHARPE</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>RETURN</th>
                  <th style={{ padding: '12px', textAlign: 'right', fontWeight: 'bold', color: '#00274C' }}>DRAWDOWN</th>
                  <th style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#00274C' }}>TRADES</th>
                  <th style={{ padding: '12px', textAlign: 'center', fontWeight: 'bold', color: '#00274C' }}>TIMESTAMP</th>
                </tr>
              </thead>
              <tbody>
                {backtests.slice().reverse().map((b, idx) => (
                  <tr 
                    key={idx} 
                    onClick={() => loadTrades(b.id, b)}
                    style={{ 
                      cursor: 'pointer',
                      borderBottom: '1px solid #f0f0f0',
                      background: b.sharpe_ratio === bestSharpe ? '#f0fff4' : 'transparent'
                    }}
                  >
                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{b.strategy_version}</td>
                    <td style={{ padding: '12px', textAlign: 'right', color: b.sharpe_ratio > 0 ? '#28a745' : b.sharpe_ratio > -1 ? '#ffc107' : '#dc3545', fontFamily: 'monospace' }}>
                      {b.sharpe_ratio.toFixed(3)}
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: b.total_return > 0 ? '#28a745' : '#dc3545', fontFamily: 'monospace' }}>
                      {(b.total_return * 100).toFixed(2)}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'right', color: '#dc3545', fontFamily: 'monospace' }}>
                      {(b.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td style={{ padding: '12px', textAlign: 'center' }}>{b.total_trades}</td>
                    <td style={{ padding: '12px', textAlign: 'center', color: '#666', fontSize: '11px' }}>
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Trade Detail Modal */}
      {selectedBacktest && (
        <div className="modal-overlay" onClick={() => setSelectedBacktest(null)}>
          <div className="modal modal-wide" onClick={e => e.stopPropagation()} style={{ maxWidth: '900px' }}>
            <div className="modal-header" style={{ background: '#00274C', color: 'white' }}>
              <h3>🔬 {selectedBacktest.strategy_version} ANALYSIS</h3>
              <button className="modal-close" onClick={() => setSelectedBacktest(null)} style={{ color: 'white' }}>×</button>
            </div>
            <div className="modal-body">
              {loadingTrades ? (
                <div style={{ padding: '40px', textAlign: 'center' }}>LOADING TRADE DATA...</div>
              ) : (
                <>
                  {tradeSummary && (
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(4, 1fr)', 
                      gap: '16px', 
                      marginBottom: '20px',
                      padding: '16px',
                      background: '#f8f9fa',
                      borderRadius: '8px'
                    }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '10px', color: '#666' }}>NET P&L</div>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: tradeSummary.net_pnl >= 0 ? '#28a745' : '#dc3545' }}>
                          ¥{tradeSummary.net_pnl?.toFixed(2) || '0.00'}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '10px', color: '#666' }}>WINS</div>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#28a745' }}>
                          {tradeSummary.win_count}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '10px', color: '#666' }}>LOSSES</div>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#dc3545' }}>
                          {tradeSummary.loss_count}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '10px', color: '#666' }}>WIN RATE</div>
                        <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#00274C' }}>
                          {tradeSummary.total_trades > 0 ? ((tradeSummary.win_count / tradeSummary.total_trades) * 100).toFixed(1) : 0}%
                        </div>
                      </div>
                    </div>
                  )}

                  {trades.length > 0 ? (
                    <div style={{ maxHeight: '400px', overflow: 'auto' }}>
                      <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: '#00274C', color: 'white' }}>
                            <th style={{ padding: '10px', textAlign: 'left' }}>DATE</th>
                            <th style={{ padding: '10px', textAlign: 'left' }}>CODE</th>
                            <th style={{ padding: '10px', textAlign: 'center' }}>ACTION</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>PRICE</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>P&L</th>
                            <th style={{ padding: '10px', textAlign: 'right' }}>P&L%</th>
                            <th style={{ padding: '10px', textAlign: 'center' }}>HOLD</th>
                            <th style={{ padding: '10px', textAlign: 'left' }}>EXIT REASON</th>
                          </tr>
                        </thead>
                        <tbody>
                          {trades.map((t, i) => (
                            <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', background: i % 2 === 0 ? '#fafafa' : 'white' }}>
                              <td style={{ padding: '10px' }}>{t.trade_date}</td>
                              <td style={{ padding: '10px', fontWeight: 'bold' }}>{t.code}</td>
                              <td style={{ padding: '10px', textAlign: 'center' }}>
                                <span style={{
                                  display: 'inline-block',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  background: t.action === 'BUY' ? '#d4edda' : '#f8d7da',
                                  color: t.action === 'BUY' ? '#155724' : '#721c24',
                                  fontSize: '10px',
                                  fontWeight: 'bold'
                                }}>
                                  {t.action}
                                </span>
                              </td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace' }}>¥{t.price?.toFixed(2)}</td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace', color: (t.realized_pnl || 0) > 0 ? '#28a745' : (t.realized_pnl || 0) < 0 ? '#dc3545' : '#666' }}>
                                {t.realized_pnl ? (t.realized_pnl > 0 ? '+' : '') + '¥' + t.realized_pnl.toFixed(2) : '-'}
                              </td>
                              <td style={{ padding: '10px', textAlign: 'right', fontFamily: 'monospace', color: (t.realized_pnl_pct || 0) > 0 ? '#28a745' : (t.realized_pnl_pct || 0) < 0 ? '#dc3545' : '#666' }}>
                                {t.realized_pnl_pct ? (t.realized_pnl_pct > 0 ? '+' : '') + t.realized_pnl_pct.toFixed(2) + '%' : '-'}
                              </td>
                              <td style={{ padding: '10px', textAlign: 'center' }}>{t.hold_days}d</td>
                              <td style={{ padding: '10px', fontSize: '10px', color: '#666' }}>{t.exit_reason || '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
                      NO TRADES RECORDED FOR THIS EXPERIMENT
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
export default App;

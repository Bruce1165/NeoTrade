import { useState, useEffect } from 'react';
import './App.css';

// Backend via ngrok
const API_BASE = 'https://chariest-nancy-nonincidentally.ngrok-free.dev/api';
const AUTH_HEADER = 'Basic ' + btoa('user:neiltrade123');

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
  const [activeTab, setActiveTab] = useState('screeners');

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
    { id: 'calendar', label: 'Calendar', icon: '📅' },
  ];

  const renderContent = () => {
    switch(activeTab) {
      case 'dashboard': return <DashboardView />;
      case 'screeners': return <ScreenersView screeners={screeners} loading={loading} />;
      case 'results': return <ResultsView screeners={screeners} />;
      case 'calendar': return <CalendarView />;
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
            <div key={item.id} className={`menu-item ${activeTab === item.id ? 'active' : ''}`} onClick={() => setActiveTab(item.id)}>
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

  useEffect(() => {
    fetch(`${API_BASE}/health`).then(r => r.json()).then(d => {
      if (d.data_date) setStats(s => ({ ...s, lastUpdate: d.data_date }));
    }).catch(() => setStats(s => ({ ...s, lastUpdate: 'N/A' })));
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
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CheckResult | null>(null);
  const [error, setError] = useState('');

  const handleCheck = async () => {
    if (!code) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/check-stock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: JSON.stringify({ screener: screener.name, code, date })
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
          <div className="form-row">
            <input type="text" placeholder="Stock Code (e.g. 600000)" value={code} onChange={e => setCode(e.target.value)} className="wsj-input" />
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="wsj-input" />
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
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/screeners/${screener.name}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': AUTH_HEADER },
        body: JSON.stringify({ date })
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResult(data);
    } catch (e: any) {
      setError(e.message || 'Failed to run screener');
    }
    setLoading(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>▶ Run Screener</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          <div className="form-row">
            <label>Screener: <strong>{screener.display_name}</strong></label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="wsj-input" />
            <button className="btn-primary" onClick={handleRun} disabled={loading}>
              {loading ? 'Running...' : 'Run'}
            </button>
          </div>

          {error && <div className="error-message">{error}</div>}

          {result && (
            <div className="screener-result">
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
              </div>
            </div>
          )}
        </div>
      </div>
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

// Results Table Component - dynamically renders any data structure
function ResultsTable({ data }: { data: any[] }) {
  if (!data || data.length === 0) return null;
  
  // Flatten first row to get all possible columns
  const flatRow = flattenObject(data[0]);
  const columns = Object.keys(flatRow);
  
  // Filter out internal/id columns
  let displayColumns = columns.filter(col => 
    !['id', 'run_id', 'created_at', 'updated_at'].includes(col)
  );
  
  // Ensure stock_code and stock_name are first
  const priorityCols = ['stock_code', 'stock_name'];
  displayColumns = [
    ...priorityCols.filter(c => displayColumns.includes(c)),
    ...displayColumns.filter(c => !priorityCols.includes(c))
  ];
  
  // Format column headers
  const formatHeader = (col: string) => {
    const translations: Record<string, string> = {
      'stock_code': '代码',
      'stock_name': '名称',
      'close_price': '收盘价',
      'pct_change': '涨幅%',
      'turnover': '换手率%',
      'extra_data.cup_depth_pct': '杯深%',
      'extra_data.handle_date': '柄部日期',
      'extra_data.days_apart': '间隔天数',
      'extra_data.volume_ratio': '量比',
      'extra_data.handle_price': '柄部价格',
      'extra_data.cup_rim_price': '杯沿价格',
      'amount': '成交额',
      'volume': '成交量'
    };
    return translations[col] || col.replace(/_/g, ' ').replace(/\./g, ' ');
  };
  
  // Format cell values
  const formatValue = (val: any): string => {
    if (val === null || val === undefined) return '-';
    if (typeof val === 'number') {
      // Format percentages
      if (val > -100 && val < 1000 && !Number.isInteger(val)) {
        return val.toFixed(2);
      }
      return val.toString();
    }
    return String(val);
  };
  
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
          return (
            <tr key={i}>
              {displayColumns.map(col => (
                <td key={col}>{formatValue(flatData[col])}</td>
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
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [screenerName, setScreenerName] = useState(screeners[0]?.name || '');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState('');

  const handleQuery = async () => {
    if (!screenerName) {
      setError('Please select a screener');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ screener: screenerName, date });
      const res = await fetch(`${API_BASE}/results?${params}`, { headers: { 'Authorization': AUTH_HEADER }});
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      setResults(data.results || []);
    } catch (e: any) {
      setError(e.message || 'Failed to fetch results');
      setResults([]);
    }
    setLoading(false);
  };

  return (
    <div>
      <div className="page-header">
        <h2>Screening Results</h2>
        <span className="subtitle">View historical screening results</span>
      </div>

      <div className="query-form">
        <input type="date" value={date} onChange={e => setDate(e.target.value)} className="wsj-input" />
        <select value={screenerName} onChange={e => setScreenerName(e.target.value)} className="wsj-select">
          <option value="" disabled>Select a screener...</option>
          {screeners.map(s => <option key={s.id} value={s.name}>{s.display_name}</option>)}
        </select>
        <button className="btn-primary" onClick={handleQuery} disabled={loading || !screenerName}>
          {loading ? 'Querying...' : 'View Results'}
        </button>
      </div>

      {error && <div className="error-message" style={{ marginBottom: '16px' }}>{error}</div>}

      {results.length > 0 ? (
        <div className="results-table-container">
          <ResultsTable data={results} />
        </div>
      ) : (
        <div className="placeholder">{loading ? 'Loading...' : 'No results found. Select a date and click View Results.'}</div>
      )}
    </div>
  );
}

// Calendar View with real data
function CalendarView() {
  const [calendarData, setCalendarData] = useState<Map<string, any>>(new Map());
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/calendar`, { headers: { 'Authorization': AUTH_HEADER }})
      .then(r => r.json())
      .then(d => {
        const map = new Map();
        (d.calendar || []).forEach((item: any) => {
          map.set(item.date, item);
        });
        setCalendarData(map);
      })
      .catch(() => setCalendarData(new Map()));
  }, []);

  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  const firstDay = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1).getDay();
  const days = Array.from({ length: daysInMonth }, (_, i) => i + 1);
  const blanks = Array.from({ length: firstDay }, (_, i) => i);

  const getDataForDay = (day: number) => {
    const dateStr = `${currentMonth.getFullYear()}-${String(currentMonth.getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return calendarData.get(dateStr);
  };

  const selectedData = selectedDay ? getDataForDay(selectedDay) : null;

  return (
    <div>
      <div className="page-header">
        <h2>Task Calendar</h2>
        <span className="subtitle">{currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}</span>
      </div>

      <div className="calendar-nav">
        <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1))}>← Prev</button>
        <button onClick={() => setCurrentMonth(new Date())}>Today</button>
        <button onClick={() => setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1))}>Next →</button>
      </div>

      <div className="calendar-grid">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => <div key={d} className="calendar-day-header">{d}</div>)}
        {blanks.map(i => <div key={`blank-${i}`} className="calendar-day blank" />)}
        {days.map(day => {
          const dayData = getDataForDay(day);
          const hasData = dayData && dayData.screeners && dayData.screeners.length > 0;
          const isSelected = selectedDay === day;
          return (
            <div 
              key={day} 
              className={`calendar-day ${hasData ? 'has-task' : ''} ${isSelected ? 'selected' : ''}`}
              onClick={() => hasData && setSelectedDay(day)}
              style={{ cursor: hasData ? 'pointer' : 'default' }}
            >
              <span className="day-number">{day}</span>
              {hasData && <span className="task-indicator">{dayData.total_stocks}</span>}
            </div>
          );
        })}
      </div>

      {selectedData && (
        <div className="day-detail-panel">
          <div className="day-detail-header">
            <h3>{selectedData.date} - {selectedData.total_stocks} stocks found</h3>
            <button className="modal-close" onClick={() => setSelectedDay(null)}>×</button>
          </div>
          <div className="day-detail-content">
            {selectedData.screeners.map((s: any, i: number) => (
              <div key={i} className="day-screener-item">
                <strong>{s.name}</strong>
                <span className={`status-badge ${s.status}`}>{s.status}</span>
                <span className="stock-count">{s.stocks_found} stocks</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

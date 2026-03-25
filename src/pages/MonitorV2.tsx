import React, { useState, useEffect, useMemo } from 'react';
import '../components/monitor/MonitorV2.css';

const API_BASE = import.meta.env.DEV ? '/api' : `${window.location.origin}/api`;
const AUTH_HEADER = 'Basic ' + btoa('user:NeoTrade2025');

interface DailyCheck {
  day: number;
  date: string;
  status: string;
  close_price?: number;
  note?: string;
}

interface Pick {
  id: number;
  screener_id: string;
  stock_code: string;
  stock_name?: string;
  entry_date: string;
  entry_price: number;
  expected_exit_date: string;
  status: 'active' | 'graduated' | 'failed';
  exit_date?: string;
  exit_reason?: string;
  daily_checks: DailyCheck[];
  created_at: string;
  cup_rim_price?: number;
  cup_bottom_price?: number;
  max_price_seen?: number;
}

interface Screener {
  id: number;
  name: string;
  display_name: string;
  pick_count: number;
}

interface PipelineData {
  screener_id: string;
  picks: Pick[];
  stats: {
    total: number;
    active: number;
    graduated: number;
    failed: number;
    win_rate: number;
  };
}

interface StageGroup {
  key: string;
  title: string;
  subtitle: string;
  picks: Pick[];
  color: string;
}

const STAGE_CONFIG = [
  { key: 'NEW', title: '今天新进', subtitle: 'Day 0', color: '#3b82f6' },
  { key: 'EARLY', title: '早期跟踪', subtitle: 'Day 1-5', color: '#10b981' },
  { key: 'MID', title: '中期跟踪', subtitle: 'Day 6-15', color: '#f59e0b' },
  { key: 'LATE', title: '后期跟踪', subtitle: 'Day 16-24', color: '#8b5cf6' },
  { key: 'GRADUATED', title: '成功毕业', subtitle: 'Day 25+', color: '#eab308' },
  { key: 'FAILED', title: '已失败', subtitle: 'Stopped', color: '#ef4444' },
];

export const Monitor: React.FC = () => {
  const [screeners, setScreeners] = useState<Screener[]>([]);
  const [selectedScreener, setSelectedScreener] = useState<string>('');
  const [pipelineData, setPipelineData] = useState<PipelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedPick, setSelectedPick] = useState<Pick | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set(['NEW', 'EARLY']));

  // Fetch screeners on mount
  useEffect(() => {
    fetch(`${API_BASE}/monitor/screeners`, { 
      headers: { 'Authorization': AUTH_HEADER }
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        setScreeners(data.screeners || []);
        if (data.screeners?.length > 0) {
          setSelectedScreener(data.screeners[0].name);
        }
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  // Fetch pipeline data when screener changes
  useEffect(() => {
    if (!selectedScreener) return;
    
    setLoading(true);
    fetch(`${API_BASE}/monitor/pipeline?screener_id=${selectedScreener}`, {
      headers: { 'Authorization': AUTH_HEADER }
    })
      .then(r => r.json())
      .then(data => {
        if (data.error) throw new Error(data.error);
        setPipelineData(data);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [selectedScreener]);

  // Group picks by stage
  const stageGroups: StageGroup[] = useMemo(() => {
    if (!pipelineData?.picks) {
      return STAGE_CONFIG.map(cfg => ({ ...cfg, picks: [] }));
    }

    const groups: Record<string, Pick[]> = {
      NEW: [],
      EARLY: [],
      MID: [],
      LATE: [],
      GRADUATED: [],
      FAILED: [],
    };

    pipelineData.picks.forEach(pick => {
      if (pick.status === 'graduated') {
        groups.GRADUATED.push(pick);
        return;
      }
      if (pick.status === 'failed') {
        groups.FAILED.push(pick);
        return;
      }

      const dayCount = pick.daily_checks?.length || 0;
      
      if (dayCount === 0) {
        groups.NEW.push(pick);
      } else if (dayCount >= 1 && dayCount <= 5) {
        groups.EARLY.push(pick);
      } else if (dayCount >= 6 && dayCount <= 15) {
        groups.MID.push(pick);
      } else if (dayCount >= 16 && dayCount <= 24) {
        groups.LATE.push(pick);
      } else {
        groups.GRADUATED.push(pick);
      }
    });

    return STAGE_CONFIG.map(cfg => ({
      ...cfg,
      picks: groups[cfg.key] || []
    }));
  }, [pipelineData]);

  // Filter picks by search term
  const filteredGroups = useMemo(() => {
    if (!searchTerm) return stageGroups;
    
    return stageGroups.map(group => ({
      ...group,
      picks: group.picks.filter(pick => 
        pick.stock_code.toLowerCase().includes(searchTerm.toLowerCase())
      )
    }));
  }, [stageGroups, searchTerm]);

  const toggleStage = (key: string) => {
    setExpandedStages(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const stats = pipelineData?.stats || { total: 0, active: 0, graduated: 0, failed: 0, win_rate: 0 };

  if (loading && !pipelineData) {
    return (
      <div className="monitor-page">
        <div className="loading-container">
          <div className="loading-spinner" />
          <span>Loading monitor data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="monitor-page v2">
      {/* Header */}
      <div className="monitor-header-v2">
        <div className="header-left">
          <h2>📊 Screener Monitor</h2>
          <span className="subtitle">25-day tracking pipeline</span>
        </div>
        
        <div className="header-controls">
          <select 
            value={selectedScreener}
            onChange={(e) => setSelectedScreener(e.target.value)}
            className="screener-select"
          >
            {screeners.map(s => (
              <option key={s.id} value={s.name}>
                {s.display_name} ({s.pick_count})
              </option>
            ))}
          </select>
          
          <input
            type="text"
            placeholder="Search stock code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {/* Stats Bar */}
      <div className="stats-bar-v2">
        <div className="stat-box">
          <span className="stat-value">{stats.active}</span>
          <span className="stat-label">Active</span>
        </div>
        <div className="stat-box">
          <span className="stat-value success">{stats.graduated}</span>
          <span className="stat-label">Graduated</span>
        </div>
        <div className="stat-box">
          <span className="stat-value failed">{stats.failed}</span>
          <span className="stat-label">Failed</span>
        </div>
        <div className="stat-box">
          <span className={`stat-value ${stats.win_rate >= 50 ? 'success' : 'failed'}`}>
            {stats.win_rate}%
          </span>
          <span className="stat-label">Win Rate</span>
        </div>
        <div className="stat-box">
          <span className="stat-value">{stats.total}</span>
          <span className="stat-label">Total</span>
        </div>
      </div>

      {/* Pipeline List */}
      <div className="pipeline-list">
        {filteredGroups.map(group => (
          <div key={group.key} className="stage-section">
            <div 
              className="stage-header"
              style={{ borderLeftColor: group.color }}
              onClick={() => toggleStage(group.key)}
            >
              <div className="stage-title-row">
                <span className="stage-toggle">
                  {expandedStages.has(group.key) ? '▼' : '▶'}
                </span>
                <span className="stage-name" style={{ color: group.color }}>
                  {group.title}
                </span>
                <span className="stage-subtitle">{group.subtitle}</span>
                <span className="stage-count">({group.picks.length})</span>
              </div>
            </div>
            
            {expandedStages.has(group.key) && (
              <div className="stage-content">
                {group.picks.length === 0 ? (
                  <div className="empty-stage">No picks in this stage</div>
                ) : (
                  group.picks.map(pick => (
                    <PickRow 
                      key={pick.id} 
                      pick={pick} 
                      onClick={() => setSelectedPick(pick)}
                      color={group.color}
                    />
                  ))
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pick Detail Modal */}
      {selectedPick && (
        <PickDetailModal 
          pick={selectedPick} 
          onClose={() => setSelectedPick(null)}
        />
      )}
    </div>
  );
};

// Pick Row Component
const PickRow: React.FC<{ pick: Pick; onClick: () => void; color: string }> = ({ pick, onClick, color }) => {
  const currentDay = pick.daily_checks?.length || 0;
  const latestCheck = pick.daily_checks?.[pick.daily_checks.length - 1];
  const currentPrice = latestCheck?.close_price || pick.entry_price;
  const performance = ((currentPrice - pick.entry_price) / pick.entry_price * 100);
  
  const statusIcon = pick.status === 'active' ? '✓' : 
                     pick.status === 'graduated' ? '🎓' : '✗';
  
  return (
    <div className="pick-row" onClick={onClick} style={{ borderLeftColor: color }}>
      <div className="pick-main">
        <span className="pick-status-icon">{statusIcon}</span>
        <span className="pick-code">{pick.stock_code}</span>
        <span className="pick-name">{pick.stock_name || '-'}</span>
        <span className="pick-day">Day {currentDay}/25</span>
      </div>
      
      <div className="pick-prices">
        <span className="pick-entry">Entry: ¥{pick.entry_price.toFixed(2)}</span>
        <span className="pick-current">Now: ¥{currentPrice.toFixed(2)}</span>
        <span className={`pick-performance ${performance >= 0 ? 'positive' : 'negative'}`}>
          {performance >= 0 ? '+' : ''}{performance.toFixed(1)}%
        </span>
      </div>
      
      <div className="pick-meta">
        <span className="pick-date">{pick.entry_date}</span>
        {pick.cup_rim_price && (
          <span className="pick-cup-info">
            Rim: ¥{pick.cup_rim_price.toFixed(1)}
          </span>
        )}
      </div>
    </div>
  );
};

// Pick Detail Modal
const PickDetailModal: React.FC<{ pick: Pick; onClose: () => void }> = ({ pick, onClose }) => {
  const currentDay = pick.daily_checks?.length || 0;
  const latestCheck = pick.daily_checks?.[pick.daily_checks.length - 1];
  const currentPrice = latestCheck?.close_price || pick.entry_price;
  const performance = ((currentPrice - pick.entry_price) / pick.entry_price * 100);
  const failureLine = pick.cup_rim_price && pick.cup_bottom_price
    ? (pick.cup_rim_price + pick.cup_bottom_price) / 2
    : null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal pick-detail-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{pick.stock_code} - Pick Details</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="modal-body">
          {/* Stats Grid */}
          <div className="detail-stats-grid">
            <div className="detail-stat">
              <span className="label">Status</span>
              <span className={`value status-${pick.status}`}>
                {pick.status === 'active' ? 'Active' : 
                 pick.status === 'graduated' ? 'Graduated' : 'Failed'}
              </span>
            </div>
            <div className="detail-stat">
              <span className="label">Day</span>
              <span className="value">{currentDay} / 25</span>
            </div>
            <div className="detail-stat">
              <span className="label">Entry</span>
              <span className="value">¥{pick.entry_price.toFixed(2)}</span>
            </div>
            <div className="detail-stat">
              <span className="label">Current</span>
              <span className="value">¥{currentPrice.toFixed(2)}</span>
            </div>
            <div className="detail-stat">
              <span className="label">P/L</span>
              <span className={`value ${performance >= 0 ? 'positive' : 'negative'}`}>
                {performance >= 0 ? '+' : ''}{performance.toFixed(2)}%
              </span>
            </div>
          </div>

          {/* Cup Pattern Info */}
          {pick.screener_id === 'coffee_cup_screener' && failureLine && (
            <div className="cup-levels">
              <h4>Cup Pattern Levels</h4>
              <div className="level-row">
                <span className="level-name">Rim</span>
                <span className="level-price">¥{pick.cup_rim_price?.toFixed(2)}</span>
              </div>
              <div className="level-row">
                <span className="level-name">Bottom</span>
                <span className="level-price">¥{pick.cup_bottom_price?.toFixed(2)}</span>
              </div>
              <div className="level-row failure">
                <span className="level-name">Failure Line</span>
                <span className="level-price">¥{failureLine.toFixed(2)}</span>
              </div>
            </div>
          )}

          {/* Daily History */}
          <div className="daily-history">
            <h4>Daily History ({pick.daily_checks?.length || 0} days)</h4>
            {pick.daily_checks?.length > 0 ? (
              <table className="history-table">
                <thead>
                  <tr>
                    <th>Day</th>
                    <th>Date</th>
                    <th>Price</th>
                    <th>Change</th>
                    <th>Note</th>
                  </tr>
                </thead>
                <tbody>
                  {pick.daily_checks.map((check, idx) => {
                    const prevPrice = idx > 0 ? pick.daily_checks[idx - 1].close_price : pick.entry_price;
                    const change = check.close_price && prevPrice 
                      ? ((check.close_price - prevPrice) / prevPrice * 100)
                      : 0;
                    return (
                      <tr key={idx}>
                        <td>{check.day}</td>
                        <td>{check.date}</td>
                        <td>¥{check.close_price?.toFixed(2) || '-'}</td>
                        <td className={change >= 0 ? 'positive' : 'negative'}>
                          {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                        </td>
                        <td>{check.note || '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <p className="no-data">No daily checks recorded yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Monitor;

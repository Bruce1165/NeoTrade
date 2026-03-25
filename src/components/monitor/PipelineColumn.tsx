import React from 'react';
import { PickCard } from './PickCard';
import './Monitor.css';

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

type PipelineStage = 'NEW' | 'EARLY' | 'MID' | 'LATE' | 'GRADUATED' | 'FAILED';

interface PipelineColumnProps {
  stage: PipelineStage;
  picks: Pick[];
  title: string;
  subtitle: string;
  onPickClick?: (pick: Pick) => void;
}

const STAGE_CONFIG: Record<PipelineStage, { color: string; icon: string; bgColor: string }> = {
  NEW: { color: '#3b82f6', icon: '🆕', bgColor: 'rgba(59, 130, 246, 0.08)' },
  EARLY: { color: '#10b981', icon: '🌱', bgColor: 'rgba(16, 185, 129, 0.08)' },
  MID: { color: '#f59e0b', icon: '📊', bgColor: 'rgba(245, 158, 11, 0.08)' },
  LATE: { color: '#8b5cf6', icon: '🎯', bgColor: 'rgba(139, 92, 246, 0.08)' },
  GRADUATED: { color: '#eab308', icon: '🎓', bgColor: 'rgba(234, 179, 8, 0.12)' },
  FAILED: { color: '#ef4444', icon: '⚠️', bgColor: 'rgba(239, 68, 68, 0.08)' },
};

export const PipelineColumn: React.FC<PipelineColumnProps> = ({ 
  stage, 
  picks, 
  title, 
  subtitle,
  onPickClick 
}) => {
  const config = STAGE_CONFIG[stage];
  
  return (
    <div className="pipeline-column">
      {/* Column Header */}
      <div 
        className="pipeline-column-header"
        style={{ 
          background: config.bgColor,
          borderColor: config.color 
        }}
      >
        <div className="column-title-row">
          <span className="column-icon" style={{ color: config.color }}>
            {config.icon}
          </span>
          <span className="column-count" style={{ 
            background: config.color,
            color: 'white'
          }}>
            {picks.length}
          </span>
        </div>
        <h4 className="column-title">{title}</h4>
        <span className="column-subtitle">{subtitle}</span>
      </div>
      
      {/* Cards Container */}
      <div className="pipeline-cards">
        {picks.length === 0 ? (
          <div className="empty-column">
            <span className="empty-icon">{config.icon}</span>
            <span className="empty-text">No picks</span>
          </div>
        ) : (
          picks.map(pick => (
            <PickCard 
              key={pick.id} 
              pick={pick} 
              onClick={onPickClick}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default PipelineColumn;

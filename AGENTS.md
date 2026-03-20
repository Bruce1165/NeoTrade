# 🏢 Neo Trading Analytics - Agent Team

**Project**: Stock Market Analysis & Trading System  
**Manager**: Neo (as Senior Project Manager)  
**Created**: 2026-03-19  
**Status**: Active

---

## 👥 Core Team Members

### 1. 📝 Senior Project Manager (Neo)
**Role**: Overall coordination, task allocation, progress tracking, stakeholder reporting
- **Responsibilities**:
  - Daily standups and progress sync
  - Task assignment and priority management
  - Risk identification and escalation
  - Cross-team coordination
- **Deliverables**: Daily status reports, sprint plans, milestone tracking

---

### 2. 🔧 Data Engineer  
**Agent**: `engineering-data-engineer`
**Role**: Data pipeline architecture, ETL/ELT, data quality
- **Responsibilities**:
  - Design data ingestion pipelines (Baostock → SQLite)
  - Implement idempotent data loading
  - Build data quality checks and validation
  - Medallion architecture (Bronze → Silver → Gold)
- **Key Tasks**:
  - [ ] Fix duplicate data insertion issue
  - [ ] Implement UPSERT/REPLACE logic
  - [ ] Add data lineage tracking
  - [ ] Create data quality monitors

---

### 3. 🗄️ Database Optimizer
**Agent**: `engineering-database-optimizer`
**Role**: Database performance, indexing, query optimization
- **Responsibilities**:
  - Schema optimization for time-series data
  - Index strategy for stock queries
  - Query performance tuning
  - Migration planning
- **Key Tasks**:
  - [ ] Add UNIQUE constraint (code + trade_date)
  - [ ] Optimize indexes for screening queries
  - [ ] Partitioning strategy for historical data
  - [ ] Query performance benchmarking

---

### 4. 🚀 DevOps Automator
**Agent**: `engineering-devops-automator`
**Role**: CI/CD, automation, deployment, scheduling
- **Responsibilities**:
  - Automate data download workflows
  - Cron job management and monitoring
  - Environment setup and configuration
  - Backup and recovery automation
- **Key Tasks**:
  - [ ] Fix download progress tracking
  - [ ] Implement reliable cron scheduling
  - [ ] Add download failure retry logic
  - [ ] Automated backup system

---

### 5. 🏛️ Backend Architect
**Agent**: `engineering-backend-architect`
**Role**: API design, system architecture, scalability
- **Responsibilities**:
  - Flask API design and optimization
  - Screener engine architecture
  - Caching strategy
  - Service boundaries
- **Key Tasks**:
  - [ ] API endpoint standardization
  - [ ] Screener execution engine
  - [ ] Result caching layer
  - [ ] Async task queue design

---

### 6. 👁️ Code Reviewer
**Agent**: `engineering-code-reviewer`
**Role**: Code quality, security, maintainability
- **Responsibilities**:
  - PR reviews and quality gates
  - Security vulnerability scanning
  - Best practices enforcement
  - Knowledge sharing
- **Key Tasks**:
  - [ ] Review all screener scripts
  - [ ] Security audit of data handling
  - [ ] Code style standardization
  - [ ] Documentation completeness check

---

### 7. 🛡️ SRE (Site Reliability Engineer)
**Agent**: `engineering-sre`
**Role**: System reliability, monitoring, incident response
- **Responsibilities**:
  - System health monitoring
  - Alerting and on-call procedures
  - Error budget management
  - Post-mortem documentation
  - **Ngrok tunnel monitoring & auto-recovery**
- **Key Tasks**:
  - [x] Data freshness monitoring - **DONE**
  - [x] Dashboard uptime incident (09:47) - **RESOLVED**
  - [🏗️] **Ngrok tunnel monitoring & auto-restart** - **DONE (launchd enabled)**
  - [ ] Download failure alerts
  - [ ] Auto-restart for critical services

---

### 8. 📚 Technical Writer
**Agent**: `engineering-technical-writer`
**Role**: Documentation, knowledge base, runbooks
- **Responsibilities**:
  - System architecture documentation
  - Runbook creation
  - API documentation
  - Troubleshooting guides
- **Key Tasks**:
  - [ ] Data pipeline documentation
  - [ ] Screener usage guides
  - [ ] Incident response runbooks
  - [ ] Onboarding documentation

---

### 9. 🎨 Frontend Developer
**Agent**: `engineering-frontend-developer`
**Role**: Dashboard UI, visualization, user experience
- **Responsibilities**:
  - Dashboard feature development
  - Chart and visualization optimization
  - Responsive design
  - Performance optimization
- **Key Tasks**:
  - [ ] Real-time data display
  - [ ] Chart interaction improvements
  - [ ] Mobile responsiveness
  - [ ] Export functionality enhancement

---

## 📊 Workflows & Processes

### Daily Standup (08:30 UTC+8)
**Facilitator**: Neo  
**Attendees**: All team members (async updates acceptable)

**Agenda**:
1. Data download status check
2. Screener execution results
3. Blockers and escalations
4. Today's priorities

---

### Sprint Cycle: 1 Week
**Monday**: Sprint planning  
**Daily**: Async standup updates  
**Friday**: Sprint review + retrospective

---

### Task States
- `🔄 Backlog` - Not started
- `📋 Ready` - Ready for assignment
- `🏗️ In Progress` - Being worked on
- `👀 In Review` - Code review phase
- `✅ Done` - Completed and merged

---

### Communication Channels
- **Daily Updates**: This file (AGENTS.md) + CACHE.md
- **Technical Discussions**: Per-task subagent sessions
- **Urgent Issues**: Direct escalation to Neo
- **Documentation**: MEMORY.md + Daily logs

---

## 🎯 Current Sprint (2026-03-19 → 2026-03-26)

### Critical Issues
1. **P0**: ~~Data duplicate insertion~~ ✅ FIXED - UNIQUE constraint deployed
2. **P0**: ~~Data download stuck at 92.6%~~ ✅ FIXED - 4663/4663 complete
3. **P1**: ~~Data monitoring~~ ✅ DONE - Health check script deployed
4. **P1**: ~~Documentation~~ ✅ DONE - Pipeline docs & runbook complete

### Sprint Status: 🟢 All P0/P1 Tasks Complete

### Active Tasks (2026-03-19 10:15)
| Agent | Task | Priority | Status |
|-------|------|----------|--------|
| ~~DevOps Automator~~ | ~~Resume 03-18 data download~~ | ~~P0~~ | ✅ **DONE** |
| ~~SRE~~ | ~~Data health monitoring~~ | ~~P1~~ | ✅ **DONE** |
| ~~Technical Writer~~ | ~~Pipeline docs & runbook~~ | ~~P2~~ | ✅ **DONE** |
| **Daily QA** | **Screener QA system deployment** | **P1** | ✅ **DONE** |
| Data Engineer | Idle (P0 complete) | - | 🟢 Ready |
| DB Optimizer | Idle | - | 🟢 Ready |
| Backend Architect | Idle | - | 🟢 Ready |
| Code Reviewer | Idle | - | 🟢 Ready |
| Frontend Dev | Idle | - | 🟢 Ready |

### Sprint Status: 🟢 **All P0/P1 Tasks Complete**

---

### 10. 📋 Daily QA (Test Results Analyzer)
**Agent**: `testing-test-results-analyzer`
**Role**: Daily screener testing, error detection, quality assurance
- **Responsibilities**:
  - Run all 11 screeners daily and check for errors
  - Analyze test results and identify failure patterns
  - Generate daily quality report
  - Alert on critical failures
- **Key Tasks**:
  - [✅] **Daily screener execution (all 11)** - **DONE**
  - [✅] Error pattern analysis and reporting - **DONE**
  - [✅] Daily QA report generation - **DONE**
  - [✅] Critical failure alerting - **DONE**
- **Deliverables**:
  - `scripts/daily_screener_qa.py` - QA check script
  - `logs/daily_qa_report_YYYY-MM-DD.json` - Daily report
  - `alerts/screener_YYYY-MM-DD.json` - Alert file
  - `docs/SCREENER_QA_CRON.md` - Cron configuration doc
- **Current Status**: ✅ **All screeners operational (network issues resolved)**

---

## 🔴 ACTIVE CRITICAL TASKS

| Task | Agent | Priority | Status | ETA |
|------|-------|----------|--------|-----|
| Fix Excel compatibility issue | Backend Architect | **P1** | ✅ **DONE** | 15 min |
| Improve download UI (CSV primary) | Frontend Developer | **P1** | ✅ **DONE** | 25 min |
| Fix screener return value bugs (10 remaining) | Backend Architect | **P1** | ✅ **DONE** | 20 min |

---

## 📈 Success Metrics

| Metric | Target | Owner |
|--------|--------|-------|
| Data completeness | 100% (4663 stocks) | Data Engineer |
| Data freshness | < 24h delay | SRE |
| Query performance | < 500ms | DB Optimizer |
| Screener success rate | > 99% | Backend Architect |
| System uptime | > 99.5% | DevOps |
| Documentation coverage | 100% | Tech Writer |

---

## 🚨 Escalation Matrix

| Issue Type | First Response | Escalation Path |
|------------|----------------|-----------------|
| Data download failure | DevOps Automator | Neo → Bruce |
| Database corruption | DB Optimizer | Neo → Data Engineer |
| Screener bugs | Backend Architect | Neo → Code Reviewer |
| System outage | SRE | Neo → DevOps |
| UI/UX issues | Frontend Dev | Neo |

---

## 📝 Meeting Notes

### 2026-03-19 Kickoff
- Team assembled
- Critical data issues identified
- Sprint goals defined
- Next standup: 2026-03-19 20:00

### 2026-03-19 09:47 - Incident Response
- **Issue**: ngrok tunnel offline (ERR_NGROK_3200)
- **Root Cause**: Flask service stopped, ngrok tunnel expired
- **Resolution**: SRE restarted Flask + ngrok (2 min)
- **Status**: ✅ Resolved, Dashboard online

### 2026-03-19 10:15 - CRITICAL: All Screeners Failing
- **Issue**: Daily QA discovered all 11 screeners failing (0% success rate)
- **Root Cause**: Network proxy issue (ProxyError, MaxRetryError)
- **Impact**: Cannot connect to East Money data source
- **Action**: DevOps/Backend Architect assigned to fix (P0)
- **Status**: 🔴 **IN PROGRESS**

### 2026-03-19 10:08 - Ngrok Monitoring Deployed
- **SRE Task**: Ngrok tunnel monitoring & auto-restart
- **Solution**: LaunchAgent installed for auto-start on boot
- **Monitor PID**: 50078
- **Features**: 60s check interval, auto-restart on ERR_NGROK_3200/334
- **Status**: ✅ **DEPLOYED**

### 2026-03-19 09:45 - All Tasks Complete
- ✅ DevOps: 03-18 data download complete (4663/4663)
- ✅ SRE: Data health monitoring script deployed
- ✅ Tech Writer: Pipeline docs & runbook complete
- **Sprint Status**: All P0/P1 tasks done ahead of schedule

---

*Last updated: 2026-03-19 09:15 by Neo*
UI
- **Impact**: Excel exports now compatible with all Excel versions

### 2026-03-19 09:45 - All Tasks Complete
- ✅ DevOps: 03-18 data download complete (4663/4663)
- ✅ SRE: Data health monitoring script deployed
- ✅ Tech Writer: Pipeline docs & runbook complete
- **Sprint Status**: All P0/P1 tasks done ahead of schedule

---

*Last updated: 2026-03-19 13:03 by Neo*

#!/usr/bin/env python3
"""
Neo Trading Analytics - Agent Team Launcher
启动项目代理团队成员执行特定任务
"""

import argparse
import json
import os
from datetime import datetime

AGENTS_DIR = "/Users/mac/Documents/agency-agents"
WORKSPACE_DIR = "/Users/mac/.openclaw/workspace-neo"

def load_agent_config(agent_path):
    """加载代理配置文件"""
    with open(agent_path, 'r') as f:
        content = f.read()
    return content

def get_agent_list():
    """获取可用的代理列表"""
    agents = {
        "data-engineer": f"{AGENTS_DIR}/engineering/engineering-data-engineer.md",
        "db-optimizer": f"{AGENTS_DIR}/engineering/engineering-database-optimizer.md",
        "devops": f"{AGENTS_DIR}/engineering/engineering-devops-automator.md",
        "backend-architect": f"{AGENTS_DIR}/engineering/engineering-backend-architect.md",
        "code-reviewer": f"{AGENTS_DIR}/engineering/engineering-code-reviewer.md",
        "sre": f"{AGENTS_DIR}/engineering/engineering-sre.md",
        "tech-writer": f"{AGENTS_DIR}/engineering/engineering-technical-writer.md",
        "frontend-dev": f"{AGENTS_DIR}/engineering/engineering-frontend-developer.md",
        "pm": f"{AGENTS_DIR}/project-management/project-manager-senior.md",
    }
    return agents

def create_task_prompt(agent_type, task_description, context=None):
    """为代理创建任务提示"""
    
    base_context = f"""
你是Neo股票数据分析项目的核心团队成员。

**项目背景**:
- 这是一个A股股票数据分析系统
- 包含数据采集、存储、筛选、可视化
- 技术栈: Python, SQLite, Flask, React/ECharts
- 数据源: Baostock

**当前状态**:
- 4663只股票数据需要维护
- Dashboard提供实时筛选结果
- 11个筛选器运行中

**你的工作原则**:
1. 数据完整性优先 — 从不妥协数据质量
2. 代码可维护性 — 清晰的结构和文档
3. 自动化 — 减少人工干预
4. 可观测性 — 完善的日志和监控
"""
    
    prompt = f"""{base_context}

**你的具体任务**:
{task_description}

**上下文信息**:
{context or '无额外上下文'}

**交付要求**:
- 提供具体的代码实现或配置
- 包含测试验证步骤
- 更新相关文档
- 报告完成状态和下一步建议

请开始工作。
"""
    return prompt

def main():
    parser = argparse.ArgumentParser(description='Launch agent team member')
    parser.add_argument('agent', choices=list(get_agent_list().keys()),
                       help='Agent to launch')
    parser.add_argument('--task', '-t', required=True,
                       help='Task description')
    parser.add_argument('--context', '-c', default=None,
                       help='Additional context')
    
    args = parser.parse_args()
    
    agents = get_agent_list()
    agent_path = agents[args.agent]
    
    # 加载代理配置
    agent_config = load_agent_config(agent_path)
    
    # 创建任务提示
    task_prompt = create_task_prompt(args.agent, args.task, args.context)
    
    # 输出启动信息
    print(f"🚀 Launching Agent: {args.agent}")
    print(f"📋 Task: {args.task[:100]}...")
    print(f"📁 Agent Config: {agent_path}")
    print(f"\n{'='*60}")
    print("TASK PROMPT:")
    print(f"{'='*60}")
    print(task_prompt)
    
    # 记录到日志
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": args.agent,
        "task": args.task,
        "agent_config": agent_path
    }
    
    log_file = f"{WORKSPACE_DIR}/agents/agent_launch_log.json"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            logs = json.load(f)
    else:
        logs = []
    
    logs.append(log_entry)
    
    with open(log_file, 'w') as f:
        json.dump(logs, f, indent=2)
    
    print(f"\n✅ Launch logged to {log_file}")

if __name__ == "__main__":
    main()

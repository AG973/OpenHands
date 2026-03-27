"""Multi-Agent Role System.

Implements specialized agent roles inspired by GPT-Pilot's 14-agent system
and CrewAI's Agent-Task-Crew model. Each role has a specific responsibility
in the execution pipeline.

Roles (strict execution order):
    Planner → Architect → Coder → Tester → Debugger → Reviewer → Manager

Patterns extracted from:
    - GPT-Pilot: 14 specialized agents with strict hand-off
    - CrewAI: Agent-Task-Crew with role/goal/backstory
    - AutoGen: Conversation-based multi-agent collaboration
    - LangGraph: StateGraph for deterministic orchestration
"""

from openhands.agents.base_role import AgentRole, RoleContext, RoleOutput
from openhands.agents.planner_agent import PlannerAgent
from openhands.agents.architect_agent import ArchitectAgent
from openhands.agents.coder_agent import CoderAgent
from openhands.agents.tester_agent import TesterAgent
from openhands.agents.debugger_agent import DebuggerAgent
from openhands.agents.reviewer_agent import ReviewerAgent
from openhands.agents.manager_agent import ManagerAgent

__all__ = [
    'AgentRole',
    'RoleContext',
    'RoleOutput',
    'PlannerAgent',
    'ArchitectAgent',
    'CoderAgent',
    'TesterAgent',
    'DebuggerAgent',
    'ReviewerAgent',
    'ManagerAgent',
]

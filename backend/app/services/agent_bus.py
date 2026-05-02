import asyncio
import logging
from typing import Callable, Any
from app.models import AgentFinding

logger = logging.getLogger(__name__)

class AgentBus:
    """In-memory pub/sub for agent findings."""
    
    def __init__(self):
        self.subscribers: list[Callable[[AgentFinding], Any]] = []

    def subscribe(self, callback: Callable[[AgentFinding], Any]):
        self.subscribers.append(callback)

    def publish(self, finding: AgentFinding):
        for callback in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(finding))
                else:
                    callback(finding)
            except Exception as e:
                logger.error("Error in AgentBus subscriber: %s", e)

# Global bus instance
agent_bus = AgentBus()

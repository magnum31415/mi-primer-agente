
from langgraph.graph import MessagesState


class AgentState(MessagesState):
    servidor: str
    tool_calls_used: int

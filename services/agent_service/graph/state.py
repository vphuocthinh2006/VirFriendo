from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    The state for the LangGraph agentic workflow.
    """
    # The history of the current conversation
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # The classified intent of the latest user message
    intent: str
    
    # The emotion detected from the user message, if applicable
    emotion: str
    
    # Optional metadata such as avatar action or bibliotherapy suggestions
    avatar_action: str
    bibliotherapy_suggestion: str | None

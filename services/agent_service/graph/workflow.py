# services/agent_service/graph/workflow.py
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage
from typing import Literal

from services.agent_service.graph.state import AgentState
from services.agent_service.graph.agents import (
    chit_chat_node, guardrail_node,
    entertainment_expert_node, comfort_node,
    advice_node, crisis_node
)
from services.agent_service.graph.emotion import emotion_node
from services.agent_service.api.intent_classifier import intent_classifier


async def classification_node(state: AgentState) -> dict:
    """
    Phân loại intent: hybrid (model/keyword + Groq reason), lấy kết quả ổn hơn.
    """
    last_message = state["messages"][-1].content
    detected_intent = await intent_classifier.predict_hybrid_async(last_message)
    return {"intent": detected_intent}


def route_intent(state: AgentState) -> Literal[
    "chit_chat", "guardrail", "entertainment_expert", "comfort", "advice", "crisis"
]:
    """
    Hàm định tuyến (Conditional Edge) dựa vào intent trong state.
    """
    intent = state.get("intent", "greeting_chitchat")
    
    mapping = {
        "greeting_chitchat": "chit_chat",
        "out_of_domain": "guardrail",
        "entertainment_knowledge": "entertainment_expert",
        "psychology_venting": "comfort",
        "psychology_advice_seeking": "advice",
        "crisis_alert": "crisis",
    }
    
    return mapping.get(intent, "chit_chat")


def build_graph() -> StateGraph:
    """
    Tạo và Compile StateGraph
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("classifier", classification_node)
    workflow.add_node("emotion", emotion_node)
    workflow.add_node("chit_chat", chit_chat_node)
    workflow.add_node("guardrail", guardrail_node)
    workflow.add_node("entertainment_expert", entertainment_expert_node)
    workflow.add_node("comfort", comfort_node)
    workflow.add_node("advice", advice_node)
    workflow.add_node("crisis", crisis_node)

    workflow.add_edge(START, "classifier")
    workflow.add_edge("classifier", "emotion")
    workflow.add_conditional_edges("emotion", route_intent)

    # Từ các Agent -> Kết nối tới END (hoặc gửi response ra output)
    workflow.add_edge("chit_chat", END)
    workflow.add_edge("guardrail", END)
    workflow.add_edge("entertainment_expert", END)
    workflow.add_edge("comfort", END)
    workflow.add_edge("advice", END)
    workflow.add_edge("crisis", END)

    # 3. Compile Graph
    app = workflow.compile()
    return app

# Khởi tạo Graph toàn cục để API tái sử dụng
graph_app = build_graph()

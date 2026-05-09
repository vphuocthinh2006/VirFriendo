# services/agent_service/graph/workflow.py
#
# DEPRECATED — legacy LangGraph workflow (classifier → emotion → route_intent →
# chit_chat / guardrail / entertainment_expert / comfort / advice / crisis).
#
# Production traffic now goes through services/agent_service/claude_agent.py
# (single Claude tool_use loop). This module is no longer imported by
# agent_api/main.py — kept temporarily for reference and as a fallback we may
# re-enable. Safe to delete once we confirm we will not need to roll back.
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


def _technical_followup_suppresses_context(last_message: str) -> bool:
    """Short follow-ups are merged with prior user text for anime/game continuity — but CS/math/code must stay OOD."""
    low = (last_message or "").strip().lower()
    markers = (
        " code", "code ", "algorithm", "shell sort", "merge sort", "quick sort", "heap sort",
        "sorting", "data structure", "leetcode", "big-o", "độ phức", "pointer", "array",
        "python", "javascript", "typescript", "html", "css", "sql", "golang", "rust", "c++",
        "toán ", " toán", "bitcoin", "chứng khoán",
    )
    return any(m in low for m in markers)


# Hard-coded greeting/interjection tokens that should always route to chit-chat
# regardless of whatever the hybrid classifier (model + Groq) decides.
_GREETING_OVERRIDES = {
    "alo", "alô", "alooo", "alooooo", "alo alo",
    "hi", "hii", "hiii", "hihi",
    "hello", "helo", "hé lô", "hé-lô",
    "hey", "yo", "yoyo", "yo yo",
    "chào", "chao", "chào bạn", "chao ban", "chào nha",
    "halo", "ới", "ê", "ê ơi", "hú", "hú hú",
    "có ai không", "có ai đó không", "có ai ở đây không",
    "?", "??", "???", ".", "...", "🙂", "👋",
}


def _force_greeting(text: str) -> bool:
    """Catch obvious greetings/interjections that the classifier sometimes
    mis-routes to the entertainment pipeline (which then fails for lack of sources)."""
    low = (text or "").strip().lower()
    if not low:
        return True
    if low in _GREETING_OVERRIDES:
        return True
    # Single word + short → greeting (covers typos like "alooo")
    words = low.split()
    if len(words) == 1 and len(low) <= 6 and not any(c.isdigit() for c in low):
        return True
    return False


async def classification_node(state: AgentState) -> dict:
    """
    Phân loại intent: hybrid (model/keyword + Groq reason), lấy kết quả ổn hơn.
    """
    last_message = state["messages"][-1].content
    # Hard override: short greetings / interjections always go to chit-chat.
    if _force_greeting(last_message):
        return {"intent": "greeting_chitchat"}
    user_msgs = [m.content for m in state.get("messages", []) if isinstance(m, HumanMessage)]
    prev_user = user_msgs[-2] if len(user_msgs) >= 2 else ""
    low = (last_message or "").strip().lower()
    use_prev = (
        bool(prev_user)
        and (
            any(k in low for k in ["nếu so sánh", "ý là", "thế còn", "còn nếu", "vậy còn", "so với", "so sánh"])
            or len(low.split()) <= 8
        )
    )
    classify_text = f"{prev_user}\nFollow-up: {last_message}" if use_prev else last_message
    detected_intent = await intent_classifier.predict_hybrid_async(classify_text)
    return {"intent": detected_intent}


def route_intent(state: AgentState) -> Literal[
    "chit_chat", "guardrail", "entertainment_expert", "comfort", "advice", "crisis"
]:
    """
    Hàm định tuyến (Conditional Edge) dựa vào intent trong state.
    """
    intent = state.get("intent", "greeting_chitchat")
    # Safety-first: emotion detector can catch crisis even if intent classifier misses.
    if state.get("emotion") == "crisis":
        return "crisis"
    
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

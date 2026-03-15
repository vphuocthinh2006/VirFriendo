import os
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from core.config import settings

# A simple fallback reply
def _fallback_reply(state: Dict[str, Any]) -> Dict[str, Any]:
    print("---FALLBACK: Generating Chit-Chat Reply---")
    intent = state.get("intent", "unknown")
    user_message = state.get("message", "")
    history = state.get("conversation_history", [])
    if intent == "psychology_venting":
        reply = "Mình hiểu cảm giác của bạn. Nếu muốn chia sẻ thêm, mình luôn sẵn sàng lắng nghe."
    elif intent == "psychology_advice":
        reply = "Bạn có thể nói rõ hơn về tình huống của mình không? Mình sẽ cố gắng giúp bạn hết sức."
    else:
        reply = "Cảm ơn bạn đã chia sẻ. Mình ở đây nếu bạn cần nói chuyện thêm."
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=reply))
    state["reply"] = reply
    state["conversation_history"] = history
    return state

def generate_response(state: Dict[str, Any]) -> Dict[str, Any]:
    print("---AGENT: Generating Chit-Chat Reply---")
    try:
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set in environment variables.")
        user_message = state.get("message", "")
        intent = state.get("intent", "unknown")
        emotion = state.get("emotion", "neutral")
        history = state.get("conversation_history", [])
        # Persona: tự nhiên, thân thiện, không sến, không cường điệu, hỗ trợ song ngữ
        system_prompt = (
            "Bạn là một người bạn AI thân thiện, trò chuyện tự nhiên, lịch sự, không dùng từ ngữ cường điệu hay cảm thán lạ. "
            "Bạn có thể trả lời bằng tiếng Việt hoặc tiếng Anh tùy vào ngôn ngữ của người dùng. "
            "Hãy phản hồi ngắn gọn, rõ ràng, tập trung vào việc lắng nghe, chia sẻ và hỗ trợ cảm xúc. "
            "Không dùng emoji, không dùng từ ngữ kiểu hoạt hình, không nói quá lên. "
            "Nếu người dùng chia sẻ cảm xúc, hãy đồng cảm và hỏi thêm nếu phù hợp. Nếu người dùng hỏi xin lời khuyên, hãy hỏi rõ hơn về hoàn cảnh trước khi đưa ra ý kiến. "
            "Ngữ cảnh cuộc trò chuyện:\n"
            "- Ý định của người dùng: {intent}\n"
            "- Cảm xúc của người dùng: {emotion}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        llm = ChatGroq(
            temperature=0.7,
            model_name="llama-3.1-70b-versatile",
            api_key=settings.GROQ_API_KEY,
        )
        chain = prompt | llm
        response = chain.invoke({
            "intent": intent,
            "emotion": emotion,
            "chat_history": history,
            "input": user_message
        })
        reply = response.content
    except Exception as e:
        print(f"Error during Groq API call: {e}")
        return _fallback_reply(state)
    history.append(HumanMessage(content=user_message))
    history.append(AIMessage(content=reply))
    state["reply"] = reply
    state["conversation_history"] = history
    return state


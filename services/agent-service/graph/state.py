from typing import Literal, TypedDict


IntentLabel = Literal[
    "greeting_chitchat",
    "out_of_domain",
    "comic_knowledge",
    "psychology_venting",
    "psychology_advice_seeking",
    "crisis_alert",
]

EmotionLabel = Literal[
    "neutral",
    "happy",
    "sad",
    "angry",
    "anxious",
    "surprised",
    "crisis",
]


class ConversationMessage(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentState(TypedDict, total=False):
    message: str
    conversation_id: str | None
    conversation_history: list[ConversationMessage]

    intent: IntentLabel
    emotion: EmotionLabel
    avatar_action: str
    reply: str
from graph.agents.chit_chat_agent import generate_response
from graph.nodes.avatar_node import avatar_node
from graph.nodes.emotion_node import emotion_node
from graph.nodes.intent_node import intent_node
from graph.state import AgentState


def run_pipeline(state: AgentState) -> AgentState:
	updates: AgentState = {}

	intent_updates = intent_node({**state, **updates})
	updates.update(intent_updates)

	emotion_updates = emotion_node({**state, **updates})
	updates.update(emotion_updates)

	avatar_updates = avatar_node({**state, **updates})
	updates.update(avatar_updates)

	response_updates = generate_response({**state, **updates})
	updates.update(response_updates)

	return updates

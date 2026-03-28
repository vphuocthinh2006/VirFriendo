export interface ChatRequest {
  message: string
  conversation_id: string | null
}

export interface ChatResponse {
  conversation_id: string
  reply: string
  detected_intent: string | null
  detected_emotion: string | null
  avatar_action: string | null
  bibliotherapy_suggestion: string | null
  user_message_count?: number | null
  relationship_level?: number | null
  relationship_level_up?: boolean
  new_relationship_level?: number | null
}

export interface ConversationSummary {
  id: string
  title: string | null
}

export interface MessageItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  /** Chunks để hiển thị từ từ (chỉ cho assistant). */
  chunks?: string[]
  /** Chỉ số chunk đang hiển thị (0 = chỉ chunk đầu). */
  visibleChunkIndex?: number
  detected_intent?: string | null
  detected_emotion?: string | null
  avatar_action?: string | null
}

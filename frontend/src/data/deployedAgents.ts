export type DeployedAgent = {
  id: string
  /** Shown on card — team / creator display name */
  authorName: string
  /** ISO date string */
  createdAt: string
  authorAvatarUrl: string
  coverImageUrl: string
  botName: string
  description: string
  /** Optional extra hashtags in detail view — only used when `genres` is empty */
  tags?: string[]
  /** System / opening prompt in detail PROMPT panel; falls back to description */
  prompt?: string
  /** Last update (ISO), for sidebar */
  updatedAt?: string
  /** e.g. Everyone */
  ratingLabel?: string
  /** Menu genre filters — lowercase ids from `agentGenres` (except `all`) */
  genres?: string[]
}

/** Static catalog — like/play counts come from GET /agents/{id}/stats */
export const DEPLOYED_AGENTS: DeployedAgent[] = [
  {
    id: 'tuq27',
    authorName: 'Bộ Tứ Random BS Go',
    createdAt: '2026-03-10T10:30:00Z',
    authorAvatarUrl:
      'https://ui-avatars.com/api/?name=Bo+Tu+Random+BS+Go&size=128&background=dbeafe&color=1e3a5f&bold=true',
    coverImageUrl: 'https://picsum.photos/seed/tuq27vf/800/450',
    botName: 'tuq27',
    description:
      'Your story-first Pally companion: warm tone, scene-style replies, and room to vent after a long day. Tuned on in-house dialogue data.',
    prompt:
      'You are a warm, scene-driven companion for Pally. Reply in short immersive scenes when it fits; offer space to vent after a long day. Stay in character; avoid lecturing.',
    updatedAt: '2026-03-21T14:00:00Z',
    ratingLabel: 'Everyone',
    genres: ['readable', 'entertainment', 'roleplay'],
  },
]

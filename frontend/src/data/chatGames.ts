/** Games shown on chat entry gate — names + CSS art id (no remote images). */
export type ChatGameItem = {
  id: 'chess' | 'caro' | 'tetris' | 'snake' | 'ringrealms'
  name: string
}

export const CHAT_GATE_GAMES: ChatGameItem[] = [
  { id: 'chess', name: 'Chess' },
  { id: 'caro', name: 'Caro' },
  { id: 'tetris', name: 'Tetris' },
  { id: 'snake', name: 'Snake' },
  { id: 'ringrealms', name: 'Ringrealms' },
]

/** Games shown on chat entry gate — image + name only */
export type ChatGameItem = {
  id: string
  name: string
  imageUrl: string
}

export const CHAT_GATE_GAMES: ChatGameItem[] = [
  {
    id: 'chess',
    name: 'Chess',
    imageUrl: 'https://images.unsplash.com/photo-1529699211952-734e80c4d42b?w=400&q=80',
  },
  {
    id: 'caro',
    name: 'Caro',
    imageUrl: 'https://images.unsplash.com/photo-1611996575749-79efa3fe1954?w=400&q=80',
  },
  {
    id: 'tetris',
    name: 'Tetris',
    imageUrl: 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80',
  },
  {
    id: 'snake',
    name: 'Snake',
    imageUrl: 'https://images.unsplash.com/photo-1550745165-9bc0b252726f?w=400&q=80',
  },
  {
    id: 'zeroad',
    name: 'Ancient RTS',
    imageUrl: 'https://images.unsplash.com/photo-1599708153386-62bf3ca671b9?w=400&q=80',
  },
]

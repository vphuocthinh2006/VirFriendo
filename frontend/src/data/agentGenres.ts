/** Lowercase ids — each agent lists `genres` that must intersect when a pill other than `all` is selected */
export const MENU_GENRE_PILLS = [
  { id: 'all', label: 'All' },
  { id: 'readable', label: 'Readable', icon: 'book' as const },
  { id: 'entertainment', label: 'Entertainment' },
  { id: 'code-industry-helper', label: 'Code / industry helper' },
  { id: 'roleplay', label: 'Roleplay' },
  { id: 'game', label: 'Game' },
] as const

/** Labels for detail hashtags — same wording as menu genre pills */
export function genreLabelsForAgent(genreIds: string[] | undefined): string[] {
  if (!genreIds?.length) return []
  const out: string[] = []
  for (const id of genreIds) {
    const pill = MENU_GENRE_PILLS.find((p) => p.id === id)
    if (pill && pill.id !== 'all') out.push(pill.label)
  }
  return out
}

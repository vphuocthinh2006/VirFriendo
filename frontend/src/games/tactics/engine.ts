/**
 * Turn-based tactics (grid). Low-fi ancient skirmish — one player action, then one bot action.
 */

export type Team = 'player' | 'enemy'
export type UnitKind = 'spear' | 'archer'

export type Unit = {
  id: string
  team: Team
  kind: UnitKind
  row: number
  col: number
  hp: number
}

export type GamePhase = 'playing' | 'player_win' | 'enemy_win'

export type GameState = {
  rows: number
  cols: number
  obstacleKeys: Set<string>
  units: Unit[]
  phase: GamePhase
}

export type GameAction =
  | { type: 'move'; unitId: string; toRow: number; toCol: number }
  | { type: 'attack'; unitId: string; targetId: string }

const SPEAR_HP = 4
const ARCHER_HP = 2
const DMG = 2

function key(r: number, c: number): string {
  return `${r},${c}`
}

function chebyshev(a: { row: number; col: number }, b: { row: number; col: number }): number {
  return Math.max(Math.abs(a.row - b.row), Math.abs(a.col - b.col))
}

function orthoDist(a: { row: number; col: number }, b: { row: number; col: number }): number {
  return Math.abs(a.row - b.row) + Math.abs(a.col - b.col)
}

export function createInitialState(): GameState {
  const rows = 5
  const cols = 6
  const obstacleKeys = new Set<string>([key(2, 2), key(2, 3)])
  const units: Unit[] = [
    { id: 'e1', team: 'enemy', kind: 'spear', row: 0, col: 1, hp: SPEAR_HP },
    { id: 'e2', team: 'enemy', kind: 'archer', row: 0, col: 2, hp: ARCHER_HP },
    { id: 'e3', team: 'enemy', kind: 'spear', row: 0, col: 3, hp: SPEAR_HP },
    { id: 'p1', team: 'player', kind: 'spear', row: 4, col: 1, hp: SPEAR_HP },
    { id: 'p2', team: 'player', kind: 'archer', row: 4, col: 2, hp: ARCHER_HP },
    { id: 'p3', team: 'player', kind: 'spear', row: 4, col: 3, hp: SPEAR_HP },
  ]
  return { rows, cols, obstacleKeys, units, phase: 'playing' }
}

function unitAt(state: GameState, r: number, c: number): Unit | undefined {
  return state.units.find((u) => u.row === r && u.col === c)
}

function inBounds(state: GameState, r: number, c: number): boolean {
  return r >= 0 && r < state.rows && c >= 0 && c < state.cols
}

export function canAttack(attacker: Unit, target: Unit): boolean {
  if (attacker.team === target.team) return false
  if (attacker.kind === 'spear') {
    return orthoDist(attacker, target) === 1
  }
  const d = chebyshev(attacker, target)
  return d >= 1 && d <= 2
}

export function legalMoves(state: GameState, unitId: string): { row: number; col: number }[] {
  const u = state.units.find((x) => x.id === unitId)
  if (!u || state.phase !== 'playing') return []
  const out: { row: number; col: number }[] = []
  const dirs = [
    [1, 0],
    [-1, 0],
    [0, 1],
    [0, -1],
  ]
  for (const [dr, dc] of dirs) {
    const r = u.row + dr
    const c = u.col + dc
    if (!inBounds(state, r, c)) continue
    if (state.obstacleKeys.has(key(r, c))) continue
    if (unitAt(state, r, c)) continue
    out.push({ row: r, col: c })
  }
  return out
}

export function legalAttackTargets(state: GameState, unitId: string): Unit[] {
  const u = state.units.find((x) => x.id === unitId)
  if (!u || state.phase !== 'playing') return []
  return state.units.filter((t) => t.team !== u.team && u.hp > 0 && t.hp > 0 && canAttack(u, t))
}

function resolveWinner(units: Unit[]): GamePhase {
  const p = units.filter((u) => u.team === 'player' && u.hp > 0)
  const e = units.filter((u) => u.team === 'enemy' && u.hp > 0)
  if (e.length === 0) return 'player_win'
  if (p.length === 0) return 'enemy_win'
  return 'playing'
}

export function applyAction(state: GameState, action: GameAction): GameState {
  if (state.phase !== 'playing') return state
  if (action.type === 'move') {
    const u = state.units.find((x) => x.id === action.unitId)
    if (!u || u.team !== 'player') return state
    const ok = legalMoves(state, u.id).some((m) => m.row === action.toRow && m.col === action.toCol)
    if (!ok) return state
    const units = state.units.map((x) =>
      x.id === u.id ? { ...x, row: action.toRow, col: action.toCol } : x,
    )
    return { ...state, units, phase: resolveWinner(units) }
  }
  const u = state.units.find((x) => x.id === action.unitId)
  const t = state.units.find((x) => x.id === action.targetId)
  if (!u || !t || u.team !== 'player' || !canAttack(u, t)) return state
  const targets = legalAttackTargets(state, u.id)
  if (!targets.some((x) => x.id === t.id)) return state
  const units = state.units.map((x) => {
    if (x.id !== t.id) return x
    return { ...x, hp: Math.max(0, x.hp - DMG) }
  })
  const phase = resolveWinner(units)
  return { ...state, units, phase }
}

/** One enemy action (greedy). Returns null if nothing to do. */
export function enemyBestAction(state: GameState): GameAction | null {
  const enemies = state.units.filter((u) => u.team === 'enemy' && u.hp > 0)
  if (enemies.length === 0) return null

  type Scored = { score: number; action: GameAction }
  const candidates: Scored[] = []

  const value = (u: Unit) => (u.kind === 'spear' ? 5 : 4)

  for (const u of enemies) {
    for (const t of legalAttackTargets(state, u.id)) {
      const kills = t.hp <= DMG ? 80 : 0
      const dmgScore = Math.min(DMG, t.hp) * 6
      const expose = 0
      candidates.push({
        score: kills + dmgScore + expose + value(t) * 0.5,
        action: { type: 'attack', unitId: u.id, targetId: t.id },
      })
    }
    for (const m of legalMoves(state, u.id)) {
      const moved = { ...u, row: m.row, col: m.col }
      let best = 0
      for (const p of state.units.filter((x) => x.team === 'player' && x.hp > 0)) {
        if (canAttack(moved, p)) best = Math.max(best, 25 + Math.min(DMG, p.hp) * 4)
      }
      const pAlive = state.units.filter((x) => x.team === 'player' && x.hp > 0)
      const closer =
        pAlive.length === 0
          ? 0
          : -Math.min(...pAlive.map((x) => chebyshev({ row: m.row, col: m.col }, x)))
      candidates.push({
        score: best + closer * 0.3,
        action: { type: 'move', unitId: u.id, toRow: m.row, toCol: m.col },
      })
    }
  }

  if (candidates.length === 0) return null
  candidates.sort((a, b) => b.score - a.score)
  return candidates[0].action
}

/** Apply an enemy move or attack. */
export function applyEnemyAction(state: GameState, action: GameAction): GameState {
  if (state.phase !== 'playing') return state
  if (action.type === 'move') {
    const u = state.units.find((x) => x.id === action.unitId)
    if (!u || u.team !== 'enemy') return state
    const ok = legalMoves(state, u.id).some((m) => m.row === action.toRow && m.col === action.toCol)
    if (!ok) return state
    const units = state.units.map((x) =>
      x.id === u.id ? { ...x, row: action.toRow, col: action.toCol } : x,
    )
    return { ...state, units, phase: resolveWinner(units) }
  }
  const u = state.units.find((x) => x.id === action.unitId)
  const t = state.units.find((x) => x.id === action.targetId)
  if (!u || !t || u.team !== 'enemy' || !canAttack(u, t)) return state
  const targets = legalAttackTargets(state, u.id)
  if (!targets.some((x) => x.id === t.id)) return state
  const units = state.units.map((x) => {
    if (x.id !== t.id) return x
    return { ...x, hp: Math.max(0, x.hp - DMG) }
  })
  const phase = resolveWinner(units)
  return { ...state, units, phase }
}

export function afterPlayerThenEnemy(state: GameState, playerAction: GameAction): GameState {
  let s = applyAction(state, playerAction)
  if (s.phase !== 'playing') return s
  const bot = enemyBestAction(s)
  if (!bot) return s
  s = applyEnemyAction(s, bot)
  return s
}

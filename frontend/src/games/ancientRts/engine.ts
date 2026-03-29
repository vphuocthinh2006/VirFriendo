import {
  BASE_DROP_RADIUS_TILES,
  BASE_MAX_HP,
  GATHER_RATE,
  MOVEMENT_PER_TURN,
  UNIT_STATS,
  type AnyEntity,
  type BaseEntity,
  type Owner,
  type ResourceEntity,
  type Terrain,
  type UnitEntity,
  type UnitKind,
} from './types'

export const MAP_W = 26
export const MAP_H = 26
export const TILE = 20
/** Ms between each tile step when resolving moves (visible march). */
export const MARCH_STEP_MS = 88
export { BASE_DROP_RADIUS_TILES, MOVEMENT_PER_TURN }

function mulberry32(seed: number) {
  return function () {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

let _nid = 0
function nid() {
  _nid += 1
  return `e${_nid}`
}

function inBounds(x: number, y: number) {
  return x >= 0 && y >= 0 && x < MAP_W && y < MAP_H
}

function chebyshev(ax: number, ay: number, bx: number, by: number) {
  return Math.max(Math.abs(ax - bx), Math.abs(ay - by))
}

function baseCenter(b: BaseEntity): [number, number] {
  return [b.x + b.w / 2, b.y + b.h / 2]
}

function inDropCircle(u: UnitEntity, b: BaseEntity): boolean {
  const [cx, cy] = baseCenter(b)
  const ux = u.x + 0.5
  const uy = u.y + 0.5
  const dx = ux - cx
  const dy = uy - cy
  return Math.sqrt(dx * dx + dy * dy) <= BASE_DROP_RADIUS_TILES
}

export type PendingMarshalChoice = { attackerId: string; marshalId: string }

export class AncientRtsEngine {
  rng: () => number
  seed: number
  terrain: Terrain[][]
  entities: Map<string, AnyEntity>
  wood: [number, number]
  gold: [number, number]
  selectedId: string | null
  winner: 0 | 1 | null
  /** Whose turn to give orders: 0 = you, 1 = AI (orders applied on End Turn) */
  turnOwner: Owner = 0
  turnNumber = 1
  pendingMarshalChoice: PendingMarshalChoice | null = null
  /** Set each frame from the UI for path / selection / range VFX (ms, e.g. performance.now()). */
  visualTimeMs = 0
  /** After End turn: resolve paths one tile at a time so units visibly march. */
  private marchInProgress: 'none' | 'player' | 'ai' = 'none'
  private marchAccumMs = 0
  constructor(seed = Date.now() & 0xffff) {
    this.seed = seed
    this.rng = mulberry32(seed)
    this.terrain = []
    this.entities = new Map()
    this.wood = [120, 120]
    this.gold = [80, 80]
    this.selectedId = null
    this.winner = null
    this.reset()
  }

  reset() {
    _nid = 0
    this.rng = mulberry32(this.seed)
    this.terrain = this.buildTerrain()
    this.entities.clear()
    this.wood = [120, 120]
    this.gold = [80, 80]
    this.selectedId = null
    this.winner = null
    this.turnOwner = 0
    this.turnNumber = 1
    this.pendingMarshalChoice = null
    this.marchInProgress = 'none'
    this.marchAccumMs = 0
    const pBase: BaseEntity = {
      id: nid(),
      kind: 'base',
      owner: 0,
      x: 2,
      y: MAP_H - 4,
      w: 2,
      h: 2,
      hp: BASE_MAX_HP,
      maxHp: BASE_MAX_HP,
    }
    const eBase: BaseEntity = {
      id: nid(),
      kind: 'base',
      owner: 1,
      x: MAP_W - 4,
      y: 2,
      w: 2,
      h: 2,
      hp: BASE_MAX_HP,
      maxHp: BASE_MAX_HP,
    }
    this.entities.set(pBase.id, pBase)
    this.entities.set(eBase.id, eBase)

    // Spawn units BEFORE random resources — a tree/gold on (4,22) etc. used to block spawnUnit() → empty map.
    this.spawnUnit(0, 'villager', pBase.x + pBase.w, pBase.y)
    this.spawnUnit(1, 'villager', eBase.x - 1, eBase.y + eBase.h - 1)
    const pSpear = this.freeAdjacentGrass(pBase)
    if (pSpear) this.spawnUnit(0, 'spearman', pSpear[0], pSpear[1])
    const eSpear = this.freeAdjacentGrass(eBase)
    if (eSpear) this.spawnUnit(1, 'spearman', eSpear[0], eSpear[1])

    this.placeResources()
    this.beginPlayerTurn()
  }

  private buildTerrain(): Terrain[][] {
    const g: Terrain[][] = []
    for (let y = 0; y < MAP_H; y++) {
      const row: Terrain[] = []
      for (let x = 0; x < MAP_W; x++) {
        const n = this.rng()
        row.push(n < 0.12 ? 'water' : 'grass')
      }
      g.push(row)
    }
    for (const bx of [2, MAP_W - 4]) {
      for (const by of [2, MAP_H - 4]) {
        for (let dy = 0; dy < 2; dy++) {
          for (let dx = 0; dx < 2; dx++) {
            if (inBounds(bx + dx, by + dy)) g[by + dy][bx + dx] = 'grass'
          }
        }
      }
    }
    return g
  }

  private placeResources() {
    const tries = 80
    for (let i = 0; i < tries; i++) {
      const x = 4 + Math.floor(this.rng() * (MAP_W - 8))
      const y = 4 + Math.floor(this.rng() * (MAP_H - 8))
      if (this.terrain[y][x] !== 'grass') continue
      if (this.occupiedByBase(x, y)) continue
      if (this.unitAt(x, y)) continue
      const res: ResourceEntity = {
        id: nid(),
        kind: 'resource',
        res: this.rng() < 0.55 ? 'tree' : 'gold',
        x,
        y,
        amount: 220 + Math.floor(this.rng() * 120),
      }
      this.entities.set(res.id, res)
    }
  }

  private occupiedByBase(x: number, y: number): boolean {
    for (const e of this.entities.values()) {
      if (e.kind !== 'base') continue
      const b = e as BaseEntity
      if (x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) return true
    }
    return false
  }

  private baseFor(owner: Owner): BaseEntity | null {
    for (const e of this.entities.values()) {
      if (e.kind === 'base' && e.owner === owner) return e as BaseEntity
    }
    return null
  }

  spawnUnit(owner: Owner, unit: UnitKind, x: number, y: number): UnitEntity | null {
    if (!inBounds(x, y) || this.terrain[y][x] !== 'grass') return null
    if (this.unitAt(x, y)) return null
    if (this.blockedTile(x, y, null)) return null
    const st = UNIT_STATS[unit]
    const u: UnitEntity = {
      id: nid(),
      kind: 'unit',
      owner,
      unit,
      x,
      y,
      hp: st.maxHp,
      maxHp: st.maxHp,
      dmg: st.dmg,
      speed: st.speed,
      carryWood: 0,
      carryGold: 0,
      path: [],
      goal: null,
      attackId: null,
      gatherId: null,
      lastAttack: 0,
      lastGather: 0,
      stepCd: 0,
      skillUsedThisTurn: false,
      hustleDoubleGather: false,
      nextBlock: false,
      buffNextAttackBonus: 0,
    }
    this.entities.set(u.id, u)
    return u
  }

  tryTrainExpanded(owner: Owner, kind: UnitKind): boolean {
    if (this.marchInProgress !== 'none') return false
    const st = UNIT_STATS[kind]
    if (!st.trainable) return false
    if (this.wood[owner] < st.costW || this.gold[owner] < st.costG) return false
    const b = this.baseFor(owner)
    if (!b) return false
    const spot = this.freeAdjacentGrass(b)
    if (!spot) return false
    this.wood[owner] -= st.costW
    this.gold[owner] -= st.costG
    this.spawnUnit(owner, kind, spot[0], spot[1])
    return true
  }

  resolveMarshalChoice(choice: 'capture' | 'eliminate') {
    if (!this.pendingMarshalChoice) return
    const m = this.entities.get(this.pendingMarshalChoice.marshalId) as UnitEntity | undefined
    this.pendingMarshalChoice = null
    if (!m || m.kind !== 'unit' || m.unit !== 'marshal') return
    if (choice === 'eliminate') {
      this.entities.delete(m.id)
      return
    }
    m.owner = 0
    m.unit = 'knight'
    m.maxHp = UNIT_STATS.knight.maxHp
    m.hp = Math.floor(UNIT_STATS.knight.maxHp * 0.55)
    m.dmg = UNIT_STATS.knight.dmg
    m.speed = UNIT_STATS.knight.speed
    m.skillUsedThisTurn = false
    m.hustleDoubleGather = false
  }

  tryUseSkill(owner: Owner): boolean {
    if (this.pendingMarshalChoice || this.turnOwner !== 0 || this.marchInProgress !== 'none') return false
    const sel = this.selectedId ? this.entities.get(this.selectedId) : null
    if (!sel || sel.kind !== 'unit') return false
    const u = sel as UnitEntity
    if (u.owner !== owner) return false
    if (u.skillUsedThisTurn) return false

    switch (u.unit) {
      case 'villager':
        u.hustleDoubleGather = true
        break
      case 'spearman':
        u.nextBlock = true
        break
      case 'archer':
        u.buffNextAttackBonus += 10
        break
      case 'knight':
        u.buffNextAttackBonus += 16
        break
      default:
        return false
    }
    u.skillUsedThisTurn = true
    return true
  }

  beginPlayerTurn() {
    this.turnOwner = 0
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      u.skillUsedThisTurn = false
      u.hustleDoubleGather = false
    }
  }

  /** True while moves from End turn are playing out tile-by-tile. */
  get marching() {
    return this.marchInProgress !== 'none'
  }

  /**
   * Drive animated march after endPlayerTurn. Call from rAF with ~frame delta.
   * Returns true when React should refresh (combat/round/winner changed).
   */
  tickMarchFrame(deltaMs: number): boolean {
    if (this.marchInProgress === 'none') return false
    if (this.winner != null) {
      this.marchInProgress = 'none'
      this.marchAccumMs = 0
      return true
    }
    this.marchAccumMs += deltaMs
    if (this.marchAccumMs < MARCH_STEP_MS) return false
    this.marchAccumMs -= MARCH_STEP_MS

    if (!this.hasAnyPath()) {
      this.finishMarchSegment()
      return true
    }
    const moved = this.flushPathsOneStep()
    if (!this.hasAnyPath()) {
      this.finishMarchSegment()
      return true
    }
    if (!moved) {
      this.flushPaths()
      this.finishMarchSegment()
      return true
    }
    return false
  }

  /** Call when you finish issuing moves / training for this round. */
  endPlayerTurn() {
    if (this.winner != null || this.pendingMarshalChoice) return
    if (this.turnOwner !== 0) return
    if (this.marchInProgress !== 'none') return

    if (this.hasAnyPathForOwner(0)) {
      this.marchInProgress = 'player'
      this.marchAccumMs = 0
      return
    }
    this.afterPlayerMarchSync()
  }

  private finishMarchSegment() {
    const phase = this.marchInProgress
    this.marchInProgress = 'none'
    this.marchAccumMs = 0
    if (phase === 'player') this.afterPlayerMarchSync()
    else if (phase === 'ai') this.finishAiHalf()
  }

  private afterPlayerMarchSync() {
    this.resolveCombatGather()
    this.checkWin()
    if (this.winner != null) return

    this.runAiTurn()
    if (this.hasAnyPathForOwner(1)) {
      this.marchInProgress = 'ai'
      this.marchAccumMs = 0
      return
    }
    this.finishAiHalf()
  }

  private finishAiHalf() {
    this.resolveCombatGather()
    this.checkWin()
    if (this.winner != null) return
    this.turnNumber += 1
    this.beginPlayerTurn()
  }

  private hasAnyPath(): boolean {
    for (const e of this.entities.values()) {
      if (e.kind === 'unit' && (e as UnitEntity).path.length > 0) return true
    }
    return false
  }

  private hasAnyPathForOwner(owner: Owner): boolean {
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      if (u.owner === owner && u.path.length > 0) return true
    }
    return false
  }

  /** One tile forward for every unit that still has path (same beat for all). */
  private flushPathsOneStep(): boolean {
    let anyMoved = false
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      if (u.path.length === 0) continue
      const [nx, ny] = u.path[0]
      const block = this.unitAt(nx, ny)
      if (block && block.id !== u.id) continue
      u.path.shift()
      u.x = nx
      u.y = ny
      anyMoved = true
    }
    return anyMoved
  }

  private flushPaths() {
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      while (u.path.length > 0) {
        const [nx, ny] = u.path[0]
        const block = this.unitAt(nx, ny)
        if (block && block.id !== u.id) break
        u.path.shift()
        u.x = nx
        u.y = ny
      }
      u.stepCd = 0
    }
  }

  private freeAdjacentGrass(b: BaseEntity): [number, number] | null {
    const cands: [number, number][] = []
    for (let y = b.y - 1; y <= b.y + b.h; y++) {
      for (let x = b.x - 1; x <= b.x + b.w; x++) {
        if (x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) continue
        if (inBounds(x, y) && this.terrain[y][x] === 'grass' && !this.blockedTile(x, y, null) && !this.unitAt(x, y)) {
          cands.push([x, y])
        }
      }
    }
    if (cands.length === 0) return null
    return cands[Math.floor(this.rng() * cands.length)]
  }

  unitAt(x: number, y: number): UnitEntity | null {
    for (const e of this.entities.values()) {
      if (e.kind === 'unit' && e.x === x && e.y === y) return e as UnitEntity
    }
    return null
  }

  resourceAt(x: number, y: number): ResourceEntity | null {
    for (const e of this.entities.values()) {
      if (e.kind === 'resource' && e.x === x && e.y === y) return e as ResourceEntity
    }
    return null
  }

  private blockedTile(x: number, y: number, mover: UnitEntity | null): boolean {
    if (this.terrain[y][x] === 'water') return true
    for (const e of this.entities.values()) {
      if (e.kind === 'base') {
        const b = e as BaseEntity
        const inside = x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h
        if (!inside) continue
        if (mover && b.owner === mover.owner) return false
        return true
      }
      if (e.kind === 'resource' && e.x === x && e.y === y) return true
    }
    return false
  }

  neighbors8Fixed(x: number, y: number): [number, number][] {
    const out: [number, number][] = []
    for (let dy = -1; dy <= 1; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        if (dx === 0 && dy === 0) continue
        const nx = x + dx
        const ny = y + dy
        if (inBounds(nx, ny)) out.push([nx, ny])
      }
    }
    return out
  }

  bfs(start: [number, number], goalTest: (x: number, y: number) => boolean, mover: UnitEntity): [number, number][] {
    const [sx, sy] = start
    const q: [number, number][] = [[sx, sy]]
    const prev = new Map<string, string | null>()
    const sk = `${sx},${sy}`
    prev.set(sk, null)
    while (q.length) {
      const [x, y] = q.shift()!
      const k = `${x},${y}`
      if (goalTest(x, y)) {
        const path: [number, number][] = []
        let cur: string | null = k
        while (cur && cur !== sk) {
          const [cx, cy] = cur.split(',').map(Number)
          path.push([cx, cy])
          cur = prev.get(cur) ?? null
        }
        path.reverse()
        return path
      }
      for (const [nx, ny] of this.neighbors8Fixed(x, y)) {
        const nk = `${nx},${ny}`
        if (prev.has(nk)) continue
        if (this.blockedTileForPath(nx, ny, mover, sx, sy)) continue
        prev.set(nk, k)
        q.push([nx, ny])
      }
    }
    return []
  }

  /** Reachable tiles in ≤maxSteps moves (8-dir); values are step counts from start (start = 0). */
  private bfsDistanceField(start: [number, number], maxSteps: number, mover: UnitEntity): Map<string, number> {
    const [sx, sy] = start
    const out = new Map<string, number>()
    const q: [number, number][] = [[sx, sy]]
    out.set(`${sx},${sy}`, 0)
    while (q.length) {
      const [x, y] = q.shift()!
      const k = `${x},${y}`
      const cd = out.get(k)!
      if (cd >= maxSteps) continue
      for (const [nx, ny] of this.neighbors8Fixed(x, y)) {
        const nk = `${nx},${ny}`
        if (out.has(nk)) continue
        if (this.blockedTileForPath(nx, ny, mover, sx, sy)) continue
        out.set(nk, cd + 1)
        q.push([nx, ny])
      }
    }
    return out
  }

  private blockedTileForPath(x: number, y: number, mover: UnitEntity, sx: number, sy: number): boolean {
    if (x === sx && y === sy) return false
    if (this.terrain[y][x] === 'water') return true
    const u = this.unitAt(x, y)
    if (u && u.id !== mover.id) return true
    for (const e of this.entities.values()) {
      if (e.kind === 'base') {
        const b = e as BaseEntity
        const inside = x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h
        if (!inside) continue
        if (b.owner === mover.owner) return false
        return true
      }
      if (e.kind === 'resource' && e.x === x && e.y === y) return true
    }
    return false
  }

  bestAdjacentTo(tx: number, ty: number, mover: UnitEntity): [number, number] | null {
    const adj = this.neighbors8Fixed(tx, ty).filter(
      ([ax, ay]) => !this.blockedTileForPath(ax, ay, mover, mover.x, mover.y) || (ax === mover.x && ay === mover.y)
    )
    if (adj.length === 0) return null
    let best = adj[0]
    let bestD = chebyshev(mover.x, mover.y, best[0], best[1])
    for (const a of adj.slice(1)) {
      const d = chebyshev(mover.x, mover.y, a[0], a[1])
      if (d < bestD) {
        best = a
        bestD = d
      }
    }
    return best
  }

  private bestStandTileForRanged(u: UnitEntity, foe: UnitEntity): [number, number] | null {
    const r = UNIT_STATS[u.unit].rangedMax
    if (r <= 0) return null
    let best: [number, number] | null = null
    let bestD = 1e9
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        const d = chebyshev(x, y, foe.x, foe.y)
        if (d < 1 || d > r) continue
        if (this.blockedTileForPath(x, y, u, u.x, u.y)) continue
        const occ = this.unitAt(x, y)
        if (occ && occ.id !== u.id) continue
        const md = chebyshev(u.x, u.y, x, y)
        if (md < bestD) {
          bestD = md
          best = [x, y]
        }
      }
    }
    return best
  }

  bestAdjacentToBase(b: BaseEntity, mover: UnitEntity): [number, number] | null {
    let best: [number, number] | null = null
    let bestD = 1e9
    for (let y = b.y - 1; y <= b.y + b.h; y++) {
      for (let x = b.x - 1; x <= b.x + b.w; x++) {
        if (x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h) continue
        if (!inBounds(x, y)) continue
        if (this.blockedTileForPath(x, y, mover, mover.x, mover.y) && (x !== mover.x || y !== mover.y)) continue
        const d = chebyshev(mover.x, mover.y, x, y)
        if (d < bestD) {
          bestD = d
          best = [x, y]
        }
      }
    }
    return best
  }

  issueMove(u: UnitEntity, gx: number, gy: number) {
    const res = this.resourceAt(gx, gy)
    const targetU = this.unitAt(gx, gy)
    let goalX = gx
    let goalY = gy

    if (res && u.unit === 'villager') {
      const adj = this.bestAdjacentTo(res.x, res.y, u)
      if (!adj) return
      goalX = adj[0]
      goalY = adj[1]
    } else if (targetU && targetU.owner !== u.owner) {
      if (u.unit === 'archer' && UNIT_STATS.archer.rangedMax > 0) {
        const stand = this.bestStandTileForRanged(u, targetU)
        if (!stand) return
        goalX = stand[0]
        goalY = stand[1]
      } else {
        const adj = this.bestAdjacentTo(targetU.x, targetU.y, u)
        if (!adj) return
        goalX = adj[0]
        goalY = adj[1]
      }
    } else {
      for (const e of this.entities.values()) {
        if (e.kind !== 'base') continue
        const b = e as BaseEntity
        if (b.owner === u.owner) continue
        const inside = gx >= b.x && gx < b.x + b.w && gy >= b.y && gy < b.y + b.h
        if (inside) {
          const adj = this.bestAdjacentToBase(b, u)
          if (!adj) return
          goalX = adj[0]
          goalY = adj[1]
          break
        }
      }
    }

    const path = this.bfs([u.x, u.y], (x, y) => x === goalX && y === goalY, u)
    const mov = MOVEMENT_PER_TURN[u.unit]
    // BFS returns [] when start === goal (already adjacent / in range to strike or gather).
    // Previously we returned early so clicks on enemies did nothing and stale paths could remain.
    if (path.length === 0) {
      if (u.x === goalX && u.y === goalY) {
        u.path = []
        u.goal = [goalX, goalY]
        u.attackId = null
        u.gatherId = null
      }
      return
    }
    if (path.length > mov) {
      if (u.owner === 0) return
      const trimmed = path.slice(0, mov)
      u.path = trimmed
      const last = trimmed[trimmed.length - 1]!
      u.goal = [last[0], last[1]]
    } else {
      u.path = path
      u.goal = [goalX, goalY]
    }
    u.attackId = null
    u.gatherId = null
  }

  selectAt(gx: number, gy: number, owner: Owner) {
    if (this.pendingMarshalChoice) return
    if (this.marchInProgress !== 'none') return
    if (owner === 0 && this.turnOwner !== 0) return
    for (const e of this.entities.values()) {
      if (e.kind === 'base' && e.owner === owner) {
        const b = e as BaseEntity
        if (gx >= b.x && gx < b.x + b.w && gy >= b.y && gy < b.y + b.h) {
          this.selectedId = b.id
          return
        }
      }
    }
    const u = this.unitAt(gx, gy)
    if (u && u.owner === owner) {
      this.selectedId = u.id
      return
    }
    const sel = this.selectedId ? (this.entities.get(this.selectedId) as UnitEntity | undefined) : null
    if (sel && sel.kind === 'unit' && sel.owner === owner) {
      this.issueMove(sel, gx, gy)
    }
  }

  private canAttack(u: UnitEntity, foe: UnitEntity): boolean {
    const d = chebyshev(u.x, u.y, foe.x, foe.y)
    if (d < 1) return false
    const st = UNIT_STATS[u.unit]
    if (st.rangedMax > 0) return d <= st.rangedMax
    return d <= st.meleeRange
  }

  /** Legacy hook — simulation is turn-based; no-op. */
  tick(_dt: number) {
    this.checkWin()
  }

  /** One combat / gather pass after movement (turn-based). */
  private resolveCombatGather() {
    if (this.pendingMarshalChoice) return
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity

      if (u.unit === 'villager') {
        const own = this.baseFor(u.owner)
        if (own && inDropCircle(u, own) && (u.carryWood > 0 || u.carryGold > 0)) {
          this.wood[u.owner] += u.carryWood
          this.gold[u.owner] += u.carryGold
          u.carryWood = 0
          u.carryGold = 0
          continue
        }
        const res = this.neighbors8Fixed(u.x, u.y)
          .map(([x, y]) => this.resourceAt(x, y))
          .find((r) => r && r.amount > 0)
        if (res) {
          let amt = Math.min(GATHER_RATE, res.amount)
          if (u.hustleDoubleGather) {
            amt = Math.min(GATHER_RATE * 2, res.amount)
            u.hustleDoubleGather = false
          }
          if (res.res === 'tree') u.carryWood += amt
          else u.carryGold += amt
          res.amount -= amt
          if (res.amount <= 0) this.entities.delete(res.id)
          continue
        }
        /* else: no gather this tick — can still melee (fixes “farmer can’t attack”). */
      }

      let foe: UnitEntity | null = null
      let bestPri = 1e9
      for (const o of this.entities.values()) {
        if (o.kind !== 'unit') continue
        const ou = o as UnitEntity
        if (ou.owner === u.owner) continue
        if (!this.canAttack(u, ou)) continue
        const d = chebyshev(u.x, u.y, ou.x, ou.y)
        const pri = UNIT_STATS[u.unit].rangedMax > 0 ? d * 10 + (d === 1 ? 0 : 2) : d
        if (pri < bestPri) {
          bestPri = pri
          foe = ou
        }
      }

      if (foe) {
        let dmg = u.dmg + u.buffNextAttackBonus
        if (foe.unit === 'marshal' && foe.owner === 1 && u.owner === 0 && foe.hp - dmg <= 0) {
          this.pendingMarshalChoice = { attackerId: u.id, marshalId: foe.id }
          continue
        }
        if (u.buffNextAttackBonus > 0) u.buffNextAttackBonus = 0
        if (foe.nextBlock) {
          foe.nextBlock = false
          dmg = 0
        }
        foe.hp -= dmg
        if (foe.hp <= 0) this.entities.delete(foe.id)
        continue
      }

      for (const o of this.entities.values()) {
        if (o.kind !== 'base') continue
        const b = o as BaseEntity
        if (b.owner === u.owner) continue
        let hit = false
        for (let y = b.y; y < b.y + b.h && !hit; y++) {
          for (let x = b.x; x < b.x + b.w && !hit; x++) {
            if (chebyshev(u.x, u.y, x, y) <= 1) hit = true
          }
        }
        if (hit) {
          b.hp -= u.dmg
          if (b.hp <= 0) {
            this.winner = u.owner
            return
          }
          break
        }
      }
    }
  }

  private runAiTurn() {
    if (this.winner != null || this.pendingMarshalChoice) return
    const owner = 1 as Owner
    const b = this.baseFor(owner)
    if (!b) return
    if (this.rng() < 0.2) {
      const pool: UnitKind[] = ['spearman', 'villager', 'archer', 'knight']
      const prefer = pool[Math.floor(this.rng() * pool.length)]
      if (!this.tryTrainExpanded(owner, prefer)) {
        for (const k of pool) {
          if (this.tryTrainExpanded(owner, k)) break
        }
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind !== 'unit' || e.owner !== owner) continue
      const u = e as UnitEntity
      if (u.path.length > 0) continue

      if (u.unit === 'villager') {
        if (u.carryWood + u.carryGold > 40 && b) {
          const adj = this.bestAdjacentToBase(b, u)
          if (adj) this.issueMove(u, adj[0], adj[1])
          continue
        }
        let best: ResourceEntity | null = null
        let bd = 1e9
        for (const r of this.entities.values()) {
          if (r.kind !== 'resource' || r.amount <= 0) continue
          const res = r as ResourceEntity
          const d = chebyshev(res.x, res.y, u.x, u.y)
          if (d < bd) {
            bd = d
            best = res
          }
        }
        if (best) this.issueMove(u, best.x, best.y)
        continue
      }

      let target: UnitEntity | null = null
      let td = 1e9
      for (const o of this.entities.values()) {
        if (o.kind !== 'unit') continue
        const ou = o as UnitEntity
        if (ou.owner === owner) continue
        const d = chebyshev(ou.x, ou.y, u.x, u.y)
        if (d < td) {
          td = d
          target = ou
        }
      }
      const pb = this.baseFor(0 as Owner)
      if (target) this.issueMove(u, target.x, target.y)
      else if (pb) this.issueMove(u, pb.x, pb.y)
    }
  }

  private checkWin() {
    if (this.winner != null) return
    const b0 = this.baseFor(0)
    const b1 = this.baseFor(1)
    if (b0 && b0.hp <= 0) this.winner = 1
    else if (b1 && b1.hp <= 0) this.winner = 0
  }

  render(ctx: CanvasRenderingContext2D) {
    ctx.imageSmoothingEnabled = false
    const tSec = this.visualTimeMs * 0.001
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        const terr = this.terrain[y][x]
        ctx.fillStyle = terr === 'water' ? '#2a4a6a' : '#3d6b3d'
        ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
        ctx.strokeStyle = 'rgba(0,0,0,0.12)'
        ctx.strokeRect(x * TILE, y * TILE, TILE, TILE)
      }
    }

    const selEnt = this.selectedId && this.turnOwner === 0 ? this.entities.get(this.selectedId) : undefined
    const selUnit = selEnt?.kind === 'unit' ? (selEnt as UnitEntity) : undefined
    if (selUnit && selUnit.owner === 0 && this.marchInProgress === 'none') {
      const maxM = MOVEMENT_PER_TURN[selUnit.unit]
      const dist = this.bfsDistanceField([selUnit.x, selUnit.y], maxM, selUnit)
      for (const [k, d] of dist) {
        if (d < 1 || d > maxM) continue
        const [tx, ty] = k.split(',').map(Number)
        ctx.fillStyle = 'rgba(34, 197, 94, 0.28)'
        ctx.fillRect(tx * TILE, ty * TILE, TILE, TILE)
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind === 'resource') {
        const r = e as ResourceEntity
        ctx.fillStyle = r.res === 'tree' ? '#1a5c2e' : '#b8860b'
        ctx.fillRect(r.x * TILE + 3, r.y * TILE + 3, TILE - 6, TILE - 6)
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind === 'base') {
        const b = e as BaseEntity
        const [cx, cy] = baseCenter(b)
        const px = cx * TILE
        const py = cy * TILE
        const r = BASE_DROP_RADIUS_TILES * TILE
        ctx.strokeStyle = b.owner === 0 ? 'rgba(96,165,250,0.42)' : 'rgba(248,113,113,0.42)'
        ctx.lineWidth = 1.5
        ctx.setLineDash([5, 6])
        ctx.lineDashOffset = -(tSec * 14) % 22
        ctx.beginPath()
        ctx.arc(px, py, r, 0, Math.PI * 2)
        ctx.stroke()
        ctx.setLineDash([])
        ctx.lineDashOffset = 0

        ctx.fillStyle = b.owner === 0 ? 'rgba(40,80,160,0.85)' : 'rgba(160,50,50,0.85)'
        ctx.fillRect(b.x * TILE, b.y * TILE, b.w * TILE, b.h * TILE)
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 2
        ctx.strokeRect(b.x * TILE + 1, b.y * TILE + 1, b.w * TILE - 2, b.h * TILE - 2)
        const pct = b.hp / b.maxHp
        ctx.fillStyle = '#222'
        ctx.fillRect(b.x * TILE + 2, b.y * TILE + b.h * TILE - 5, b.w * TILE - 4, 4)
        ctx.fillStyle = '#4ade80'
        ctx.fillRect(b.x * TILE + 2, b.y * TILE + b.h * TILE - 5, (b.w * TILE - 4) * pct, 4)
      }
    }

    if (selUnit && selUnit.owner === 0 && selUnit.path.length > 0 && this.marchInProgress === 'none') {
      ctx.strokeStyle = 'rgba(253, 224, 71, 0.78)'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.lineJoin = 'round'
      ctx.beginPath()
      let px = selUnit.x * TILE + TILE / 2
      let py = selUnit.y * TILE + TILE / 2
      ctx.moveTo(px, py)
      for (const [gx, gy] of selUnit.path) {
        px = gx * TILE + TILE / 2
        py = gy * TILE + TILE / 2
        ctx.lineTo(px, py)
      }
      ctx.stroke()
      ctx.setLineDash([])
      ctx.lineDashOffset = 0
    }

    const labelChar = (u: UnitEntity) => {
      switch (u.unit) {
        case 'villager':
          return 'V'
        case 'spearman':
          return 'S'
        case 'archer':
          return 'A'
        case 'knight':
          return 'K'
        case 'marshal':
          return 'M'
        default:
          return '?'
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      const cx = u.x * TILE + TILE / 2
      const cy = u.y * TILE + TILE / 2
      ctx.fillStyle = u.owner === 0 ? '#60a5fa' : '#f87171'
      ctx.beginPath()
      ctx.arc(cx, cy, TILE * 0.32, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 11px system-ui,sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(labelChar(u), cx, cy)
    }

    if (selUnit && selUnit.owner === 0 && this.marchInProgress === 'none') {
      for (const e of this.entities.values()) {
        if (e.kind !== 'unit') continue
        const ou = e as UnitEntity
        if (ou.owner === selUnit.owner) continue
        if (!this.canAttack(selUnit, ou)) continue
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.92)'
        ctx.lineWidth = 2.5
        ctx.strokeRect(ou.x * TILE - 1, ou.y * TILE - 1, TILE + 2, TILE + 2)
      }
    }

    if (this.selectedId) {
      const e = this.entities.get(this.selectedId)
      if (e?.kind === 'unit') {
        const u = e as UnitEntity
        ctx.strokeStyle = '#fde047'
        ctx.lineWidth = 2
        ctx.strokeRect(u.x * TILE + 1, u.y * TILE + 1, TILE - 2, TILE - 2)
      }
    }

    ctx.fillStyle = 'rgba(15, 12, 8, 0.82)'
    ctx.fillRect(4, 4, MAP_W * TILE - 8, 38)
    ctx.fillStyle = 'rgba(232, 197, 71, 0.95)'
    ctx.font = 'bold 10px system-ui, sans-serif'
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    const movHint = selUnit && selUnit.owner === 0 ? ` · this unit: ${MOVEMENT_PER_TURN[selUnit.unit]} steps max` : ''
    const line1 =
      this.winner != null
        ? 'Game over'
        : this.pendingMarshalChoice
          ? 'Choose: capture or eliminate'
          : `Round ${this.turnNumber} — green = tiles you can reach${movHint}`
    const line2 =
      this.winner != null || this.pendingMarshalChoice
        ? ''
        : this.marchInProgress !== 'none'
          ? 'Marching — units move one tile at a time'
          : 'Red frame = can attack · Yellow = planned path · End turn to march & fight'
    ctx.fillText(line1, 10, 14)
    if (line2) ctx.fillText(line2, 10, 30)
  }
}

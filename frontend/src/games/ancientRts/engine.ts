import {
  BASE_MAX_HP,
  GATHER_RATE,
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

export type DamagePopupEvent = { gx: number; gy: number; value: number; kind: 'hit' | 'base' | 'gather' }

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

export class AncientRtsEngine {
  rng: () => number
  seed: number
  terrain: Terrain[][]
  entities: Map<string, AnyEntity>
  wood: [number, number]
  gold: [number, number]
  selectedId: string | null
  winner: 0 | 1 | null
  /** 0 = your turn, 1 = AI turn (only used between rounds; AI resolves synchronously). */
  turnOwner: 0 | 1
  /** Player units (owner 0) that already moved/acted this player turn. */
  actedThisPlayerTurn: Set<string>
  /** Step-by-step movement animation for the human player (AI still resolves instantly). */
  moveAnimation: { unitId: string; path: [number, number][]; step: number } | null = null
  private _damagePopups: DamagePopupEvent[] = []

  constructor(seed = Date.now() & 0xffff) {
    this.seed = seed
    this.rng = mulberry32(seed)
    this.terrain = []
    this.entities = new Map()
    this.wood = [120, 120]
    this.gold = [80, 80]
    this.selectedId = null
    this.winner = null
    this.turnOwner = 0
    this.actedThisPlayerTurn = new Set()
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
    this.actedThisPlayerTurn = new Set()
    this.moveAnimation = null
    this._damagePopups = []

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

    this.placeResources()

    this.spawnUnit(0, 'villager', pBase.x + pBase.w, pBase.y)
    this.spawnUnit(1, 'villager', eBase.x - 1, eBase.y + eBase.h - 1)
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
    }
    this.entities.set(u.id, u)
    return u
  }

  tryTrainExpanded(owner: Owner, kind: UnitKind): boolean {
    if (owner === 0 && this.moveAnimation) return false
    if (owner === 0 && this.turnOwner !== 0) return false
    if (owner === 1 && this.turnOwner !== 1) return false
    const st = UNIT_STATS[kind]
    if (this.wood[owner] < st.costW || this.gold[owner] < st.costG) return false
    const b = this.baseFor(owner)
    if (!b) return false
    const spot = this.freeAdjacentGrass(b)
    if (!spot) return false
    this.wood[owner] -= st.costW
    this.gold[owner] -= st.costG
    const u = this.spawnUnit(owner, kind, spot[0], spot[1])
    if (!u) return false
    if (owner === 0) this.actedThisPlayerTurn.add(u.id)
    return true
  }

  private freeAdjacentGrass(b: BaseEntity): [number, number] | null {
    const cands: [number, number][] = []
    for (let y = b.y - 1; y <= b.y + b.h; y++) {
      for (let x = b.x - 1; x <= b.x + b.w; x++) {
        if (x < b.x || x >= b.x + b.w || y < b.y || y >= b.y + b.h) {
          if (inBounds(x, y) && this.terrain[y][x] === 'grass' && !this.blockedTile(x, y, null) && !this.unitAt(x, y)) {
            cands.push([x, y])
          }
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

  neighbors4Fixed(x: number, y: number): [number, number][] {
    const out: [number, number][] = []
    if (inBounds(x + 1, y)) out.push([x + 1, y])
    if (inBounds(x - 1, y)) out.push([x - 1, y])
    if (inBounds(x, y + 1)) out.push([x, y + 1])
    if (inBounds(x, y - 1)) out.push([x, y - 1])
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
      for (const [nx, ny] of this.neighbors4Fixed(x, y)) {
        const nk = `${nx},${ny}`
        if (prev.has(nk)) continue
        if (this.blockedTileForPath(nx, ny, mover, sx, sy)) continue
        prev.set(nk, k)
        q.push([nx, ny])
      }
    }
    return []
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
    const adj = this.neighbors4Fixed(tx, ty).filter(
      ([ax, ay]) => !this.blockedTileForPath(ax, ay, mover, mover.x, mover.y) || (ax === mover.x && ay === mover.y)
    )
    if (adj.length === 0) return null
    let best = adj[0]
    let bestD = Math.abs(best[0] - mover.x) + Math.abs(best[1] - mover.y)
    for (const a of adj.slice(1)) {
      const d = Math.abs(a[0] - mover.x) + Math.abs(a[1] - mover.y)
      if (d < bestD) {
        best = a
        bestD = d
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
        const d = Math.abs(x - mover.x) + Math.abs(y - mover.y)
        if (d < bestD) {
          bestD = d
          best = [x, y]
        }
      }
    }
    return best
  }

  /** Goal tile after resolving click (adjacent to enemy, resource, etc.). */
  private computeGoalTile(u: UnitEntity, gx: number, gy: number): [number, number] | null {
    const res = this.resourceAt(gx, gy)
    const targetU = this.unitAt(gx, gy)
    let goalX = gx
    let goalY = gy

    if (res && u.unit === 'villager') {
      const adj = this.bestAdjacentTo(res.x, res.y, u)
      if (!adj) return null
      goalX = adj[0]
      goalY = adj[1]
    } else if (targetU && targetU.owner !== u.owner) {
      const adj = this.bestAdjacentTo(targetU.x, targetU.y, u)
      if (!adj) return null
      goalX = adj[0]
      goalY = adj[1]
    } else {
      for (const e of this.entities.values()) {
        if (e.kind !== 'base') continue
        const b = e as BaseEntity
        if (b.owner === u.owner) continue
        const inside = gx >= b.x && gx < b.x + b.w && gy >= b.y && gy < b.y + b.h
        if (inside) {
          const adj = this.bestAdjacentToBase(b, u)
          if (!adj) return null
          goalX = adj[0]
          goalY = adj[1]
          break
        }
      }
    }
    return [goalX, goalY]
  }

  /** Full BFS path capped to movement range (UNIT_STATS.speed tiles per turn). */
  computeMovePath(u: UnitEntity, gx: number, gy: number): [number, number][] {
    const goal = this.computeGoalTile(u, gx, gy)
    if (!goal) return []
    const path = this.bfs([u.x, u.y], (x, y) => x === goal[0] && y === goal[1], u)
    const cap = UNIT_STATS[u.unit].speed
    return path.slice(0, cap)
  }

  issueMove(u: UnitEntity, gx: number, gy: number) {
    const path = this.computeMovePath(u, gx, gy)
    u.path = path
    const last = path.length ? path[path.length - 1] : null
    u.goal = last ? [last[0], last[1]] : null
    u.attackId = null
    u.gatherId = null
  }

  selectAt(gx: number, gy: number, owner: Owner) {
    if (this.winner != null) return
    if (owner === 0 && this.turnOwner !== 0) return
    if (this.moveAnimation) return
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
      if (this.actedThisPlayerTurn.has(sel.id)) return
      const path = this.computeMovePath(sel, gx, gy)
      if (path.length === 0) return
      this.moveAnimation = { unitId: sel.id, path, step: 0 }
    }
  }

  /** One tile of movement; returns true if more tiles remain. */
  tickMoveAnimation(): boolean {
    if (!this.moveAnimation) return false
    const m = this.moveAnimation
    const u = this.entities.get(m.unitId) as UnitEntity | undefined
    if (!u || u.kind !== 'unit') {
      this.moveAnimation = null
      return false
    }
    if (m.step < m.path.length) {
      const [tx, ty] = m.path[m.step]
      u.x = tx
      u.y = ty
      m.step++
      if (m.step >= m.path.length) {
        this.moveAnimation = null
        this.actedThisPlayerTurn.add(u.id)
        this.resolveCombatGatherNoCooldown(u)
        this.checkWin()
        return false
      }
      return true
    }
    return false
  }

  popDamagePopups(): DamagePopupEvent[] {
    const out = this._damagePopups
    this._damagePopups = []
    return out
  }

  /** Highlight tiles reachable in one move (BFS, movement range = unit speed). */
  getReachableKeysForSelection(owner: Owner): Set<string> | null {
    if (this.winner != null) return null
    if (owner === 0 && this.turnOwner !== 0) return null
    if (this.moveAnimation) return null
    const sel = this.selectedId ? this.entities.get(this.selectedId) : null
    if (!sel || sel.kind !== 'unit' || sel.owner !== owner) return null
    if (this.actedThisPlayerTurn.has(sel.id)) return null
    return this.getReachableTilesKeys(sel as UnitEntity)
  }

  private getReachableTilesKeys(u: UnitEntity): Set<string> {
    const max = UNIT_STATS[u.unit].speed
    const q: [number, number, number][] = [[u.x, u.y, 0]]
    const seen = new Set<string>([`${u.x},${u.y}`])
    const out = new Set<string>()
    while (q.length) {
      const [x, y, d] = q.shift()!
      if (d > 0) out.add(`${x},${y}`)
      if (d >= max) continue
      for (const [nx, ny] of this.neighbors4Fixed(x, y)) {
        const k = `${nx},${ny}`
        if (seen.has(k)) continue
        if (this.blockedTileForPath(nx, ny, u, u.x, u.y)) continue
        seen.add(k)
        q.push([nx, ny, d + 1])
      }
    }
    return out
  }

  /**
   * Move carried wood/gold into the stockpile for any villager orthogonally adjacent to their town hall.
   * Called at turn boundaries so idle workers next to base still bank without needing a move order.
   */
  private depositVillagersAtTownHall(owner: Owner): void {
    const own = this.baseFor(owner)
    if (!own) return
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      if (u.owner !== owner || u.unit !== 'villager') continue
      if (u.carryWood <= 0 && u.carryGold <= 0) continue
      if (!this.adjacentToBase(u, own)) continue
      this.wood[owner] += u.carryWood
      this.gold[owner] += u.carryGold
      u.carryWood = 0
      u.carryGold = 0
    }
  }

  /** Player ends their turn → AI plays one full round, then it is your turn again. */
  endPlayerTurn() {
    if (this.moveAnimation) return
    if (this.winner != null || this.turnOwner !== 0) return
    this.depositVillagersAtTownHall(0)
    this.turnOwner = 1
    this.runAiTurn()
    this.depositVillagersAtTownHall(1)
    this.turnOwner = 0
    this.actedThisPlayerTurn.clear()
    this.checkWin()
  }

  /** Stockpile + carried resources (for HUD; carry is not in stock until deposited at base). */
  getPlayerEconomy(): {
    stockWood: number
    stockGold: number
    carryWood: number
    carryGold: number
  } {
    let carryWood = 0
    let carryGold = 0
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit' || e.owner !== 0) continue
      const u = e as UnitEntity
      carryWood += u.carryWood
      carryGold += u.carryGold
    }
    return {
      stockWood: this.wood[0],
      stockGold: this.gold[0],
      carryWood,
      carryGold,
    }
  }

  private executePathInstant(u: UnitEntity) {
    while (u.path.length > 0) {
      const [nx, ny] = u.path[0]
      const block = this.unitAt(nx, ny)
      if (block && block.id !== u.id) break
      u.path.shift()
      u.x = nx
      u.y = ny
    }
    u.path = []
    u.goal = null
    u.stepCd = 0
  }

  /** If `only` is set (player or one AI unit that just moved), only that unit resolves combat/gather — avoids idle units firing every click. */
  private resolveCombatGatherNoCooldown(only?: UnitEntity) {
    const units: UnitEntity[] = only
      ? [only]
      : [...this.entities.values()].filter((e): e is UnitEntity => e.kind === 'unit')
    for (const u of units) {
      if (u.path.length > 0) continue

      if (u.unit === 'villager') {
        const own = this.baseFor(u.owner)
        if (own && this.adjacentToBase(u, own) && (u.carryWood > 0 || u.carryGold > 0)) {
          this.wood[u.owner] += u.carryWood
          this.gold[u.owner] += u.carryGold
          u.carryWood = 0
          u.carryGold = 0
          continue
        }
        const res = this.neighbors4Fixed(u.x, u.y)
          .map(([x, y]) => this.resourceAt(x, y))
          .find((r) => r && r.amount > 0)
        if (res) {
          const amt = Math.min(GATHER_RATE, res.amount)
          if (res.res === 'tree') u.carryWood += amt
          else u.carryGold += amt
          res.amount -= amt
          if (res.amount <= 0) this.entities.delete(res.id)
          this._damagePopups.push({ gx: u.x, gy: u.y, value: amt, kind: 'gather' })
          continue
        }
        /* else: no gather this tick — villagers may still melee (low damage). */
      }

      let foe: UnitEntity | null = null
      for (const o of this.entities.values()) {
        if (o.kind !== 'unit') continue
        const ou = o as UnitEntity
        if (ou.owner === u.owner) continue
        if (this.adjacent(u, ou)) {
          foe = ou
          break
        }
      }
      if (foe) {
        foe.hp -= u.dmg
        this._damagePopups.push({ gx: foe.x, gy: foe.y, value: u.dmg, kind: 'hit' })
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
            if (Math.abs(u.x - x) + Math.abs(u.y - y) === 1) hit = true
          }
        }
        if (hit) {
          b.hp -= u.dmg
          this._damagePopups.push({ gx: u.x, gy: u.y, value: u.dmg, kind: 'base' })
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
    if (this.winner != null) return
    const owner = 1 as Owner
    const b = this.baseFor(owner)
    if (!b) return

    if (this.rng() < 0.35) {
      const prefer = this.rng() < 0.5 ? 'spearman' : 'villager'
      if (!this.tryTrainExpanded(owner, prefer)) this.tryTrainExpanded(owner, prefer === 'spearman' ? 'villager' : 'spearman')
    }

    const snapshot = [...this.entities.values()]
      .filter((e): e is UnitEntity => e.kind === 'unit' && e.owner === owner)
      .map((u) => u.id)

    for (const id of snapshot) {
      if (this.winner != null) return
      const raw = this.entities.get(id)
      if (!raw || raw.kind !== 'unit') continue
      const u = raw as UnitEntity
      if (u.owner !== owner) continue

      if (u.unit === 'villager') {
        const base = this.baseFor(owner)
        if (u.carryWood + u.carryGold > 40 && base) {
          const adj = this.bestAdjacentToBase(base, u)
          if (adj) this.issueMove(u, adj[0], adj[1])
        } else {
          let best: ResourceEntity | null = null
          let bd = 1e9
          for (const r of this.entities.values()) {
            if (r.kind !== 'resource' || r.amount <= 0) continue
            const res = r as ResourceEntity
            const d = Math.abs(res.x - u.x) + Math.abs(res.y - u.y)
            if (d < bd) {
              bd = d
              best = res
            }
          }
          if (best) this.issueMove(u, best.x, best.y)
        }
      } else {
        let target: UnitEntity | null = null
        let td = 1e9
        for (const o of this.entities.values()) {
          if (o.kind !== 'unit') continue
          const ou = o as UnitEntity
          if (ou.owner === owner) continue
          const d = Math.abs(ou.x - u.x) + Math.abs(ou.y - u.y)
          if (d < td) {
            td = d
            target = ou
          }
        }
        const pb = this.baseFor(0 as Owner)
        if (target) this.issueMove(u, target.x, target.y)
        else if (pb) this.issueMove(u, pb.x, pb.y)
      }

      if (u.path.length > 0) {
        this.executePathInstant(u)
        this.resolveCombatGatherNoCooldown(u)
      }
    }
  }

  adjacent(a: UnitEntity, b: UnitEntity): boolean {
    return Math.abs(a.x - b.x) + Math.abs(a.y - b.y) === 1
  }

  adjacentToBase(u: UnitEntity, b: BaseEntity): boolean {
    for (let y = b.y; y < b.y + b.h; y++) {
      for (let x = b.x; x < b.x + b.w; x++) {
        if (Math.abs(u.x - x) + Math.abs(u.y - y) === 1) return true
      }
    }
    return false
  }

  private checkWin() {
    if (this.winner != null) return
    const b0 = this.baseFor(0)
    const b1 = this.baseFor(1)
    if (b0 && b0.hp <= 0) this.winner = 1
    else if (b1 && b1.hp <= 0) this.winner = 0
  }

  render(ctx: CanvasRenderingContext2D, opts?: { reachableKeys?: Set<string> }) {
    ctx.imageSmoothingEnabled = false
    const reach = opts?.reachableKeys
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        const t = this.terrain[y][x]
        ctx.fillStyle = t === 'water' ? '#1e3a5c' : '#2d5a35'
        ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
        if (t === 'grass') {
          ctx.fillStyle = 'rgba(255,255,255,0.04)'
          if ((x + y) % 2 === 0) ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
        }
        if (reach?.has(`${x},${y}`)) {
          ctx.fillStyle = 'rgba(52, 211, 153, 0.22)'
          ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
          ctx.strokeStyle = 'rgba(52, 211, 153, 0.45)'
          ctx.lineWidth = 1
          ctx.strokeRect(x * TILE + 0.5, y * TILE + 0.5, TILE - 2, TILE - 2)
        }
        ctx.strokeStyle = 'rgba(0,0,0,0.18)'
        ctx.strokeRect(x * TILE + 0.5, y * TILE + 0.5, TILE - 1, TILE - 1)
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind === 'resource') {
        const r = e as ResourceEntity
        ctx.fillStyle = r.res === 'tree' ? '#166534' : '#ca8a04'
        ctx.fillRect(r.x * TILE + 2, r.y * TILE + 2, TILE - 4, TILE - 4)
        ctx.fillStyle = 'rgba(0,0,0,0.35)'
        ctx.fillRect(r.x * TILE + 2, r.y * TILE + 2, TILE - 4, 3)
      }
    }

    for (const e of this.entities.values()) {
      if (e.kind === 'base') {
        const b = e as BaseEntity
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

    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      const cx = u.x * TILE + TILE / 2
      const cy = u.y * TILE + TILE / 2
      const spent = u.owner === 0 && this.turnOwner === 0 && this.actedThisPlayerTurn.has(u.id)
      ctx.globalAlpha = spent ? 0.38 : 1
      ctx.fillStyle = u.owner === 0 ? '#38bdf8' : '#fb7185'
      ctx.beginPath()
      ctx.arc(cx, cy, TILE * 0.32, 0, Math.PI * 2)
      ctx.fill()
      ctx.globalAlpha = 1
      ctx.fillStyle = '#fff'
      ctx.font = 'bold 11px system-ui,sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(u.unit === 'villager' ? 'V' : 'S', cx, cy)
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
  }
}

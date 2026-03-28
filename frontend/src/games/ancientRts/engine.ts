import {
  ATTACK_COOLDOWN_MS,
  BASE_MAX_HP,
  GATHER_INTERVAL_MS,
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
  aiCd = 0

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
    this.aiCd = 0

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
    const st = UNIT_STATS[kind]
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
      const adj = this.bestAdjacentTo(targetU.x, targetU.y, u)
      if (!adj) return
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
          if (!adj) return
          goalX = adj[0]
          goalY = adj[1]
          break
        }
      }
    }

    const path = this.bfs([u.x, u.y], (x, y) => x === goalX && y === goalY, u)
    u.path = path
    u.goal = path.length ? [goalX, goalY] : null
    u.attackId = null
    u.gatherId = null
  }

  selectAt(gx: number, gy: number, owner: Owner) {
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

  tick(dt: number) {
    if (this.winner != null) return
    this.moveStep(dt)
    this.combatAndGather(dt)
    this.aiCd -= dt
    if (this.aiCd <= 0) {
      this.aiCd = 0.45
      this.tickAi()
    }
    this.checkWin()
  }

  private moveStep(dt: number) {
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
      if (u.path.length === 0) {
        u.stepCd = 0
        continue
      }
      u.stepCd -= dt * u.speed
      while (u.stepCd <= 0 && u.path.length > 0) {
        const [nx, ny] = u.path[0]
        const block = this.unitAt(nx, ny)
        if (block && block.id !== u.id) break
        u.path.shift()
        u.x = nx
        u.y = ny
        u.stepCd += 0.35
      }
    }
  }

  private combatAndGather(_dt: number) {
    const now = performance.now()
    for (const e of this.entities.values()) {
      if (e.kind !== 'unit') continue
      const u = e as UnitEntity
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
          if (now - u.lastGather < GATHER_INTERVAL_MS) continue
          u.lastGather = now
          const amt = Math.min(GATHER_RATE, res.amount)
          if (res.res === 'tree') u.carryWood += amt
          else u.carryGold += amt
          res.amount -= amt
          if (res.amount <= 0) this.entities.delete(res.id)
        }
        continue
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
        if (now - u.lastAttack < ATTACK_COOLDOWN_MS) continue
        u.lastAttack = now
        foe.hp -= u.dmg
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
          if (now - u.lastAttack < ATTACK_COOLDOWN_MS) break
          u.lastAttack = now
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

  private tickAi() {
    if (this.winner != null) return
    const owner = 1 as Owner
    const b = this.baseFor(owner)
    if (!b) return
    if (this.rng() < 0.22) {
      const prefer = this.rng() < 0.5 ? 'spearman' : 'villager'
      if (!this.tryTrainExpanded(owner, prefer)) this.tryTrainExpanded(owner, prefer === 'spearman' ? 'villager' : 'spearman')
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
          const d = Math.abs(res.x - u.x) + Math.abs(res.y - u.y)
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
    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        const t = this.terrain[y][x]
        ctx.fillStyle = t === 'water' ? '#2a4a6a' : '#3d6b3d'
        ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
        ctx.strokeStyle = 'rgba(0,0,0,0.12)'
        ctx.strokeRect(x * TILE, y * TILE, TILE, TILE)
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
      ctx.fillStyle = u.owner === 0 ? '#60a5fa' : '#f87171'
      ctx.beginPath()
      ctx.arc(cx, cy, TILE * 0.32, 0, Math.PI * 2)
      ctx.fill()
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

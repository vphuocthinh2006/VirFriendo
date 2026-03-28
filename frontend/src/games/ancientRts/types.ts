export type Owner = 0 | 1

export type UnitKind = 'villager' | 'spearman'

export type Terrain = 'grass' | 'water'

export type ResType = 'tree' | 'gold'

export type BaseEntity = {
  id: string
  kind: 'base'
  owner: Owner
  x: number
  y: number
  w: number
  h: number
  hp: number
  maxHp: number
}

export type UnitEntity = {
  id: string
  kind: 'unit'
  owner: Owner
  unit: UnitKind
  x: number
  y: number
  hp: number
  maxHp: number
  dmg: number
  speed: number
  carryWood: number
  carryGold: number
  path: [number, number][]
  goal: [number, number] | null
  attackId: string | null
  gatherId: string | null
  lastAttack: number
  lastGather: number
  stepCd: number
}

export type ResourceEntity = {
  id: string
  kind: 'resource'
  res: ResType
  x: number
  y: number
  amount: number
}

export type AnyEntity = BaseEntity | UnitEntity | ResourceEntity

export const UNIT_STATS: Record<
  UnitKind,
  { maxHp: number; dmg: number; speed: number; costW: number; costG: number }
> = {
  villager: { maxHp: 45, dmg: 4, speed: 6, costW: 35, costG: 0 },
  spearman: { maxHp: 85, dmg: 14, speed: 5, costW: 25, costG: 45 },
}

export const BASE_MAX_HP = 720
export const GATHER_RATE = 8
export const ATTACK_COOLDOWN_MS = 520
export const GATHER_INTERVAL_MS = 380

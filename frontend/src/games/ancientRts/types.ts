export type Owner = 0 | 1

/** marshal = enemy general (capture flow); not trainable */
export type UnitKind = 'villager' | 'spearman' | 'archer' | 'knight' | 'marshal'

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
  /** Turn-based: one skill per unit per your turn */
  skillUsedThisTurn: boolean
  /** Villager skill: next gather takes double (once) */
  hustleDoubleGather: boolean
  nextBlock: boolean
  buffNextAttackBonus: number
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

export type UnitStatRow = {
  maxHp: number
  dmg: number
  speed: number
  costW: number
  costG: number
  meleeRange: number
  rangedMax: number
  trainable: boolean
}

export const UNIT_STATS: Record<UnitKind, UnitStatRow> = {
  villager: { maxHp: 45, dmg: 4, speed: 6, costW: 35, costG: 0, meleeRange: 1, rangedMax: 0, trainable: true },
  spearman: { maxHp: 85, dmg: 14, speed: 5, costW: 25, costG: 45, meleeRange: 1, rangedMax: 0, trainable: true },
  archer: { maxHp: 55, dmg: 11, speed: 5, costW: 40, costG: 55, meleeRange: 1, rangedMax: 2, trainable: true },
  knight: { maxHp: 120, dmg: 17, speed: 4, costW: 60, costG: 70, meleeRange: 1, rangedMax: 0, trainable: true },
  marshal: { maxHp: 160, dmg: 20, speed: 4, costW: 0, costG: 0, meleeRange: 1, rangedMax: 0, trainable: false },
}

export const BASE_MAX_HP = 720
export const GATHER_RATE = 8
export const BASE_DROP_RADIUS_TILES = 3.45

/** Max tiles along one move order this turn (8-dir, Chebyshev steps). */
export const MOVEMENT_PER_TURN: Record<UnitKind, number> = {
  villager: 4,
  spearman: 3,
  archer: 3,
  knight: 5,
  marshal: 3,
}

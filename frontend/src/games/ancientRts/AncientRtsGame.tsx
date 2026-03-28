import { useCallback, useEffect, useRef, useState } from 'react'
import type { DamagePopupEvent } from './engine'
import { AncientRtsEngine, MAP_H, MAP_W, TILE } from './engine'
import type { UnitKind } from './types'

type Props = {
  onExit: () => void
}

type Particle = { id: string; x: number; y: number; vx: number; vy: number; life: number; hue: number }
type FloatTxt = { id: string; gx: number; gy: number; label: string; born: number; kind: DamagePopupEvent['kind'] }

let _pid = 0
let _fid = 0

function syncEconomy(eng: AncientRtsEngine) {
  return eng.getPlayerEconomy()
}

function spawnStepParticles(gx: number, gy: number): Particle[] {
  const cx = gx * TILE + TILE / 2
  const cy = gy * TILE + TILE / 2
  const out: Particle[] = []
  for (let i = 0; i < 10; i++) {
    _pid += 1
    out.push({
      id: `p${_pid}`,
      x: cx,
      y: cy,
      vx: (Math.random() - 0.5) * 3.2,
      vy: (Math.random() - 0.5) * 3.2 - 1.2,
      life: 0.85 + Math.random() * 0.25,
      hue: 180 + Math.random() * 80,
    })
  }
  return out
}

function spawnHitBurst(gx: number, gy: number, kind: DamagePopupEvent['kind']): Particle[] {
  const cx = gx * TILE + TILE / 2
  const cy = gy * TILE + TILE / 2
  const baseHue = kind === 'hit' ? 0 : kind === 'base' ? 45 : 140
  const out: Particle[] = []
  for (let i = 0; i < 14; i++) {
    _pid += 1
    const ang = (Math.PI * 2 * i) / 14
    out.push({
      id: `p${_pid}`,
      x: cx,
      y: cy,
      vx: Math.cos(ang) * (2.5 + Math.random()),
      vy: Math.sin(ang) * (2.5 + Math.random()),
      life: 1,
      hue: baseHue + Math.random() * 25,
    })
  }
  return out
}

export default function AncientRtsGame({ onExit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const engineRef = useRef<AncientRtsEngine | null>(null)
  const particlesRef = useRef<Particle[]>([])
  const floatsRef = useRef<FloatTxt[]>([])

  const [economy, setEconomy] = useState({
    stockWood: 120,
    stockGold: 80,
    carryWood: 0,
    carryGold: 0,
  })
  const [winner, setWinner] = useState<0 | 1 | null>(null)
  const [turnPhase, setTurnPhase] = useState<'yours' | 'ai'>('yours')

  const syncHud = useCallback(() => {
    const eng = engineRef.current
    if (!eng) return
    setEconomy(syncEconomy(eng))
    setTurnPhase(eng.turnOwner === 0 ? 'yours' : 'ai')
    setWinner(eng.winner)
  }, [])

  const paintCanvas = useCallback(() => {
    const eng = engineRef.current
    const ctx = canvasRef.current?.getContext('2d')
    if (!eng || !ctx) return
    const reach = eng.getReachableKeysForSelection(0)
    eng.render(ctx, reach ? { reachableKeys: reach } : undefined)

    const now = performance.now()
    floatsRef.current = floatsRef.current.filter((f) => now - f.born < 900)
    for (const f of floatsRef.current) {
      const age = (now - f.born) / 1000
      const py = f.gy * TILE + TILE * 0.2 - age * 28
      const px = f.gx * TILE + TILE / 2
      ctx.save()
      ctx.globalAlpha = Math.max(0, 1 - age * 1.1)
      ctx.font = 'bold 12px system-ui,sans-serif'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      const col =
        f.kind === 'hit' ? '#fca5a5' : f.kind === 'base' ? '#fcd34d' : '#86efac'
      ctx.fillStyle = col
      ctx.strokeStyle = 'rgba(0,0,0,0.55)'
      ctx.lineWidth = 3
      ctx.strokeText(f.label, px, py)
      ctx.fillText(f.label, px, py)
      ctx.restore()
    }

    for (const p of particlesRef.current) {
      ctx.save()
      ctx.globalAlpha = Math.min(1, p.life * 1.2)
      ctx.fillStyle = `hsl(${p.hue}, 85%, 62%)`
      ctx.beginPath()
      ctx.arc(p.x, p.y, 2.2 + p.life * 1.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.restore()
    }
  }, [])

  const pushFloatsFromPopups = (pops: DamagePopupEvent[]) => {
    const now = performance.now()
    for (const p of pops) {
      _fid += 1
      const label = p.kind === 'gather' ? `+${p.value}` : `-${p.value}`
      floatsRef.current.push({
        id: `f${_fid}`,
        gx: p.gx,
        gy: p.gy,
        label,
        born: now,
        kind: p.kind,
      })
      if (p.kind === 'hit' || p.kind === 'base') {
        particlesRef.current.push(...spawnHitBurst(p.gx, p.gy, p.kind))
      }
    }
  }

  const redraw = useCallback(() => {
    syncHud()
    paintCanvas()
  }, [syncHud, paintCanvas])

  const runParticlePhysics = useCallback(() => {
    const list = particlesRef.current
    if (list.length === 0) return
    const dt = 0.038
    particlesRef.current = list
      .map((p) => ({
        ...p,
        x: p.x + p.vx,
        y: p.y + p.vy,
        vy: p.vy + 0.07,
        life: p.life - dt,
      }))
      .filter((p) => p.life > 0)
    paintCanvas()
  }, [paintCanvas])

  useEffect(() => {
    let raf = 0
    const loop = () => {
      runParticlePhysics()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [runParticlePhysics])

  useEffect(() => {
    const engine = new AncientRtsEngine()
    engineRef.current = engine
    syncHud()
    paintCanvas()
  }, [syncHud, paintCanvas])

  const runMoveChain = (eng: AncientRtsEngine) => {
    const step = () => {
      const uid = eng.moveAnimation?.unitId
      eng.tickMoveAnimation()
      const pops = eng.popDamagePopups()
      pushFloatsFromPopups(pops)
      const u = uid ? eng.entities.get(uid) : null
      if (u && u.kind === 'unit') {
        particlesRef.current.push(...spawnStepParticles(u.x, u.y))
      }
      syncHud()
      paintCanvas()
      if (eng.moveAnimation) {
        setTimeout(step, 92)
      }
    }
    step()
  }

  const onCanvasClick = (ev: React.MouseEvent<HTMLCanvasElement>) => {
    const eng = engineRef.current
    const c = canvasRef.current
    if (!eng || !c || eng.winner != null || eng.turnOwner !== 0 || eng.moveAnimation) return
    const r = c.getBoundingClientRect()
    const sx = c.width / r.width
    const sy = c.height / r.height
    const gx = Math.floor(((ev.clientX - r.left) * sx) / TILE)
    const gy = Math.floor(((ev.clientY - r.top) * sy) / TILE)
    if (gx < 0 || gy < 0 || gx >= MAP_W || gy >= MAP_H) return
    eng.selectAt(gx, gy, 0)
    if (eng.moveAnimation) {
      runMoveChain(eng)
    } else {
      syncHud()
      paintCanvas()
    }
  }

  const train = (kind: UnitKind) => {
    const eng = engineRef.current
    if (!eng || eng.winner != null || eng.turnOwner !== 0 || eng.moveAnimation) return
    eng.tryTrainExpanded(0, kind)
    redraw()
  }

  const endTurn = () => {
    const eng = engineRef.current
    if (!eng || eng.winner != null || eng.turnOwner !== 0 || eng.moveAnimation) return
    eng.endPlayerTurn()
    redraw()
  }

  const restart = () => {
    const eng = engineRef.current
    if (!eng) return
    eng.reset()
    particlesRef.current = []
    floatsRef.current = []
    redraw()
  }

  const eng = engineRef.current
  const yourTurn = eng ? eng.turnOwner === 0 : true
  const canAct = yourTurn && eng?.winner == null && !eng?.moveAnimation

  return (
    <div className="vf-ancient-rts w-full max-w-5xl mx-auto">
      <div className="rounded-2xl border border-vn-dialogueBorder bg-gradient-to-b from-[#12181f] via-[#0d1117] to-[#080a0c] shadow-[0_0_0_1px_rgba(255,255,255,0.04)_inset] overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-white/10 bg-black/20">
          <div>
            <h2 className="text-base font-semibold text-vn-text tracking-tight">Ancient RTS (turn-based)</h2>
            <p className="text-[11px] text-vn-textDim mt-0.5">
              Carried resources bank into Wood/Gold when a villager is orthogonally next to your town hall — including
              automatically at End turn. Melee only; movement is limited per turn (speed = tiles).
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={endTurn}
              disabled={!canAct}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-amber-600/90 hover:bg-amber-500 text-white disabled:opacity-40 disabled:pointer-events-none transition shadow-sm"
            >
              End turn
            </button>
            <button
              type="button"
              onClick={restart}
              className="px-3 py-1.5 rounded-lg text-sm border border-white/15 text-vn-text hover:bg-white/10 transition"
            >
              Restart
            </button>
            <button
              type="button"
              onClick={onExit}
              className="px-3 py-1.5 rounded-lg text-sm text-vn-textDim hover:text-vn-text hover:bg-white/10 transition"
            >
              Exit
            </button>
          </div>
        </div>

        <div className="px-4 py-3 flex flex-wrap gap-3 items-stretch border-b border-white/10 bg-black/15">
          <div
            className={`flex-1 min-w-[140px] rounded-xl px-3 py-2 border ${
              turnPhase === 'yours' ? 'border-emerald-500/35 bg-emerald-500/10' : 'border-white/10 bg-white/5'
            }`}
          >
            <p className="text-[10px] uppercase tracking-wider text-vn-textDim mb-1">Phase</p>
            <p className="text-sm font-medium text-vn-text">
              {winner != null ? 'Game over' : turnPhase === 'yours' ? 'Your turn (blue)' : 'Enemy (red)'}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 flex-[2] min-w-[200px]">
            <div className="flex-1 min-w-[100px] rounded-xl border border-emerald-500/25 bg-emerald-950/40 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-emerald-200/70 mb-0.5">Wood</p>
              <p className="text-xl font-semibold tabular-nums text-emerald-100">{economy.stockWood}</p>
            </div>
            <div className="flex-1 min-w-[100px] rounded-xl border border-amber-500/25 bg-amber-950/40 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-amber-200/70 mb-0.5">Gold</p>
              <p className="text-xl font-semibold tabular-nums text-amber-100">{economy.stockGold}</p>
            </div>
            <div className="flex-1 min-w-[120px] rounded-xl border border-sky-500/20 bg-sky-950/30 px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-sky-200/70 mb-0.5">Carried (vills)</p>
              <p className="text-sm tabular-nums text-sky-100">
                <span className="font-semibold">{economy.carryWood}</span>
                <span className="text-sky-200/50 mx-1">W</span>
                <span className="font-semibold">{economy.carryGold}</span>
                <span className="text-sky-200/50 ml-1">G</span>
              </p>
            </div>
          </div>
        </div>

        <div className="p-4 flex flex-col lg:flex-row gap-4 items-start">
          <div className="relative rounded-xl p-1 bg-gradient-to-br from-zinc-700/40 to-zinc-900/80 ring-1 ring-white/10 shadow-xl mx-auto lg:mx-0">
            <div className="rounded-lg overflow-hidden border border-black/50 shadow-inner relative">
              <canvas
                ref={canvasRef}
                width={MAP_W * TILE}
                height={MAP_H * TILE}
                onClick={onCanvasClick}
                className="block max-w-[min(92vw,480px)] h-auto w-full cursor-crosshair"
                style={{ imageRendering: 'pixelated' }}
              />
            </div>
            <p className="text-[10px] text-vn-textDim mt-2 px-1 text-center lg:text-left">
              Dark green: trees · Gold: ore · Blue: water. Green overlay = movement range. Select a unit, then click a
              tile.
            </p>
          </div>

          <div className="flex-1 w-full space-y-3 min-w-0">
            <div className="rounded-xl border border-white/10 bg-white/[0.04] p-4">
              <p className="text-xs font-medium text-vn-text mb-3">Train (town hall)</p>
              <div className="flex flex-col sm:flex-row gap-2">
                <button
                  type="button"
                  onClick={() => train('villager')}
                  disabled={!canAct}
                  className="flex-1 rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-4 py-3 text-left hover:bg-emerald-500/25 transition disabled:opacity-40"
                >
                  <span className="block text-sm font-semibold text-emerald-100">Villager</span>
                  <span className="text-[11px] text-emerald-200/80">35 wood — gather, weak melee</span>
                </button>
                <button
                  type="button"
                  onClick={() => train('spearman')}
                  disabled={!canAct}
                  className="flex-1 rounded-xl border border-amber-500/40 bg-amber-500/15 px-4 py-3 text-left hover:bg-amber-500/25 transition disabled:opacity-40"
                >
                  <span className="block text-sm font-semibold text-amber-100">Spearman</span>
                  <span className="text-[11px] text-amber-200/80">25 wood · 45 gold — stronger melee</span>
                </button>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs text-vn-textDim leading-relaxed">
              <p className="text-vn-text font-medium mb-2 text-sm">Rules</p>
              <ul className="space-y-1.5 list-disc pl-4">
                <li>Each unit moves at most its speed in tiles per turn (villager 6, spearman 5).</li>
                <li>Combat is adjacent tiles only — walk next to an enemy to attack. Villagers can fight for low damage.</li>
                <li>
                  Villagers next to your town hall (not diagonally) deposit carry into Wood/Gold when their move ends and
                  again when you press End turn.
                </li>
                <li>Dimmed blue units have already acted. Press End turn when finished.</li>
              </ul>
            </div>

            {winner !== null ? (
              <div
                className={`rounded-xl border px-4 py-3 text-sm font-medium ${
                  winner === 0 ? 'border-emerald-500/45 bg-emerald-500/10 text-emerald-200' : 'border-red-500/45 bg-red-500/10 text-red-200'
                }`}
              >
                {winner === 0 ? 'Victory — enemy town hall destroyed.' : 'Defeat — your town hall was destroyed.'}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}

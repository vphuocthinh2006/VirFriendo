import { useCallback, useEffect, useRef, useState } from 'react'
import { AncientRtsEngine, MAP_H, MAP_W, TILE } from './engine'
import { MOVEMENT_PER_TURN } from './types'
import type { UnitEntity, UnitKind } from './types'

type Props = {
  onExit: () => void
}

const TRAINABLE: { kind: UnitKind; label: string }[] = [
  { kind: 'villager', label: 'Villager (35 wood)' },
  { kind: 'spearman', label: 'Spearman (25 wood, 45 gold)' },
  { kind: 'archer', label: 'Archer (40 wood, 55 gold)' },
  { kind: 'knight', label: 'Knight (60 wood, 70 gold)' },
]

function skillLabel(kind: UnitKind): string | null {
  switch (kind) {
    case 'villager':
      return 'Hustle — double next gather'
    case 'spearman':
      return 'Phalanx — block next hit'
    case 'archer':
      return 'Volley — stronger next shot'
    case 'knight':
      return 'Slam — bonus next strike'
    default:
      return null
  }
}

function paint(eng: AncientRtsEngine, canvas: HTMLCanvasElement | null) {
  const ctx = canvas?.getContext('2d')
  if (ctx) eng.render(ctx)
}

export default function AncientRtsGame({ onExit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const engineRef = useRef<AncientRtsEngine | null>(null)
  const lastFrameRef = useRef<number>(0)
  const [, setUi] = useState(0)
  const [winner, setWinner] = useState<0 | 1 | null>(null)

  useEffect(() => {
    const engine = new AncientRtsEngine()
    engineRef.current = engine
    let id = 0
    lastFrameRef.current = performance.now()
    const loop = (now: number) => {
      const eng = engineRef.current
      if (eng) {
        const dt = Math.min(48, now - lastFrameRef.current)
        lastFrameRef.current = now
        eng.visualTimeMs = now
        if (eng.tickMarchFrame(dt)) {
          setWinner(eng.winner)
          setUi((n) => n + 1)
        }
        paint(eng, canvasRef.current)
      }
      id = requestAnimationFrame(loop)
    }
    id = requestAnimationFrame(loop)
    setUi((n) => n + 1)
    return () => {
      cancelAnimationFrame(id)
      engineRef.current = null
    }
  }, [])

  const bump = useCallback(() => {
    const eng = engineRef.current
    if (!eng) return
    setWinner(eng.winner)
    setUi((n) => n + 1)
    paint(eng, canvasRef.current)
  }, [])

  const onCanvasClick = useCallback(
    (ev: React.MouseEvent<HTMLCanvasElement>) => {
      const eng = engineRef.current
      const c = canvasRef.current
      if (!eng || !c || eng.winner != null || eng.pendingMarshalChoice || eng.marching) return
      const r = c.getBoundingClientRect()
      const sx = c.width / r.width
      const sy = c.height / r.height
      const gx = Math.floor(((ev.clientX - r.left) * sx) / TILE)
      const gy = Math.floor(((ev.clientY - r.top) * sy) / TILE)
      if (gx < 0 || gy < 0 || gx >= MAP_W || gy >= MAP_H) return
      eng.selectAt(gx, gy, 0)
      bump()
    },
    [bump],
  )

  const train = (kind: UnitKind) => {
    const eng = engineRef.current
    if (!eng || eng.winner != null) return
    eng.tryTrainExpanded(0, kind)
    bump()
  }

  const useSkill = () => {
    const eng = engineRef.current
    if (!eng || eng.winner != null) return
    eng.tryUseSkill(0)
    bump()
  }

  const endTurn = () => {
    const eng = engineRef.current
    if (!eng || eng.winner != null) return
    eng.endPlayerTurn()
    bump()
  }

  const resolveMarshal = (choice: 'capture' | 'eliminate') => {
    const eng = engineRef.current
    if (!eng) return
    eng.resolveMarshalChoice(choice)
    bump()
  }

  const restart = () => {
    const eng = engineRef.current
    if (!eng) return
    eng.reset()
    setWinner(null)
    bump()
  }

  const eng = engineRef.current
  const wood = eng?.wood[0] ?? 0
  const gold = eng?.gold[0] ?? 0
  const pending = eng?.pendingMarshalChoice
  const sel = eng?.selectedId ? eng.entities.get(eng.selectedId) : null
  const selUnit = sel?.kind === 'unit' ? (sel as UnitEntity) : null
  const skillName = selUnit ? skillLabel(selUnit.unit) : null
  const skillReady = !!(selUnit && skillName && !selUnit.skillUsedThisTurn)
  const round = eng?.turnNumber ?? 1
  const marching = eng?.marching ?? false

  return (
    <div className="vf-ancient-rts w-full max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 px-1">
        <div>
          <h2 className="text-lg font-semibold text-vn-text tracking-tight">Ringrealms</h2>
          <p className="text-xs text-vn-textDim mt-0.5 max-w-xl">
            Turn-based: give orders (move, train, skill), then press <strong className="text-vn-text">End turn</strong>. Both
            sides start with a villager and a spearman; combat and gathering resolve between rounds.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={restart}
            className="px-3 py-1.5 rounded-lg text-sm border border-vn-dialogueBorder text-vn-text hover:bg-white/10 transition"
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

      <div className="flex flex-wrap items-start gap-4">
        <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/50 p-2 overflow-auto max-w-full">
          <canvas
            ref={canvasRef}
            width={MAP_W * TILE}
            height={MAP_H * TILE}
            onClick={onCanvasClick}
            className={`block w-full max-w-[min(100vw-2rem,520px)] aspect-square rounded-lg ${marching ? 'cursor-wait' : 'cursor-crosshair'}`}
            style={{ imageRendering: 'pixelated' }}
          />
        </div>
        <div className="flex-1 min-w-[200px] space-y-3">
          <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-sm">
            <p className="text-vn-textDim text-xs uppercase tracking-wider mb-2">
              Round <span className="tabular-nums font-semibold text-vn-text">{round}</span> · your order phase
            </p>
            <button
              type="button"
              onClick={endTurn}
              disabled={!!pending || winner !== null || marching}
              className="w-full mb-3 rounded-lg border border-amber-500/60 bg-amber-500/15 px-4 py-2.5 text-sm font-semibold text-amber-100 hover:bg-amber-500/25 transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {marching ? 'Marching…' : 'End turn'}
            </button>
            <p className="text-vn-textDim text-xs uppercase tracking-wider mb-2">Your resources</p>
            <p className="text-vn-text">
              Wood <span className="tabular-nums font-semibold">{wood}</span> · Gold{' '}
              <span className="tabular-nums font-semibold">{gold}</span>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {TRAINABLE.map(({ kind, label }) => (
                <button
                  key={kind}
                  type="button"
                  onClick={() => train(kind)}
                  disabled={!!pending || winner !== null || marching}
                  className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200 hover:bg-emerald-500/20 transition disabled:opacity-40"
                >
                  {label}
                </button>
              ))}
            </div>
            {skillName ? (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={useSkill}
                  disabled={!skillReady || !!pending || winner !== null || marching}
                  className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-100 hover:bg-amber-500/20 transition disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Skill: {skillName}
                  {!skillReady && selUnit ? (
                    <span className="block text-[10px] text-amber-200/80 mt-0.5">Already used this turn</span>
                  ) : null}
                </button>
              </div>
            ) : null}
          </div>
          <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-xs text-vn-textDim leading-relaxed">
            <p className="text-vn-textDim font-semibold mb-1">Controls</p>
            <ul className="list-disc pl-4 space-y-1">
              <li>
                Green = walk range; red frame = enemy in strike range from your current tile; yellow = queued path. Clicks
                beyond range are ignored.
              </li>
              <li>
                Combat resolves on <strong className="text-vn-text">End turn</strong>. If you already see a red frame,
                click that enemy once to confirm (clears path); then End turn to deal damage.
              </li>
              <li>
                Move limit per turn: V {MOVEMENT_PER_TURN.villager} · S {MOVEMENT_PER_TURN.spearman} · A{' '}
                {MOVEMENT_PER_TURN.archer} · K {MOVEMENT_PER_TURN.knight} · M {MOVEMENT_PER_TURN.marshal}.
              </li>
              <li>Villagers gather on 8 directions; ring deposit. One skill per unit per round.</li>
            </ul>
          </div>
          {pending ? (
            <div className="rounded-xl border border-amber-500/50 bg-amber-950/40 px-4 py-3 text-sm space-y-3">
              <p className="text-amber-100 font-medium">Enemy marshal cornered</p>
              <p className="text-vn-textDim text-xs">Take the piece or remove it from the board.</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => resolveMarshal('capture')}
                  className="rounded-lg border border-emerald-500/60 bg-emerald-500/15 px-3 py-2 text-xs text-emerald-100"
                >
                  Capture (turn to knight)
                </button>
                <button
                  type="button"
                  onClick={() => resolveMarshal('eliminate')}
                  className="rounded-lg border border-red-500/50 bg-red-500/10 px-3 py-2 text-xs text-red-200"
                >
                  Eliminate
                </button>
              </div>
            </div>
          ) : null}
          {winner !== null ? (
            <div
              className={`rounded-xl border px-4 py-3 text-sm font-medium ${
                winner === 0 ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-200' : 'border-red-500/50 bg-red-500/10 text-red-200'
              }`}
            >
              {winner === 0 ? 'You win — enemy civic center destroyed.' : 'AI wins — your civic center fell.'}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { AncientRtsEngine, MAP_H, MAP_W, TILE } from './engine'
import type { UnitKind } from './types'

type Props = {
  onExit: () => void
}

export default function AncientRtsGame({ onExit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const engineRef = useRef<AncientRtsEngine | null>(null)
  const [, setTick] = useState(0)
  const [winner, setWinner] = useState<0 | 1 | null>(null)

  useEffect(() => {
    const engine = new AncientRtsEngine()
    engineRef.current = engine
    let raf = 0
    const loop = () => {
      const eng = engineRef.current
      if (!eng) return
      eng.tick(1 / 60)
      setWinner(eng.winner)
      setTick((t) => t + 1)
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx) eng.render(ctx)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  const onCanvasClick = useCallback((ev: React.MouseEvent<HTMLCanvasElement>) => {
    const eng = engineRef.current
    const c = canvasRef.current
    if (!eng || !c || eng.winner != null) return
    const r = c.getBoundingClientRect()
    const sx = c.width / r.width
    const sy = c.height / r.height
    const gx = Math.floor((ev.clientX - r.left) * sx / TILE)
    const gy = Math.floor((ev.clientY - r.top) * sy / TILE)
    if (gx < 0 || gy < 0 || gx >= MAP_W || gy >= MAP_H) return
    eng.selectAt(gx, gy, 0)
    const ctx = c.getContext('2d')
    if (ctx) eng.render(ctx)
    setTick((t) => t + 1)
  }, [])

  const train = (kind: UnitKind) => {
    const eng = engineRef.current
    if (!eng || eng.winner != null) return
    eng.tryTrainExpanded(0, kind)
    const ctx = canvasRef.current?.getContext('2d')
    if (ctx) eng.render(ctx)
    setTick((t) => t + 1)
  }

  const restart = () => {
    const eng = engineRef.current
    if (!eng) return
    eng.reset()
    setWinner(null)
    const ctx = canvasRef.current?.getContext('2d')
    if (ctx) eng.render(ctx)
    setTick((t) => t + 1)
  }

  const eng = engineRef.current
  const wood = eng?.wood[0] ?? 0
  const gold = eng?.gold[0] ?? 0

  return (
    <div className="vf-ancient-rts w-full max-w-6xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4 px-1">
        <div>
          <h2 className="text-lg font-semibold text-vn-text tracking-tight">Ancient RTS</h2>
          <p className="text-xs text-vn-textDim mt-0.5 max-w-xl">
            Lightweight browser RTS — you (blue) vs AI (red). Select a unit, click to move or gather. Destroy the enemy
            civic center to win.
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
            className="block rounded-lg cursor-crosshair max-w-[min(100vw-2rem,520px)] h-auto"
            style={{ imageRendering: 'pixelated' }}
          />
        </div>
        <div className="flex-1 min-w-[200px] space-y-3">
          <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-sm">
            <p className="text-vn-textDim text-xs uppercase tracking-wider mb-2">Your resources</p>
            <p className="text-vn-text">
              Wood <span className="tabular-nums font-semibold">{wood}</span> · Gold{' '}
              <span className="tabular-nums font-semibold">{gold}</span>
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => train('villager')}
                className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200 hover:bg-emerald-500/20 transition"
              >
                Train villager (35 wood)
              </button>
              <button
                type="button"
                onClick={() => train('spearman')}
                className="rounded-lg border border-amber-500/50 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 hover:bg-amber-500/20 transition"
              >
                Train spearman (25 wood, 45 gold)
              </button>
            </div>
          </div>
          <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-xs text-vn-textDim leading-relaxed">
            <p className="text-vn-textDim font-semibold mb-1">Controls</p>
            <ul className="list-disc pl-4 space-y-1">
              <li>Click your unit (V) or spearman (S) to select, then click a tile to move.</li>
              <li>Villagers gather from trees or gold nodes next to them. They auto-drop at your civic center when adjacent.</li>
              <li>Spearmen fight enemies next to them. Click the enemy base tiles to attack-move.</li>
            </ul>
          </div>
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

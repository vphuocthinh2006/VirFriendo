import { useCallback, useEffect, useRef, useState } from 'react'

type Props = { onExit: () => void }

const GRID = 18
const CELL = 18
const BASE_MS = 140

type Dir = 'up' | 'down' | 'left' | 'right'

export default function SnakeGame({ onExit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const snakeRef = useRef<{ x: number; y: number }[]>([])
  const dirRef = useRef<Dir>('right')
  const pendingRef = useRef<Dir | null>(null)
  const foodRef = useRef<{ x: number; y: number }>({ x: 8, y: 8 })
  const tickRef = useRef(0)
  const overRef = useRef(false)
  const pausedRef = useRef(false)

  const [score, setScore] = useState(0)
  const scoreRef = useRef(0)
  const [best, setBest] = useState(() => {
    try {
      return Number(localStorage.getItem('vf-snake-best') || '0') || 0
    } catch {
      return 0
    }
  })
  const [paused, setPaused] = useState(false)
  const [gameOver, setGameOver] = useState(false)
  const [, setFrame] = useState(0)

  const randFood = useCallback((snake: { x: number; y: number }[]) => {
    const taken = new Set(snake.map((p) => `${p.x},${p.y}`))
    let x = 0
    let y = 0
    for (let i = 0; i < 400; i++) {
      x = Math.floor(Math.random() * GRID)
      y = Math.floor(Math.random() * GRID)
      if (!taken.has(`${x},${y}`)) break
    }
    foodRef.current = { x, y }
  }, [])

  const resetGame = useCallback(() => {
    snakeRef.current = [
      { x: 4, y: 9 },
      { x: 3, y: 9 },
      { x: 2, y: 9 },
    ]
    dirRef.current = 'right'
    pendingRef.current = null
    overRef.current = false
    pausedRef.current = false
    tickRef.current = performance.now()
    randFood(snakeRef.current)
    setScore(0)
    setPaused(false)
    setGameOver(false)
    setFrame((n) => n + 1)
  }, [randFood])

  useEffect(() => {
    resetGame()
  }, [resetGame])

  useEffect(() => {
    scoreRef.current = score
  }, [score])

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  const step = useCallback(() => {
    if (overRef.current || pausedRef.current) return
    if (pendingRef.current) {
      const p = pendingRef.current
      const d = dirRef.current
      const opp: Record<Dir, Dir> = { up: 'down', down: 'up', left: 'right', right: 'left' }
      if (p !== opp[d]) dirRef.current = p
      pendingRef.current = null
    }
    const d = dirRef.current
    const head = snakeRef.current[0]
    const nx = head.x + (d === 'right' ? 1 : d === 'left' ? -1 : 0)
    const ny = head.y + (d === 'down' ? 1 : d === 'up' ? -1 : 0)
    if (nx < 0 || nx >= GRID || ny < 0 || ny >= GRID) {
      overRef.current = true
      setGameOver(true)
      setBest((b) => {
        const ns = scoreRef.current
        if (ns > b) {
          try {
            localStorage.setItem('vf-snake-best', String(ns))
          } catch {
            /* ignore */
          }
          return ns
        }
        return b
      })
      return
    }
    const body = snakeRef.current
    if (body.some((s, i) => i > 0 && s.x === nx && s.y === ny)) {
      overRef.current = true
      setGameOver(true)
      setBest((b) => {
        const ns = scoreRef.current
        if (ns > b) {
          try {
            localStorage.setItem('vf-snake-best', String(ns))
          } catch {
            /* ignore */
          }
          return ns
        }
        return b
      })
      return
    }
    const newHead = { x: nx, y: ny }
    const food = foodRef.current
    if (nx === food.x && ny === food.y) {
      snakeRef.current = [newHead, ...body]
      setScore((s) => s + 10 + Math.floor(s / 50))
      randFood(snakeRef.current)
    } else {
      snakeRef.current = [newHead, ...body.slice(0, -1)]
    }
    setFrame((n) => n + 1)
  }, [randFood])

  const draw = useCallback(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const S = GRID * CELL
    const g = ctx.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S * 0.75)
    g.addColorStop(0, '#0f1419')
    g.addColorStop(1, '#06080c')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, S, S)
    for (let y = 0; y < GRID; y++) {
      for (let x = 0; x < GRID; x++) {
        ctx.strokeStyle = 'rgba(148,163,184,0.06)'
        ctx.strokeRect(x * CELL, y * CELL, CELL, CELL)
      }
    }
    const food = foodRef.current
    const fx = food.x * CELL
    const fy = food.y * CELL
    const pulse = 0.85 + Math.sin(performance.now() / 220) * 0.08
    ctx.fillStyle = `rgba(251, 191, 36, ${pulse})`
    ctx.shadowColor = '#fbbf24'
    ctx.shadowBlur = 12
    ctx.beginPath()
    ctx.arc(fx + CELL / 2, fy + CELL / 2, CELL * 0.32, 0, Math.PI * 2)
    ctx.fill()
    ctx.shadowBlur = 0

    const snake = snakeRef.current
    snake.forEach((seg, i) => {
      const px = seg.x * CELL
      const py = seg.y * CELL
      const t = i === 0 ? 1 : i / snake.length
      ctx.fillStyle =
        i === 0
          ? '#4ade80'
          : `rgba(34, 197, 94, ${0.45 + t * 0.4})`
      ctx.fillRect(px + 1, py + 1, CELL - 2, CELL - 2)
      if (i === 0) {
        ctx.fillStyle = 'rgba(255,255,255,0.35)'
        ctx.fillRect(px + 4, py + 4, 5, 5)
      }
    })
  }, [])

  useEffect(() => {
    let raf = 0
    const loop = (t: number) => {
      const spd = Math.max(55, BASE_MS - Math.min(70, Math.floor(scoreRef.current / 15) * 4))
      if (!pausedRef.current && !overRef.current) {
        if (t - tickRef.current >= spd) {
          tickRef.current = t
          step()
        }
      } else tickRef.current = t
      draw()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [draw, step])

  useEffect(() => {
    const queue = (d: Dir) => {
      pendingRef.current = d
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.code === 'KeyP') {
        setPaused((p) => !p)
        return
      }
      if (overRef.current || pausedRef.current) return
      if (e.code === 'ArrowUp') queue('up')
      else if (e.code === 'ArrowDown') queue('down')
      else if (e.code === 'ArrowLeft') queue('left')
      else if (e.code === 'ArrowRight') queue('right')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="vf-arcade vf-snake w-full max-w-4xl mx-auto">
      <div className="vf-arcade__hero mb-5 px-1">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="vf-arcade__eyebrow">Arcade</p>
            <h2 className="vf-arcade__title">Snake</h2>
            <p className="vf-arcade__sub text-sm text-vn-textDim mt-1 max-w-md">
              Ăn điểm vàng, đừng cắn tường hay thân. Phím mũi tên, P tạm dừng — tốc độ tăng dần theo điểm.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setPaused((p) => !p)}
              className="vf-arcade__btn vf-arcade__btn--ghost"
            >
              {paused ? 'Tiếp tục' : 'Tạm dừng'}
            </button>
            <button type="button" onClick={resetGame} className="vf-arcade__btn vf-arcade__btn--ghost">
              Chơi lại
            </button>
            <button type="button" onClick={onExit} className="vf-arcade__btn vf-arcade__btn--dim">
              Thoát
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-start justify-center gap-6">
        <div className="vf-arcade__board-wrap relative rounded-2xl p-[2px] bg-gradient-to-br from-emerald-500/40 via-amber-500/25 to-lime-500/30 shadow-[0_0_44px_rgba(74,222,128,0.14)]">
          <div className="rounded-[14px] bg-[#050608] p-2">
            <canvas
              ref={canvasRef}
              width={GRID * CELL}
              height={GRID * CELL}
              className="block rounded-lg max-w-[min(88vw,340px)] h-auto"
              style={{ imageRendering: 'pixelated' }}
            />
          </div>
          {paused && !gameOver ? (
            <div className="absolute inset-2 flex items-center justify-center rounded-xl bg-black/55 backdrop-blur-[2px]">
              <p className="text-lg font-semibold text-white/95">Tạm dừng</p>
            </div>
          ) : null}
          {gameOver ? (
            <div className="absolute inset-2 flex flex-col items-center justify-center rounded-xl bg-black/65 backdrop-blur-sm gap-2">
              <p className="text-lg font-semibold text-rose-200">Game over</p>
              <button type="button" onClick={resetGame} className="vf-arcade__btn vf-arcade__btn--primary text-sm">
                Chơi lại
              </button>
            </div>
          ) : null}
        </div>

        <aside className="vf-arcade__hud w-full max-w-[220px] space-y-4">
          <div className="vf-arcade__statgrid rounded-xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm">
            <div className="space-y-3 text-sm">
              <div>
                <p className="text-[0.65rem] uppercase tracking-widest text-vn-textDim">Điểm</p>
                <p className="text-3xl font-bold tabular-nums bg-gradient-to-r from-emerald-200 to-lime-200 bg-clip-text text-transparent">
                  {score}
                </p>
              </div>
              <div>
                <p className="text-[0.65rem] uppercase tracking-widest text-vn-textDim">Kỷ lục</p>
                <p className="text-xl font-semibold text-amber-200/90 tabular-nums">{best}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs text-vn-textDim leading-relaxed">
            <p className="font-semibold text-vn-text/90 mb-2">Điều khiển</p>
            <ul className="space-y-1 list-disc pl-4">
              <li>Mũi tên đổi hướng (không quay đầu ngược)</li>
              <li>P để pause</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  )
}

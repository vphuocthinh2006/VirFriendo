import { useCallback, useEffect, useRef, useState } from 'react'

type Props = { onExit: () => void }

const COLS = 10
const ROWS = 20
const CELL = 22

const COLORS = ['', '#22d3ee', '#fbbf24', '#a78bfa', '#4ade80', '#f87171', '#fb923c', '#60a5fa'] as const

type PieceName = 'I' | 'O' | 'T' | 'S' | 'Z' | 'J' | 'L'

const SHAPES: Record<PieceName, number[][][]> = {
  I: [
    [
      [0, 0, 0, 0],
      [1, 1, 1, 1],
      [0, 0, 0, 0],
      [0, 0, 0, 0],
    ],
    [
      [0, 0, 1, 0],
      [0, 0, 1, 0],
      [0, 0, 1, 0],
      [0, 0, 1, 0],
    ],
    [
      [0, 0, 0, 0],
      [0, 0, 0, 0],
      [1, 1, 1, 1],
      [0, 0, 0, 0],
    ],
    [
      [0, 1, 0, 0],
      [0, 1, 0, 0],
      [0, 1, 0, 0],
      [0, 1, 0, 0],
    ],
  ],
  O: [[[2, 2], [2, 2]]],
  T: [
    [
      [0, 3, 0],
      [3, 3, 3],
      [0, 0, 0],
    ],
    [
      [0, 3, 0],
      [0, 3, 3],
      [0, 3, 0],
    ],
    [
      [0, 0, 0],
      [3, 3, 3],
      [0, 3, 0],
    ],
    [
      [0, 3, 0],
      [3, 3, 0],
      [0, 3, 0],
    ],
  ],
  S: [
    [
      [0, 4, 4],
      [4, 4, 0],
      [0, 0, 0],
    ],
    [
      [0, 4, 0],
      [0, 4, 4],
      [0, 0, 4],
    ],
    [
      [0, 0, 0],
      [0, 4, 4],
      [4, 4, 0],
    ],
    [
      [4, 0, 0],
      [4, 4, 0],
      [0, 4, 0],
    ],
  ],
  Z: [
    [
      [5, 5, 0],
      [0, 5, 5],
      [0, 0, 0],
    ],
    [
      [0, 0, 5],
      [0, 5, 5],
      [0, 5, 0],
    ],
    [
      [0, 0, 0],
      [5, 5, 0],
      [0, 5, 5],
    ],
    [
      [0, 5, 0],
      [5, 5, 0],
      [5, 0, 0],
    ],
  ],
  J: [
    [
      [6, 0, 0],
      [6, 6, 6],
      [0, 0, 0],
    ],
    [
      [0, 6, 6],
      [0, 6, 0],
      [0, 6, 0],
    ],
    [
      [0, 0, 0],
      [6, 6, 6],
      [0, 0, 6],
    ],
    [
      [0, 6, 0],
      [0, 6, 0],
      [6, 6, 0],
    ],
  ],
  L: [
    [
      [0, 0, 7],
      [7, 7, 7],
      [0, 0, 0],
    ],
    [
      [0, 7, 0],
      [0, 7, 0],
      [0, 7, 7],
    ],
    [
      [0, 0, 0],
      [7, 7, 7],
      [7, 0, 0],
    ],
    [
      [7, 7, 0],
      [0, 7, 0],
      [0, 7, 0],
    ],
  ],
}

const BAG: PieceName[] = ['I', 'O', 'T', 'S', 'Z', 'J', 'L']

function emptyBoard(): number[][] {
  return Array.from({ length: ROWS }, () => Array(COLS).fill(0))
}

function rotateCount(name: PieceName) {
  return name === 'O' ? 1 : 4
}

export default function TetrisGame({ onExit }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const boardRef = useRef<number[][]>(emptyBoard())
  const pieceRef = useRef<{ name: PieceName; rot: number; x: number; y: number } | null>(null)
  const bagRef = useRef<PieceName[]>([])
  const nextRef = useRef<PieceName[]>([])
  const dropMsRef = useRef(800)
  const lastTickRef = useRef(0)
  const pausedRef = useRef(false)
  const overRef = useRef(false)

  const [score, setScore] = useState(0)
  const [lines, setLines] = useState(0)
  const [level, setLevel] = useState(1)
  const [paused, setPaused] = useState(false)
  const [gameOver, setGameOver] = useState(false)
  const [, setFrame] = useState(0)

  const fillBag = useCallback(() => {
    const a = [...BAG].sort(() => Math.random() - 0.5)
    bagRef.current.push(...a)
  }, [])

  const pullNext = useCallback((): PieceName => {
    if (bagRef.current.length === 0) fillBag()
    return bagRef.current.shift()!
  }, [fillBag])

  const collide = useCallback((b: number[][], name: PieceName, rot: number, px: number, py: number) => {
    const sh = SHAPES[name][rot % rotateCount(name)]
    for (let yy = 0; yy < sh.length; yy++) {
      for (let xx = 0; xx < sh[yy].length; xx++) {
        if (!sh[yy][xx]) continue
        const gx = px + xx
        const gy = py + yy
        if (gx < 0 || gx >= COLS || gy >= ROWS) return true
        if (gy >= 0 && b[gy][gx]) return true
      }
    }
    return false
  }, [])

  const mergePiece = useCallback(() => {
    const cur = pieceRef.current
    if (!cur) return
    const sh = SHAPES[cur.name][cur.rot % rotateCount(cur.name)]
    const b = boardRef.current
    for (let yy = 0; yy < sh.length; yy++) {
      for (let xx = 0; xx < sh[yy].length; xx++) {
        const v = sh[yy][xx]
        if (!v) continue
        const gy = cur.y + yy
        const gx = cur.x + xx
        if (gy >= 0) b[gy][gx] = v
      }
    }
  }, [])

  const clearLines = useCallback((): number => {
    const b = boardRef.current
    let cleared = 0
    for (let y = ROWS - 1; y >= 0; ) {
      if (b[y].every((c) => c !== 0)) {
        b.splice(y, 1)
        b.unshift(Array(COLS).fill(0))
        cleared++
      } else y--
    }
    return cleared
  }, [])

  const spawnPiece = useCallback((): boolean => {
    const name = nextRef.current.length ? nextRef.current.shift()! : pullNext()
    if (nextRef.current.length < 3) {
      nextRef.current.push(pullNext(), pullNext(), pullNext())
    }
    const rot = 0
    const shape = SHAPES[name][rot % rotateCount(name)]
    const w = shape[0].length
    const h = shape.length
    const x = Math.floor((COLS - w) / 2)
    const y = -h + 1
    pieceRef.current = { name, rot, x, y }
    if (collide(boardRef.current, name, rot, x, y)) {
      overRef.current = true
      setGameOver(true)
      return false
    }
    return true
  }, [collide, pullNext])

  const draw = useCallback(() => {
    const c = canvasRef.current
    if (!c) return
    const ctx = c.getContext('2d')
    if (!ctx) return
    const W = COLS * CELL
    const H = ROWS * CELL
    const g = ctx.createLinearGradient(0, 0, W, H)
    g.addColorStop(0, '#0c0a12')
    g.addColorStop(1, '#12101c')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, W, H)
    for (let y = 0; y < ROWS; y++) {
      for (let x = 0; x < COLS; x++) {
        const v = boardRef.current[y][x]
        const px = x * CELL
        const py = y * CELL
        ctx.strokeStyle = 'rgba(255,255,255,0.04)'
        ctx.strokeRect(px, py, CELL, CELL)
        if (v) {
          ctx.fillStyle = COLORS[v] ?? '#fff'
          ctx.fillRect(px + 1, py + 1, CELL - 2, CELL - 2)
          ctx.fillStyle = 'rgba(255,255,255,0.2)'
          ctx.fillRect(px + 2, py + 2, CELL * 0.35, CELL * 0.35)
        }
      }
    }
    const cur = pieceRef.current
    if (cur && !overRef.current) {
      const sh = SHAPES[cur.name][cur.rot % rotateCount(cur.name)]
      for (let yy = 0; yy < sh.length; yy++) {
        for (let xx = 0; xx < sh[yy].length; xx++) {
          const v = sh[yy][xx]
          if (!v) continue
          const gx = cur.x + xx
          const gy = cur.y + yy
          if (gy < 0) continue
          const px = gx * CELL
          const py = gy * CELL
          ctx.fillStyle = COLORS[v] ?? '#fff'
          ctx.shadowColor = COLORS[v] ?? '#fff'
          ctx.shadowBlur = 8
          ctx.fillRect(px + 1, py + 1, CELL - 2, CELL - 2)
          ctx.shadowBlur = 0
        }
      }
    }
  }, [])

  const tick = useCallback(() => {
    if (overRef.current || pausedRef.current) return
    const cur = pieceRef.current
    if (!cur) return
    if (!collide(boardRef.current, cur.name, cur.rot, cur.x, cur.y + 1)) {
      cur.y++
      setFrame((n) => n + 1)
      return
    }
    mergePiece()
    const c = clearLines()
    if (c) {
      setLines((l) => {
        const nl = l + c
        const lev = Math.floor(nl / 10) + 1
        setLevel(lev)
        dropMsRef.current = Math.max(110, 780 - (lev - 1) * 58)
        setScore((s) => s + [0, 100, 300, 500, 800][c]! * lev)
        return nl
      })
    }
    spawnPiece()
    setFrame((n) => n + 1)
  }, [clearLines, collide, mergePiece, spawnPiece])

  const resetGame = useCallback(() => {
    boardRef.current = emptyBoard()
    pieceRef.current = null
    bagRef.current = []
    nextRef.current = []
    fillBag()
    nextRef.current = [pullNext(), pullNext(), pullNext()]
    overRef.current = false
    pausedRef.current = false
    dropMsRef.current = 800
    lastTickRef.current = performance.now()
    setScore(0)
    setLines(0)
    setLevel(1)
    setPaused(false)
    setGameOver(false)
    spawnPiece()
    setFrame((n) => n + 1)
  }, [fillBag, pullNext, spawnPiece])

  useEffect(() => {
    resetGame()
  }, [resetGame])

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  useEffect(() => {
    let raf = 0
    const loop = (t: number) => {
      if (!pausedRef.current && !overRef.current) {
        if (t - lastTickRef.current >= dropMsRef.current) {
          lastTickRef.current = t
          tick()
        }
      } else lastTickRef.current = t
      draw()
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [draw, tick])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (overRef.current) return
      const cur = pieceRef.current
      if (e.code === 'KeyP') {
        setPaused((p) => !p)
        return
      }
      if (pausedRef.current) return
      if (!cur) return
      const rc = rotateCount(cur.name)
      if (e.code === 'ArrowLeft') {
        if (!collide(boardRef.current, cur.name, cur.rot, cur.x - 1, cur.y)) cur.x--
      } else if (e.code === 'ArrowRight') {
        if (!collide(boardRef.current, cur.name, cur.rot, cur.x + 1, cur.y)) cur.x++
      } else if (e.code === 'ArrowDown') {
        if (!collide(boardRef.current, cur.name, cur.rot, cur.x, cur.y + 1)) {
          cur.y++
          setScore((s) => s + 1)
        }
      } else if (e.code === 'ArrowUp') {
        const nr = (cur.rot + 1) % rc
        if (!collide(boardRef.current, cur.name, nr, cur.x, cur.y)) cur.rot = nr
      } else if (e.code === 'Space') {
        e.preventDefault()
        while (!collide(boardRef.current, cur.name, cur.rot, cur.x, cur.y + 1)) {
          cur.y++
          setScore((s) => s + 2)
        }
        mergePiece()
        const cl = clearLines()
        if (cl) {
          setLines((l) => {
            const nl = l + cl
            const lev = Math.floor(nl / 10) + 1
            setLevel(lev)
            dropMsRef.current = Math.max(110, 780 - (lev - 1) * 58)
            setScore((s) => s + [0, 100, 300, 500, 800][cl]! * lev)
            return nl
          })
        }
        spawnPiece()
      }
      setFrame((n) => n + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [clearLines, collide, mergePiece, spawnPiece])

  return (
    <div className="vf-arcade vf-tetris w-full max-w-4xl mx-auto">
      <div className="vf-arcade__hero mb-5 px-1">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="vf-arcade__eyebrow">Arcade</p>
            <h2 className="vf-arcade__title">Tetris</h2>
            <p className="vf-arcade__sub text-sm text-vn-textDim mt-1 max-w-md">
              Xếp khối, xóa hàng, leo level. Phím mũi tên, ↑ xoay, Space rơi nhanh, P tạm dừng.
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
        <div className="vf-arcade__board-wrap relative rounded-2xl p-[2px] bg-gradient-to-br from-cyan-500/35 via-violet-500/25 to-amber-500/30 shadow-[0_0_48px_rgba(34,211,238,0.12)]">
          <div className="rounded-[14px] bg-[#07060b] p-2">
            <canvas
              ref={canvasRef}
              width={COLS * CELL}
              height={ROWS * CELL}
              className="block rounded-lg max-w-[min(92vw,280px)] h-auto"
              style={{ imageRendering: 'pixelated' }}
            />
          </div>
          {paused && !gameOver ? (
            <div className="absolute inset-2 flex items-center justify-center rounded-xl bg-black/55 backdrop-blur-[2px]">
              <p className="text-lg font-semibold text-white/95 tracking-wide">Tạm dừng</p>
            </div>
          ) : null}
          {gameOver ? (
            <div className="absolute inset-2 flex flex-col items-center justify-center rounded-xl bg-black/65 backdrop-blur-sm gap-2">
              <p className="text-lg font-semibold text-rose-200">Hết lượt</p>
              <button type="button" onClick={resetGame} className="vf-arcade__btn vf-arcade__btn--primary text-sm">
                Chơi lại
              </button>
            </div>
          ) : null}
        </div>

        <aside className="vf-arcade__hud w-full max-w-[220px] space-y-4">
          <div className="vf-arcade__statgrid rounded-xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-sm">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-[0.65rem] uppercase tracking-widest text-vn-textDim">Điểm</p>
                <p className="text-2xl font-bold tabular-nums bg-gradient-to-r from-cyan-200 to-teal-200 bg-clip-text text-transparent">
                  {score}
                </p>
              </div>
              <div>
                <p className="text-[0.65rem] uppercase tracking-widest text-vn-textDim">Hàng</p>
                <p className="text-2xl font-bold tabular-nums text-vn-text">{lines}</p>
              </div>
              <div className="col-span-2">
                <p className="text-[0.65rem] uppercase tracking-widest text-vn-textDim">Cấp</p>
                <p className="text-xl font-semibold text-amber-200/90">{level}</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs text-vn-textDim leading-relaxed">
            <p className="font-semibold text-vn-text/90 mb-2">Điều khiển</p>
            <ul className="space-y-1 list-disc pl-4">
              <li>← → di chuyển · ↓ mềm · ↑ xoay</li>
              <li>Space rơi thẳng · P pause</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  )
}

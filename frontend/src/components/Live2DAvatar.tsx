import { useEffect, useRef, useState } from 'react'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'

// Make PIXI globally accessible — pixi-live2d-display registers Ticker via window.PIXI
;(window as unknown as { PIXI: typeof PIXI }).PIXI = PIXI

export type Live2DEmotion =
  | 'idle'
  | 'happy'
  | 'sad'
  | 'angry'
  | 'surprised'
  | 'sleepy'
  | 'blush'

/** Hosted Shizuku sample model — better expressions than Haru. */
const DEFAULT_MODEL_URL =
  'https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display@master/test/assets/shizuku/shizuku.model.json'

/**
 * Map our high-level emotion → motion group for Shizuku model.
 * Shizuku uses motion groups instead of named expressions.
 */
const EMOTION_EXPRESSIONS: Record<Live2DEmotion, string | null> = {
  idle: null,
  happy: 'tap_body',
  sad: 'shake',
  angry: 'flick_head',
  surprised: 'pinch_out',
  sleepy: 'pinch_in',
  blush: 'tap_body',
}

interface Props {
  /** Override model URL (default: Haru sample). */
  modelUrl?: string
  /** Current emotion. */
  emotion?: Live2DEmotion
  /** Optional className for the wrapper. */
  className?: string
  /** Render this if Live2D fails to load (e.g. Cubism Core blocked). */
  fallback?: React.ReactNode
}

export default function Live2DAvatar({
  modelUrl = DEFAULT_MODEL_URL,
  emotion = 'idle',
  className,
  fallback,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const appRef = useRef<PIXI.Application | null>(null)
  const modelRef = useRef<Live2DModel | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [errored, setErrored] = useState(false)

  // Initial create
  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = canvasRef.current
    let cancelled = false

    // Wait for Cubism Core to be available (script in index.html loads async on slow networks)
    const ensureCore = async (): Promise<boolean> => {
      const w = window as unknown as { Live2DCubismCore?: unknown }
      for (let i = 0; i < 50; i++) {
        if (w.Live2DCubismCore) return true
        await new Promise((r) => setTimeout(r, 100))
      }
      return Boolean(w.Live2DCubismCore)
    }

    // Wait until parent has non-zero size — avoids
    // "checkMaxIfStatementsInShader Invalid value 0" when canvas is 0×0.
    const waitForSize = async (): Promise<{ w: number; h: number }> => {
      const parent = canvas.parentElement
      for (let i = 0; i < 50; i++) {
        const w = Math.max(1, parent?.clientWidth || 0)
        const h = Math.max(1, parent?.clientHeight || 0)
        if (w > 1 && h > 1) return { w, h }
        await new Promise((r) => setTimeout(r, 60))
      }
      // Fallback dimensions
      return { w: 280, h: 360 }
    }

    let cleanupExtra: (() => void) | undefined

    const init = async () => {
      const ok = await ensureCore()
      if (!ok) {
        setErrored(true)
        return
      }
      try {
        const { w, h } = await waitForSize()
        if (cancelled) return

        const app = new PIXI.Application({
          view: canvas,
          width: w,
          height: h,
          autoStart: true,
          backgroundAlpha: 0,
          antialias: true,
          resolution: window.devicePixelRatio || 1,
          autoDensity: true,
        })
        if (cancelled) {
          app.destroy(true)
          return
        }
        appRef.current = app

        const model = await Live2DModel.from(modelUrl, { autoInteract: false })
        if (cancelled) {
          try { model.destroy() } catch { /* ignore */ }
          return
        }

        // Fit model into the stage area using its INTRINSIC size (not getBounds()
        // which is post-scale and unreliable before first render).
        const fit = () => {
          const a = appRef.current
          const m = modelRef.current
          const parent = canvas.parentElement
          if (!a || !m || !parent) return
          const pw = Math.max(1, parent.clientWidth)
          const ph = Math.max(1, parent.clientHeight)
          a.renderer.resize(pw, ph)
          // Reset scale before measuring, so getLocalBounds reflects intrinsic size.
          m.scale.set(1)
          const internal = (m as unknown as { internalModel?: { originalWidth?: number; originalHeight?: number } }).internalModel
          const ow = (internal?.originalWidth && internal.originalWidth > 0) ? internal.originalWidth : 1900
          const oh = (internal?.originalHeight && internal.originalHeight > 0) ? internal.originalHeight : 2700
          const scale = Math.min(pw / ow, ph / oh) * 0.95
          m.scale.set(scale)
          m.anchor.set(0.5, 1)
          m.x = pw / 2
          m.y = ph
        }
        modelRef.current = model
        app.stage.addChild(model as unknown as PIXI.DisplayObject)
        fit()
        const onMove = (e: MouseEvent) => {
          const rect = canvas.getBoundingClientRect()
          const x = e.clientX - rect.left
          const y = e.clientY - rect.top
          ;(model as unknown as { focus: (x: number, y: number) => void }).focus(x, y)
        }
        canvas.addEventListener('mousemove', onMove)
        const ro = new ResizeObserver(() => fit())
        if (canvas.parentElement) ro.observe(canvas.parentElement)
        cleanupExtra = () => {
          canvas.removeEventListener('mousemove', onMove)
          ro.disconnect()
        }
        setLoaded(true)
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('Live2D init failed:', e)
        setErrored(true)
      }
    }
    void init()

    return () => {
      cancelled = true
      try { cleanupExtra?.() } catch { /* ignore */ }
      try { modelRef.current?.destroy() } catch { /* ignore */ }
      try { appRef.current?.destroy(true) } catch { /* ignore */ }
      modelRef.current = null
      appRef.current = null
    }
  }, [modelUrl])

  // Apply emotion changes via motion groups (Shizuku model)
  useEffect(() => {
    const model = modelRef.current
    if (!loaded || !model) return
    const motionGroup = EMOTION_EXPRESSIONS[emotion]
    try {
      if (motionGroup) {
        ;(model as unknown as { motion: (group: string, index?: number) => void }).motion(motionGroup)
      }
      // idle = no explicit motion, model returns to default
    } catch { /* model may not have this motion — ignore */ }
  }, [emotion, loaded])

  if (errored && fallback) return <>{fallback}</>

  return (
    <div className={`vf-live2d-wrap${className ? ' ' + className : ''}`}>
      <canvas ref={canvasRef} className="vf-live2d-canvas" />
      {!loaded && !errored && (
        <div className="vf-live2d-loading" aria-hidden>
          <span className="vf-chat-spinner" />
        </div>
      )}
    </div>
  )
}

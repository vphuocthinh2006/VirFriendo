import { lazy, type ComponentType, type LazyExoticComponent } from 'react'
import { LOADING_MIN_MS } from '../constants/loading'

export function lazyWithMinDelay<T extends ComponentType<unknown>>(
  factory: () => Promise<{ default: T }>,
  minMs = LOADING_MIN_MS
): LazyExoticComponent<T> {
  return lazy(() =>
    Promise.all([
      factory(),
      new Promise<void>((resolve) => setTimeout(resolve, minMs)),
    ]).then(([m]) => m)
  )
}

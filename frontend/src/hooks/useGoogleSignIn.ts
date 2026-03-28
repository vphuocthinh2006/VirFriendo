import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import * as api from '../services/api'

type GsiCredentialResponse = { credential?: string }

const gsiCredentialHandler: {
  onSuccess: (credential: string) => Promise<void>
  onMissing: () => void
} = {
  onSuccess: async () => {},
  onMissing: () => {},
}

let gsiInitialized = false

function getGsiId(): {
  initialize: (o: Record<string, unknown>) => void
  renderButton: (el: HTMLElement, o: Record<string, unknown>) => void
} | null {
  const w = window as unknown as {
    google?: {
      accounts?: {
        id?: {
          initialize: (o: Record<string, unknown>) => void
          renderButton: (el: HTMLElement, o: Record<string, unknown>) => void
        }
      }
    }
  }
  return w.google?.accounts?.id ?? null
}

function ensureGsiInitialized(clientId: string): boolean {
  const id = getGsiId()
  if (!id) return false
  if (!gsiInitialized) {
    id.initialize({
      client_id: clientId,
      locale: 'en',
      auto_select: false,
      use_fedcm_for_prompt: true,
      callback: (resp: GsiCredentialResponse) => {
        const cred = resp?.credential
        if (!cred) {
          gsiCredentialHandler.onMissing()
          return
        }
        void gsiCredentialHandler.onSuccess(cred)
      },
    })
    gsiInitialized = true
  }
  return true
}

/**
 * Mounts the official GSI widget off-screen; use the returned styled CTA + `triggerGoogleSignIn`
 * so “Continue with Google” matches `aid-cta-primary` / `aid-cta-google` typography.
 */
export function useGoogleSignIn() {
  const navigate = useNavigate()
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const gsiMountRef = useRef<HTMLDivElement | null>(null)
  const [mountTick, setMountTick] = useState(0)

  const setGoogleMountRef = useCallback((node: HTMLDivElement | null) => {
    gsiMountRef.current = node
    setMountTick((n) => n + 1)
  }, [])

  useEffect(() => {
    const existing = document.getElementById('google-gsi-script') as HTMLScriptElement | null
    if (existing) {
      if (getGsiId()) setReady(true)
      return
    }
    const script = document.createElement('script')
    script.id = 'google-gsi-script'
    script.src = 'https://accounts.google.com/gsi/client?hl=en'
    script.async = true
    script.defer = true
    script.onload = () => setReady(true)
    script.onerror = () => setError('Could not load Google Sign-In script')
    document.head.appendChild(script)
  }, [])

  const runSignIn = useCallback(
    async (credential: string) => {
      setLoading(true)
      setError('')
      try {
        await api.loginWithGoogle(credential)
        navigate('/menu', { replace: true })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Google sign-in failed')
      } finally {
        setLoading(false)
      }
    },
    [navigate],
  )

  useEffect(() => {
    gsiCredentialHandler.onSuccess = runSignIn
    gsiCredentialHandler.onMissing = () => {
      setError('Could not get Google credential')
      setLoading(false)
    }
    return () => {
      gsiCredentialHandler.onSuccess = async () => {}
      gsiCredentialHandler.onMissing = () => {}
    }
  }, [runSignIn])

  useEffect(() => {
    if (!ready) return
    const clientId = (import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()
    if (!clientId) {
      setError('Missing VITE_GOOGLE_CLIENT_ID in frontend environment')
      return
    }
    const host = gsiMountRef.current
    if (!host) return

    if (!ensureGsiInitialized(clientId)) {
      setError('Google Sign-In is not ready')
      return
    }

    const id = getGsiId()
    if (!id) return

    host.innerHTML = ''
    id.renderButton(host, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      width: 320,
      text: 'continue_with',
      shape: 'rectangular',
      logo_alignment: 'left',
      locale: 'en',
    })

    return () => {
      host.innerHTML = ''
    }
  }, [ready, mountTick])

  const triggerGoogleSignIn = useCallback(() => {
    const mount = gsiMountRef.current
    if (!mount) return
    const inner = mount.querySelector<HTMLElement>('[role="button"]')
    inner?.click()
  }, [])

  const clientIdPresent = !!(import.meta.env.VITE_GOOGLE_CLIENT_ID || '').trim()

  return {
    ready: ready && clientIdPresent,
    loading,
    error,
    setError,
    googleMountRef: setGoogleMountRef,
    triggerGoogleSignIn,
  }
}

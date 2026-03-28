import { Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthBootOverlay } from './hooks/useAuthBootOverlay'
import { lazyWithMinDelay } from './utils/lazyWithMinDelay'
import ConnectingVirFriendo from './components/ConnectingVirFriendo'

const Landing = lazyWithMinDelay(() => import('./pages/Landing'))
const Contact = lazyWithMinDelay(() => import('./pages/Contact'))
const Updates = lazyWithMinDelay(() => import('./pages/Updates'))
const Login = lazyWithMinDelay(() => import('./pages/Login'))
const Register = lazyWithMinDelay(() => import('./pages/Register'))
const ForgotPassword = lazyWithMinDelay(() => import('./pages/ForgotPassword'))
const Chat = lazyWithMinDelay(() => import('./pages/Chat'))
const Menu = lazyWithMinDelay(() => import('./pages/Menu'))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuth, loading, showOverlay } = useAuthBootOverlay()

  if (!loading && !isAuth) return <Navigate to="/login" replace />

  return (
    <>
      {showOverlay ? <ConnectingVirFriendo /> : null}
      {isAuth ? children : null}
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<ConnectingVirFriendo />}>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/updates" element={<Updates />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route
            path="/menu"
            element={
              <ProtectedRoute>
                <Menu />
              </ProtectedRoute>
            }
          />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

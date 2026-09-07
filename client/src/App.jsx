import { useState, lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { AppShell } from './layouts/AppShell'
import { SplashScreen } from './pages/SplashScreen'
import { LoadingSkeleton } from './components/LoadingSkeleton'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Stations = lazy(() => import('./pages/Stations'))
const StationDetail = lazy(() => import('./pages/StationDetail'))
const Anomalies = lazy(() => import('./pages/Anomalies'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Analytics = lazy(() => import('./pages/Analytics'))
const ModelStatus = lazy(() => import('./pages/ModelStatus'))
const SystemHealth = lazy(() => import('./pages/SystemHealth'))
const TestObservation = lazy(() => import('./pages/TestObservation'))

function PageFallback() {
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <LoadingSkeleton rows={5} height="h-12" />
    </div>
  )
}

export default function App() {
  const [splashDone, setSplashDone] = useState(false)

  if (!splashDone) {
    return <SplashScreen onDone={() => setSplashDone(true)} />
  }

  return (
    <BrowserRouter>
      <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Dashboard />} />
            <Route path="stations" element={<Stations />} />
            <Route path="stations/:id" element={<StationDetail />} />
            <Route path="anomalies" element={<Anomalies />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="model-status" element={<ModelStatus />} />
            <Route path="system-health" element={<SystemHealth />} />
            <Route path="test" element={<TestObservation />} />
          </Route>
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

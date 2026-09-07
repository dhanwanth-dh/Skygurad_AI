import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const STEPS = [
  'Initializing monitoring system...',
  'Loading prediction engine...',
  'Connecting to AWS network...',
]

export function SplashScreen({ onDone }) {
  const [step, setStep] = useState(0)

  useEffect(() => {
    const timers = STEPS.map((_, i) =>
      setTimeout(() => setStep(i + 1), 300 + i * 350)
    )
    const done = setTimeout(onDone, 300 + STEPS.length * 350 + 300)
    return () => { timers.forEach(clearTimeout); clearTimeout(done) }
  }, [onDone])

  return (
    <div
      className="fixed inset-0 flex flex-col items-center justify-center z-50"
      style={{ background: '#07111F' }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center gap-6"
      >
        {/* Shield icon */}
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
          <path d="M32 4L8 14v20c0 14 10.5 24.5 24 28 13.5-3.5 24-14 24-28V14L32 4z"
            fill="none" stroke="#38BDF8" strokeWidth="2" strokeLinejoin="round" />
          <circle cx="32" cy="30" r="8" fill="#38BDF8" opacity="0.2" />
          <circle cx="32" cy="30" r="4" fill="#38BDF8" />
          <path d="M32 22v16M24 30h16" stroke="#07111F" strokeWidth="2" strokeLinecap="round" />
        </svg>

        <div className="text-center">
          <div className="text-3xl font-bold tracking-widest mb-1" style={{ color: '#F4F7FB' }}>
            SKYGUARD AI
          </div>
          <div className="text-xs tracking-widest" style={{ color: '#38BDF8' }}>
            INTELLIGENT WEATHER STATION MONITORING
          </div>
        </div>

        <div className="space-y-1.5 text-center min-h-[72px]">
          {STEPS.slice(0, step).map((s, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-xs"
              style={{ color: '#64748B' }}
            >
              {s}
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

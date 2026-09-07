import { useEffect, useRef, useState } from 'react'

export function BackgroundVideo() {
  const videoRef = useRef(null)
  const [videoActive, setVideoActive] = useState(false)

  useEffect(() => {
    const video = videoRef.current

    if (video) {
      video.muted = true
      video.defaultMuted = true
      video.playbackRate = 1

      video.play()
        .then(() => {
          setVideoActive(true)
        })
        .catch(err => {
          console.warn('Autoplay prevented:', err)

          const handleInteraction = () => {
            video.play()
              .then(() => setVideoActive(true))
              .catch(console.error)

            window.removeEventListener('click', handleInteraction)
          }

          window.addEventListener('click', handleInteraction)
        })
    }
  }, [])

  return (
    <div className="fixed inset-0 pointer-events-none -z-20 overflow-hidden bg-slate-900">

      {/* Background Video */}
      <video
        ref={videoRef}
        autoPlay
        loop
        muted
        playsInline
        preload="auto"
        onPlaying={() => setVideoActive(true)}
        className="absolute inset-0 w-full h-full object-cover transition-opacity duration-700"
        style={{
          opacity: videoActive ? 1 : 0.7,
          filter: 'brightness(1.05) contrast(1.05) saturate(1.1)',
        }}
      >
        <source src="/bg-video.mp4" type="video/mp4" />
        <source src="/bg-video.webm" type="video/webm" />
      </video>

      {/* Dark Atmospheric Overlay - NO BLUR */}
      <div
        className="absolute inset-0 bg-gradient-to-br from-slate-900/20 via-sky-950/10 to-slate-900/25"
      />

      {/* Radiant Light Vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(ellipse at 50% 30%,  rgba(15, 23, 42, 0.35) 100%)',
        }}
      />

    </div>
  )
}

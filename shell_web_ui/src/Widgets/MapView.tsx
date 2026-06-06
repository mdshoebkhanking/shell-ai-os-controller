import { lazy, Suspense, useEffect, useState } from 'react'

const MapCanvas = lazy(() => import('./MapCanvas'))

type MapPosition = [number, number]

type RouteData = {
  start: MapPosition
  end: MapPosition
  path: MapPosition[]
  info: {
    origin: string
    destination: string
    distance: string
    duration: string
  }
}

export default function LeafletMapWidget() {
  const [isVisible, setIsVisible] = useState(false)

  const [position, setPosition] = useState<MapPosition>([51.505, -0.09])
  const [locationName, setLocationName] = useState('India')

  const [isRouteMode, setIsRouteMode] = useState(false)
  const [routeData, setRouteData] = useState<RouteData | null>(null)

  useEffect(() => {
    const handleMap = (event: any) => {
      const { lat, lng, name } = event.detail
      if (lat != null && lng != null) {
        setIsRouteMode(false)
        setPosition([lat, lng])
        setLocationName(name)
        setIsVisible(true)
      }
    }

    const handleRoute = (event: any) => {
      const data = event.detail as RouteData
      setIsRouteMode(true)
      setRouteData(data)
      setPosition(data.start)
      setIsVisible(true)
    }

    window.addEventListener('map-update', handleMap)
    window.addEventListener('map-route', handleRoute)

    return () => {
      window.removeEventListener('map-update', handleMap)
      window.removeEventListener('map-route', handleRoute)
    }
  }, [])

  if (!isVisible) return null

  return (
    <div className="fixed inset-0 z-9000 flex items-center justify-center bg-black/80 backdrop-blur-md p-10 animate-in fade-in zoom-in duration-300">
      <div className="relative w-full h-full max-w-6xl max-h-[85vh] border-2 border-cyan-500/40 rounded-3xl overflow-hidden shadow-[0_0_80px_rgba(6,182,212,0.2)]">
        <div className="absolute top-0 left-0 w-full z-1000 p-4 flex justify-between items-start pointer-events-none">
          <div className="bg-black/90 border border-cyan-500/50 px-4 py-2 rounded-lg pointer-events-auto">
            {isRouteMode && routeData ? (
              <div>
                <h2 className="text-cyan-400 font-bold tracking-widest text-sm">
                  NAV: {routeData.info.origin} ➡ {routeData.info.destination}
                </h2>
                <div className="text-gray-400 text-xs font-mono mt-1">
                  DIST: <span className="text-white">{routeData.info.distance}</span> | TIME:{' '}
                  <span className="text-white">{routeData.info.duration}</span>
                </div>
              </div>
            ) : (
              <h2 className="text-cyan-400 font-bold tracking-widest text-sm">
                TARGET: {locationName}
              </h2>
            )}
          </div>
          <button
            onClick={() => setIsVisible(false)}
            className="bg-red-500/20 hover:bg-red-500 text-red-500 hover:text-white border border-red-500 px-4 py-2 rounded-lg font-bold pointer-events-auto"
          >
            CLOSE
          </button>
        </div>

        <Suspense fallback={<div className="h-full w-full bg-black" />}>
          <MapCanvas
            isRouteMode={isRouteMode}
            locationName={locationName}
            position={position}
            routeData={routeData}
          />
        </Suspense>
      </div>
    </div>
  )
}

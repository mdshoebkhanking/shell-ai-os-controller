import { useEffect } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L, { LatLngExpression } from 'leaflet'

import icon from 'leaflet/dist/images/marker-icon.png'
import iconShadow from 'leaflet/dist/images/marker-shadow.png'

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

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

function MapUpdater({ center }: { center: LatLngExpression }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center as L.LatLngTuple, 13, { duration: 2.5 })
  }, [center, map])
  return null
}

export default function MapCanvas({
  isRouteMode,
  locationName,
  position,
  routeData
}: {
  isRouteMode: boolean
  locationName: string
  position: MapPosition
  routeData: RouteData | null
}) {
  return (
    <MapContainer
      {...({ center: position, zoom: isRouteMode ? 6 : 13 } as any)}
      style={{ height: '100%', width: '100%', background: '#000' }}
    >
      <TileLayer
        {...({
          attribution: '&copy; Google Maps',
          url: 'http://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}'
        } as any)}
      />

      {!isRouteMode && (
        <Marker position={position}>
          <Popup>{locationName}</Popup>
        </Marker>
      )}

      {isRouteMode && routeData && (
        <>
          <Marker position={routeData.start}>
            <Popup>Start: {routeData.info.origin}</Popup>
          </Marker>
          <Marker position={routeData.end}>
            <Popup>End: {routeData.info.destination}</Popup>
          </Marker>

          <Polyline
            positions={routeData.path}
            pathOptions={{ color: '#22d3ee', weight: 4, dashArray: '10, 10', opacity: 0.8 }}
          />

          <MapUpdater center={routeData.start} />
        </>
      )}

      {!isRouteMode && <MapUpdater center={position} />}
    </MapContainer>
  )
}

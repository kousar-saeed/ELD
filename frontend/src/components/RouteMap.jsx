import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Custom SVG icon generator for Leaflet map markers
const createCustomIcon = (type, label) => {
  let bgColor = '#6366f1'; // indigo default
  let symbol = '📍';

  if (type === 'pickup') {
    bgColor = '#10b981'; // emerald green
    symbol = '📦';
  } else if (type === 'dropoff') {
    bgColor = '#f43f5e'; // rose red
    symbol = '🏁';
  } else if (type === 'fuel') {
    bgColor = '#f59e0b'; // amber orange
    symbol = '⛽';
  } else if (type === 'rest') {
    bgColor = label.includes('restart') ? '#8b5cf6' : '#3b82f6'; // purple restart / blue rest
    symbol = label.includes('restart') ? '🔄' : '🛑';
  }

  const svgHtml = `
    <div style="
      background-color: ${bgColor};
      color: white;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.4), 0 0 0 3px rgba(255,255,255,0.2);
      border: 2px solid #ffffff;
      cursor: pointer;
    ">
      ${symbol}
    </div>
  `;

  return L.divIcon({
    html: svgHtml,
    className: 'custom-leaflet-marker',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
};

// Component to auto-fit map view to route bounds
function MapController({ routeCoords, stops }) {
  const map = useMap();

  useEffect(() => {
    if (!routeCoords || routeCoords.length === 0) return;

    const bounds = L.latLngBounds(routeCoords);
    stops.forEach((s) => {
      if (s.lat && s.lng) bounds.extend([s.lat, s.lng]);
    });

    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }, [routeCoords, stops, map]);

  return null;
}

export default function RouteMap({ route, stops }) {
  // Convert GeoJSON [lng, lat] coordinates to Leaflet [lat, lng]
  const routeCoords = route?.geometry?.coordinates
    ? route.geometry.coordinates.map((coord) => [coord[1], coord[0]])
    : [];

  const defaultCenter = routeCoords.length > 0 ? routeCoords[0] : [39.8283, -98.5795];

  return (
    <div className="route-map-card">
      <div className="map-header">
        <div>
          <span className="live-badge">Live Interactive Map</span>
          <h4 className="map-title">Route & Rest Stop Markers</h4>
        </div>
        {route && (
          <div className="map-stats">
            <span className="stat-pill">🛣️ {route.distance_miles} mi</span>
            <span className="stat-pill">⏱️ {route.duration_hours} hrs driving</span>
            <span className="stat-pill">🛑 {stops?.length || 0} stops</span>
          </div>
        )}
      </div>

      <div className="map-container-wrapper">
        <MapContainer
          center={defaultCenter}
          zoom={6}
          scrollWheelZoom={true}
          style={{ height: '100%', width: '100%', borderRadius: '12px' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {routeCoords.length > 0 && (
            <>
              {/* Outer route shadow line */}
              <Polyline
                positions={routeCoords}
                pathOptions={{ color: '#000000', weight: 8, opacity: 0.3 }}
              />
              {/* Main route polyline */}
              <Polyline
                positions={routeCoords}
                pathOptions={{ color: '#6366f1', weight: 5, opacity: 0.9, lineCap: 'round' }}
              />
            </>
          )}

          {stops &&
            stops.map((stop, idx) => {
              if (!stop.lat || !stop.lng) return null;

              return (
                <Marker
                  key={idx}
                  position={[stop.lat, stop.lng]}
                  icon={createCustomIcon(stop.type, stop.label || '')}
                >
                  <Popup className="custom-map-popup">
                    <div className="popup-content">
                      <span className={`stop-badge ${stop.type}`}>
                        {stop.type.toUpperCase()}
                      </span>
                      <h5>{stop.label || 'Stop Marker'}</h5>
                      <div className="popup-details">
                        {stop.arrival_time && (
                          <p>
                            <strong>Arrival:</strong>{' '}
                            {new Date(stop.arrival_time).toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                        )}
                        {stop.departure_time && (
                          <p>
                            <strong>Departure:</strong>{' '}
                            {new Date(stop.departure_time).toLocaleString([], {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </p>
                        )}
                      </div>
                    </div>
                  </Popup>
                </Marker>
              );
            })}

          <MapController routeCoords={routeCoords} stops={stops || []} />
        </MapContainer>
      </div>
    </div>
  );
}

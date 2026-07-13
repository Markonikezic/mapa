'use client';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

export default function Map({ tsData, onSelectTs }) {
  const getColor = (gubitak) => {
    if (gubitak > 15) return '#ef4444'; // Crvena
    if (gubitak > 10) return '#eab308'; // Žuta
    return '#22c55e'; // Zelena
  };

  return (
    <MapContainer center={[42.44, 19.25]} zoom={12} className="h-full w-full">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {tsData.map(ts => (
        <CircleMarker 
          key={ts.id} 
          center={[ts.latitude, ts.longitude]} 
          radius={8}
          fillColor={getColor(ts.gubitak || 0)}
          color="white"
          weight={2}
          eventHandlers={{ click: () => onSelectTs(ts) }}
        >
          <Popup>{ts.naziv_ts}</Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

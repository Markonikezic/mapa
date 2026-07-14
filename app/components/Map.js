'use client';
import L from 'leaflet';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon.src,
    shadowUrl: iconShadow.src,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

export default function Map({ tsData, onSelectTs }) {
  return (
    <MapContainer center={[42.44, 19.25]} zoom={12} className="h-full w-full">
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      
      {tsData && tsData.map((ts) => {
        if (!ts.lat || !ts.lng) return null;

        return (
          <CircleMarker 
            key={ts.id} 
            center={[ts.lat, ts.lng]} 
            radius={5}
            eventHandlers={{
              click: () => onSelectTs && onSelectTs(ts),
            }}
          >
            <Popup>{ts.naziv_ts}</Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}

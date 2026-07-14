'use client';

import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

export default function Map({ tsData }) {
  const mapContainer = useRef(null);
  const mapInstance = useRef(null);

  useEffect(() => {
    // Sprečava inicijalizaciju više mapa ako se komponenta re-renderuje
    if (mapInstance.current) return;

    mapInstance.current = new maplibregl.Map({
      container: mapContainer.current,
      // Ovo je prelepa "Dark Matter" tamna mapa
      style: 'https://tiles.basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [19.25, 42.44], // Podgorica
      zoom: 12
    });

    mapInstance.current.on('load', () => {
      // Dodajemo podatke kao izvor
      mapInstance.current.addSource('trafo-stanice', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: tsData.map(ts => ({
            type: 'Feature',
            geometry: { 
              type: 'Point', 
              coordinates: [parseFloat(ts.lng), parseFloat(ts.lat)] 
            },
            properties: { name: ts.naziv_ts }
          }))
        }
      });

      // Dodajemo sloj sa crvenim krugovima
      mapInstance.current.addLayer({
        id: 'ts-layer',
        type: 'circle',
        source: 'trafo-stanice',
        paint: {
          'circle-radius': 7,
          'circle-color': '#FF3333', // Crvena boja za trafostanice
          'circle-opacity': 0.8,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#FFFFFF' // Bela ivica kruga
        }
      });
    });

    // Cleanup funkcija
    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [tsData]);

  return <div ref={mapContainer} className="h-screen w-full" />;
}

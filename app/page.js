'use client'; // Ovo je obavezno za Next.js komponente koje koriste browser funkcije

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import 'leaflet/dist/leaflet.css'; // Uvoz Leaflet stila

// 1. Inicijalizacija Supabase klijenta 
// (Koristi varijable iz tvog .env fajla)
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function MapPage() {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 2. Dinamički uvoz Leaflet-a (radi samo u browseru)
    const initMap = async () => {
      const L = (await import('leaflet')).default;

      // Popravka za ikone koje nestaju u Next.js
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
      });

      // Inicijalizacija mape na Danilovgrad
      const map = L.map('map').setView([42.5535, 19.1098], 13);

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);

      // 3. Dohvatanje podataka iz tvog novog View-a
      const { data, error } = await supabase.from('view_mapa_potrosaca').select('*');

      if (error) {
        console.error("Greška pri dohvatanju:", error);
      } else {
        // 4. Dodavanje markera
        data.forEach((potrosac) => {
          if (potrosac.lat && potrosac.lon) {
            L.marker([potrosac.lat, potrosac.lon])
              .addTo(map)
              .bindPopup(`
                <b>${potrosac.ime}</b><br>
                Pretplatni: ${potrosac.pretplatni}<br>
                Potrošnja zadnji mjesec (259): ${potrosac["259"] || 0} kWh
              `);
          }
        });
      }
      setLoading(false);
    };

    initMap();
  }, []);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100vh' }}>
      {loading && <div style={{ position: 'absolute', zIndex: 1000 }}>Učitavam podatke sa baze...</div>}
      <div id="map" style={{ width: '100%', height: '100%' }}></div>
    </div>
  );
}

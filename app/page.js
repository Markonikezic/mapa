'use client';
export const dynamic = 'force-client'; 

import { useState, useEffect } from 'react';
// Ovde menjamo ime iz 'dynamic' u 'dynamicImport'
import dynamicImport from 'next/dynamic'; 
import { createClient } from '@supabase/supabase-js';

// Sada koristimo to novo ime ovde:
const Map = dynamicImport(() => import('./components/Map'), { 
  ssr: false,
  loading: () => <div className="h-full w-full flex items-center justify-center">Učitavanje mape...</div>
});

// Inicijalizacija Supabase klijenta
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Home() {
  const [tsList, setTsList] = useState([]);
  const [selectedTs, setSelectedTs] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadTs() {
      try {
        setLoading(true);
        const { data, error } = await supabase.from('trafo_stanice').select('*');
        
        if (error) {
          console.error("Greška pri učitavanju:", error);
          return;
        }
        
        // Osiguravamo da je data niz
        setTsList(data || []);
      } catch (err) {
        console.error("Neočekivana greška:", err);
      } finally {
        setLoading(false);
      }
    }
    
    loadTs();
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950">
      {/* Sidebar - Lijeva strana */}
      <aside className="w-80 bg-slate-900 border-r border-slate-800 p-4 overflow-y-auto">
        <h1 className="text-xl font-bold mb-6 text-white">TS Monitoring</h1>
        
        {loading ? (
          <p className="text-slate-400">Učitavanje trafostanica...</p>
        ) : (
          tsList.map(ts => (
            <div 
              key={ts.id} 
              onClick={() => setSelectedTs(ts)}
              className={`p-3 mb-2 rounded cursor-pointer transition-colors ${
                selectedTs?.id === ts.id ? 'bg-blue-600' : 'bg-slate-800 hover:bg-slate-700'
              }`}
            >
              <h3 className="font-medium text-slate-100">{ts.naziv_ts}</h3>
              <p className="text-xs text-slate-400">Šifra: {ts.sifra_ts}</p>
            </div>
          ))
        )}
      </aside>

      {/* Glavni deo - Mapa */}
      <main className="flex-1 relative h-full">
        <Map tsData={tsList} onSelectTs={setSelectedTs} />
      </main>

      {/* Info Panel - Desna strana (opciono) */}
      {selectedTs && (
        <aside className="w-96 bg-slate-900 border-l border-slate-800 p-6 overflow-y-auto">
          <h2 className="text-2xl font-bold mb-4 text-white">{selectedTs.naziv_ts}</h2>
          <div className="space-y-4 text-slate-300">
            <p><span className="text-slate-500">Šifra TS:</span> {selectedTs.sifra_ts}</p>
            <p><span className="text-slate-500">Tip:</span> {selectedTs.tip_ts}</p>
            <p><span className="text-slate-500">Snaga:</span> {selectedTs.instalisana_snaga} kW</p>
          </div>
        </aside>
      )}
    </div>
  );
}

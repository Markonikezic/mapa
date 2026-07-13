
'use client';
import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { createClient } from '@supabase/supabase-js';

const Map = dynamic(() => import('@/components/Map'), { ssr: false });

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Home() {
  const [tsList, setTsList] = useState([]);
  const [selectedTs, setSelectedTs] = useState(null);

  useEffect(() => {
    async function loadTs() {
      const { data } = await supabase.from('trafo_stanice').select('*');
      setTsList(data || []);
    }
    loadTs();
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-80 bg-slate-900 border-r border-slate-800 p-4 overflow-y-auto">
        <h1 className="text-xl font-bold mb-6">TS Monitoring</h1>
        {tsList.map(ts => (
          <div key={ts.id} onClick={() => setSelectedTs(ts)} 
               className="p-3 mb-2 bg-slate-800 rounded cursor-pointer hover:bg-slate-700">
            {ts.naziv_ts}
          </div>
        ))}
      </aside>
      <main className="flex-1 relative">
        <Map tsData={tsList} onSelectTs={setSelectedTs} />
      </main>
    </div>
  );
}

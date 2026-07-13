'use client';

import { useState, useEffect } from 'react';
import dynamicImport from 'next/dynamic';
import { createClient } from '@supabase/supabase-js';

const Map = dynamicImport(() => import('./components/Map'), { 
  ssr: false,
  loading: () => <div className="h-screen w-full flex items-center justify-center">Učitavanje mape...</div>
});

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Home() {
  const [tsList, setTsList] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const { data } = await supabase.from('trafo_stanice').select('*');
      if (data) {
        // Obavezno: pretvaramo u običan niz/objekat
        setTsList(JSON.parse(JSON.stringify(data)));
      }
      setLoading(false);
    }
    fetchData();
  }, []);

  if (loading) return <div>Učitavanje...</div>;

  return (
    <main className="h-screen w-screen">
      <Map tsData={tsList} />
    </main>
  );
}

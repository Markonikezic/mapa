import psycopg2
import folium
from folium.features import DivIcon
from folium import Element
import json

# --- 1. SUPABASE PARAMETRI ---
DB_HOST = "aws-1-eu-central-2.pooler.supabase.com" 
DB_NAME = "postgres"
DB_USER = "postgres.zfcrrnusmhmcwiwqfzlz"
DB_PASS = "hz0boWvwDhG6b8ms"  # <-- UPIŠI SVOJU LOZINKU OVDE
DB_PORT = "5432"

# PALETA OD 5 KONTRASTNIH BOJA ZA TOPOLOGIJE (VODOVE I KORISNIKE)
# Svaka TS dobija jednu od ovih boja na osnovu svoje šifre kako bi se susjedne razlikovale
PALETA_BOJA = [
    {"hex": "#38bdf8", "naziv": "Svijetloplava"},
    {"hex": "#4ade80", "naziv": "Zelena"},
    {"hex": "#c084fc", "naziv": "Ljubičasta"},
    {"hex": "#fb923c", "naziv": "Narandžasta"},
    {"hex": "#facc15", "naziv": "Žuta"}
]

def odredi_boju_topologije_za_ts(sifra_ts):
    """
    Na osnovu šifre TS matematički određuje indeks u paleti od 5 boja.
    Ovo garantuje da će ista TS uvijek imati istu boju, a susjedne TS različite.
    """
    try:
        # Koristimo zbir ASCII vrijednosti karaktera šifre za stabilan hash
        suma_ascii = sum(ord(char) for char in str(sifra_ts))
        indeks = suma_ascii % len(PALETA_BOJA)
        return PALETA_BOJA[indeks]["hex"]
    except Exception:
        return PALETA_BOJA[0]["hex"]

def kreiraj_2d_kockicu_html(boja_bilansa, naziv_ts):
    # Kreiranje moderne kockice sa gromom i stalno vidljivim nazivom iznad nje
    return f"""
    <div style="position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 120px; margin-left: -50px; margin-top: -20px;">
        <!-- Naziv TS iznad ikonice -->
        <div style="
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 11px;
            font-weight: 800;
            color: #ffffff;
            text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;
            white-space: nowrap;
            margin-bottom: 4px;
            text-align: center;
        ">
            {naziv_ts}
        </div>
        <!-- Kockica sa gromom -->
        <div style="
            background: {boja_bilansa};
            width: 22px;
            height: 22px;
            border: 2px solid #ffffff;
            border-radius: 5px;
            box-shadow: 0px 3px 6px rgba(0, 0, 0, 0.4), inset 0px -3px 0px rgba(0, 0, 0, 0.25);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-size: 12px;
        ">
            <i class="fa fa-bolt" style="text-shadow: 0px 1px 2px rgba(0,0,0,0.6);"></i>
        </div>
    </div>
    """

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    cursor = conn.cursor()
    print("Uspješno povezivanje sa bazom!")

    # --- 2. DOHVATANJE SVIH DOSTUPNIH PERIODA ---
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'potrosnja' AND column_name ~ '^[0-9]+$';
    """)
    sve_kolone = sorted([row[0] for row in cursor.fetchall()], key=int)
    
    if not sve_kolone:
        print("Greška: Nema obračunskih perioda u tabeli 'potrosnja'!")
        exit()

    print(f"Pronađeno {len(sve_kolone)} perioda u bazi. Generišem podatke...")

    # --- DEFINISANJE FIKSNIH ZADNJIH 12 MJESECI ZA GODIŠNJI BILANS ---
    fiksni_poslednji_12 = sve_kolone[-12:]
    sql_suma_potrosnja_fiksna_12 = " + ".join([f"COALESCE(NULLIF(REPLACE(potr.\"{p}\", ',', ''), '')::double precision, 0)" for p in fiksni_poslednji_12])

    # --- 3. DOHVATANJE SVIH TRAFOSTANICA ---
    cursor.execute("""
        SELECT sifra_ts, naziv_ts, latitude, longitude, instalisana_snaga 
        FROM trafo_stanice
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
    """)
    sve_ts = cursor.fetchall()
    
    if not sve_ts:
        print("Greška: Nema TS u bazi!")
        exit()

    # --- 4. PRE-KALKULACIJA PODATAKA PO PERIODIMA ---
    cursor.execute("""
        SELECT sifra_ts, COUNT(pretplatni) 
        FROM baza_potrosaca 
        WHERE sifra_ts IS NOT NULL AND (lat IS NULL OR lon IS NULL)
        GROUP BY sifra_ts;
    """)
    nemapirani_po_ts = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT sifra_ts, COUNT(id) 
        FROM baza_potrosaca 
        WHERE sifra_ts IS NOT NULL
        GROUP BY sifra_ts;
    """)
    ukupno_kupaca_po_ts = {row[0]: row[1] for row in cursor.fetchall()}

    # Izračunavanje FIKSNE godišnje potrošnje kupaca po TS
    cursor.execute(f"""
        SELECT 
            p.sifra_ts,
            SUM({sql_suma_potrosnja_fiksna_12}) AS kupci_godisnje_fiksno
        FROM baza_potrosaca p
        LEFT JOIN potrosnja potr ON p.pretplatni = potr.pretplatni_broj
        WHERE p.sifra_ts IS NOT NULL
        GROUP BY p.sifra_ts;
    """)
    kupci_godisnje_fiksno_po_ts = {row[0]: row[1] for row in cursor.fetchall()}

    # Izračunavanje TRENUTNE potrošnje kupaca za svaki pojedinačni period
    kupci_trenutni_po_periodu = {p: {} for p in sve_kolone}
    for period in sve_kolone:
        cursor.execute(f"""
            SELECT 
                p.sifra_ts,
                SUM(COALESCE(NULLIF(REPLACE(potr."{period}", ',', ''), '')::double precision, 0)) AS kupci_trenutni
            FROM baza_potrosaca p
            LEFT JOIN potrosnja potr ON p.pretplatni = potr.pretplatni_broj
            WHERE p.sifra_ts IS NOT NULL
            GROUP BY p.sifra_ts;
        """)
        for row in cursor.fetchall():
            s_ts, m_val = row
            kupci_trenutni_po_periodu[period][s_ts] = m_val

    # Očitavanja na samoj TS (ts_obracun)
    sql_suma_ts_fiksna_12 = ", ".join([f'"{p}"' for p in fiksni_poslednji_12])
    cursor.execute(f"SELECT trafostanica, {sql_suma_ts_fiksna_12} FROM ts_obracun;")
    ts_ocitanja_fiksna_12_raw = cursor.fetchall()
    
    ts_godisnje_fiksno_po_ts = {}
    for row in ts_ocitanja_fiksna_12_raw:
        ts_sifra = row[0]
        suma_g_fiksno = 0.0
        for val in row[1:]:
            if val:
                try:
                    suma_g_fiksno += float(str(val).replace(',', ''))
                except ValueError:
                    pass
        ts_godisnje_fiksno_po_ts[ts_sifra] = suma_g_fiksno

    # Trenutna očitavanja TS za svaki pojedinačni period
    kolone_ts_sql = ", ".join([f'COALESCE(NULLIF(REPLACE("{p}", \',\', \'\'), \'\')::double precision, 0) AS ts_{p}' for p in sve_kolone])
    cursor.execute(f"SELECT trafostanica, {kolone_ts_sql} FROM ts_obracun;")
    ts_ocitanja_sirova = cursor.fetchall()
    
    ts_trenutni_po_periodu = {p: {} for p in sve_kolone}
    for row in ts_ocitanja_sirova:
        ts_sifra = row[0]
        for idx, period in enumerate(sve_kolone):
            val_m = row[idx + 1]
            ts_trenutni_po_periodu[period][ts_sifra] = val_m

    kolone_potr_kupci = ", ".join([f'potr."{p}"' for p in sve_kolone])
    
    # --- 5. DOHVATANJE SVIH DETALJA POTROŠAČA ---
    cursor.execute(f"""
        SELECT p.pretplatni, p.ime, p.sifra_ts, p.lat, p.lon, {kolone_potr_kupci}
        FROM baza_potrosaca p
        LEFT JOIN potrosnja potr ON p.pretplatni = potr.pretplatni_broj
        WHERE p.sifra_ts IS NOT NULL; 
    """)
    svi_potrosaci_db = cursor.fetchall()

    potrosaci_po_ts = {}
    for row in svi_potrosaci_db:
        pret = row[0]
        ime = row[1] if row[1] and row[1].strip() != "" else f"Kupac ({pret})"
        sifra_ts = row[2]
        lat = row[3]
        lon = row[4]
        
        if sifra_ts not in potrosaci_po_ts:
            potrosaci_po_ts[sifra_ts] = []
            
        potr_vrijednosti = {}
        for idx, p in enumerate(sve_kolone):
            potr_vrijednosti[p] = row[5 + idx]

        potrosaci_po_ts[sifra_ts].append({
            "pretplatni": pret,
            "ime": ime,
            "lat": lat,
            "lon": lon,
            "potrosnje": potr_vrijednosti
        })

    # --- 6. INICIJALIZACIJA MAPE ---
    mapa = folium.Map(location=[sve_ts[0][2], sve_ts[0][3]], zoom_start=14, tiles="cartodbdark_matter")
    folium.Element("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">
    """).add_to(mapa.get_root().header)

    custom_css = """
    <style>
        html, body, .folium-map {
            width: 100% !important;
            height: 100% !important;
            margin: 0;
            padding: 0;
        }
        
        #period-selector-container {
            position: absolute;
            top: 15px;
            left: 120px;
            z-index: 2100;
            background: white;
            padding: 6px 12px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 8px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            border: 1px solid #cbd5e1;
        }
        #period-selector-container label {
            font-weight: 700;
            font-size: 0.9rem;
            color: #1e293b;
        }
        #period-select {
            padding: 4px 8px;
            font-size: 0.95rem;
            font-weight: 700;
            border-radius: 5px;
            border: 1px solid #94a3b8;
            background-color: #f8fafc;
            color: #0f172a;
            cursor: pointer;
            outline: none;
        }

        /* SVIJETLI PANELI SA VISOKIM KONTRASTOM */
        .floating-panel {
            position: absolute;
            background-color: #ffffff !important;
            color: #1e293b !important;
            border-radius: 8px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            z-index: 2000;
            display: none;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            border: 1px solid #cbd5e1;
        }
        
        #draggable-panel {
            top: 15px;
            right: 15px;
            width: 340px;
        }
        
        #customers-panel {
            top: 85px;
            left: 55px;
            width: 380px;
        }
        
        .panel-header {
            background-color: #f1f5f9;
            color: #1e293b;
            border-bottom: 1px solid #e2e8f0;
            padding: 10px 14px;
            cursor: move;
            user-select: none;
            position: relative;
        }
        .panel-header h4 { 
            margin: 0; 
            font-size: 1.15rem; 
            font-weight: 700; 
            padding-right: 25px; 
            line-height: 1.2;
            color: #1e293b;
        }
        .panel-header span { 
            font-size: 0.95rem;
            color: #334155; 
            font-weight: 700;
            display: block;
            margin-top: 3px;
        }
        
        .close-panel-btn {
            position: absolute;
            top: 10px;
            right: 14px;
            background: none;
            border: none;
            color: #64748b;
            font-size: 1.4rem;
            cursor: pointer;
            line-height: 1;
            padding: 0;
        }
        .close-panel-btn:hover { color: #0f172a; }

        .panel-body {
            padding: 12px;
            background-color: #ffffff;
        }
        
        .scrollable-container {
            max-height: 300px;
            overflow-y: auto;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            margin-top: 5px;
        }
        
        .popup-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 8px;
            font-size: 0.95rem;
        }
        .popup-table th {
            text-align: left;
            background-color: #f8fafc !important;
            color: #475569 !important;
            padding: 8px 10px;
            font-weight: 700;
            border-bottom: 2px solid #e2e8f0;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .popup-table td {
            padding: 8px 10px;
            border-bottom: 1px solid #f1f5f9;
            color: #1e293b !important;
        }
        
        .popup-table tbody tr {
            background-color: #ffffff !important;
        }
        .popup-table tbody tr:hover {
            background-color: #f8fafc !important;
        }
        
        .section-title {
            font-size: 1rem;
            font-weight: 700;
            color: #1e293b;
            margin-top: 12px;
            margin-bottom: 6px;
            border-left: 4px solid #2563eb;
            padding-left: 8px;
        }
        
        .action-btn {
            display: inline-block;
            background-color: #2563eb;
            color: white !important;
            padding: 8px 16px;
            border-radius: 5px;
            text-decoration: none !important;
            font-weight: 700;
            font-size: 0.9rem;
            margin-top: 4px;
            margin-right: 5px;
            cursor: pointer;
            border: none;
            transition: background 0.2s;
        }
        .action-btn:hover { background-color: #1d4ed8; }
        .action-btn.danger {
            background-color: #dc2626;
        }
        .action-btn.danger:hover { background-color: #b91c1c; }

        .leaflet-popup-content-wrapper {
            border-radius: 8px;
            padding: 5px;
            background-color: #ffffff !important;
            color: #1e293b !important;
            border: 1px solid #cbd5e1;
        }
        .leaflet-popup-content {
            margin: 10px 14px;
            color: #1e293b !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
    </style>
    """
    mapa.get_root().header.add_child(Element(custom_css))

    opcije_dropdowna = "".join([f'<option value="{p}" {"selected" if p == sve_kolone[-1] else ""}>Period {p}</option>' for p in sve_kolone])
    
    panel_html = f"""
    <div id="period-selector-container">
        <label for="period-select">Obračunski period:</label>
        <select id="period-select" onchange="promijeniPeriod(this.value)">
            {opcije_dropdowna}
        </select>
    </div>
    <div id="search-container" style="position: absolute; top: 15px; left: 350px; z-index: 2100;">
    <input type="text" id="search-input" placeholder="Pretraži TS ili potrošača..." 
           onkeyup="pretrazi(this.value)" 
           style="padding: 8px; width: 220px; border-radius: 5px; border: 1px solid #475569; background: #1e293b; color: white;">
    </div>

    <!-- Desni panel -->
    <div id="draggable-panel" class="floating-panel">
        <div class="panel-header" id="panel-header-drag">
            <h4 id="panel-title">Naziv TS</h4>
            <span id="panel-subtitle">Šifra TS</span>
            <button class="close-panel-btn" onclick="zatvoriPanel()">&times;</button>
        </div>
        <div class="panel-body" id="panel-content">
            <!-- JS generiše redove ovdje -->
        </div>
    </div>

    <!-- Lijevi panel -->
    <div id="customers-panel" class="floating-panel">
        <div class="panel-header" id="customers-header-drag">
            <h4 id="cust-panel-title">Spisak potrošača</h4>
            <span id="cust-panel-subtitle">Naziv TS</span>
            <button class="close-panel-btn" onclick="zatvoriPotrosace()">&times;</button>
        </div>
        <div class="panel-body">
            <div class="section-title" id="cust-section-title">Geolocirani kupci (0)</div>
            <div class="scrollable-container">
                <table class="popup-table">
                    <thead>
                        <tr>
                            <th style="width: 50%;">Ime i prezime</th>
                            <th style="width: 50%; text-align: right;">Potr. (kWh) - zadnjih 12m</th>
                        </tr>
                    </thead>
                    <tbody id="customers-list-body">
                        <!-- JS generiše redove ovdje -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(Element(panel_html))

    # --- 7. FORMIRANJE STRUKTURE SVIH PODATAKA ZA JAVASCRIPT ---
    js_baza_podataka = {}
    
    for ts in sve_ts:
        sifra, naziv, lat, lon, snaga = ts
        potrosaci_lista = potrosaci_po_ts.get(sifra, []) 
        
        broj_mapiranih = len([p for p in potrosaci_lista if p['lat'] is not None])
        broj_nemapiranih = len([p for p in potrosaci_lista if p['lat'] is None])
        ukupno_kupaca = len(potrosaci_lista)

        # OVDJE SE DODJELJUJE PAMETNA BOJA TOPOLOGIJE IZ PALETE OD 5 BOJA
        boja_topologije = odredi_boju_topologije_za_ts(sifra)

        ts_g_fiksno = ts_godisnje_fiksno_po_ts.get(sifra, 0.0)
        kupci_g_fiksno = kupci_godisnje_fiksno_po_ts.get(sifra, 0.0)
        proc_g_g_fiksno = ((ts_g_fiksno - kupci_g_fiksno) / ts_g_fiksno * 100) if ts_g_fiksno > 0 else 0.0

        if ts_g_fiksno == 0:
            boja_bilansa_fiksna = "gray"
        elif proc_g_g_fiksno < 0:
            boja_bilansa_fiksna = "purple"
        elif proc_g_g_fiksno < 10.0:
            boja_bilansa_fiksna = "green"
        elif proc_g_g_fiksno <= 20.0:
            boja_bilansa_fiksna = "orange"
        else:
            boja_bilansa_fiksna = "red"

        statistika_po_periodima = {}
        for p in sve_kolone:
            ts_m = ts_trenutni_po_periodu[p].get(sifra, 0.0)
            kupci_m = kupci_trenutni_po_periodu[p].get(sifra, 0.0)
            proc_g_m = ((ts_m - kupci_m) / ts_m * 100) if ts_m > 0 else 0.0

            statistika_po_periodima[p] = {
                "ts_m": f"{ts_m:,.0f}",
                "kupci_m": f"{kupci_m:,.0f}",
                "proc_g_m": f"{proc_g_m:.1f}%",
                "boja_g_m": "#dc2626" if proc_g_m > 20 else "#16a34a"
            }

        js_baza_podataka[sifra] = {
            "naziv": naziv,
            "sifra": sifra,
            "snaga": snaga if snaga else 'N/A',
            "koordinate": [lat, lon],
            "boja_topologije": boja_topologije,  # Prosljeđujemo dodijeljenu heksadecimalnu boju
            "potrosaci": potrosaci_lista,
            "ukupno_prijavljenih": ukupno_kupaca,
            "broj_mapiranih": broj_mapiranih,
            "broj_nemapiranih": broj_nemapiranih,
            "boja_nemapirano": "#dc2626" if broj_nemapiranih > 0 else "#475569",
            
            "fiksno_godisnje": {
                "ts_g": f"{ts_g_fiksno:,.0f}",
                "kupci_g": f"{kupci_g_fiksno:,.0f}",
                "proc_g_g": f"{proc_g_g_fiksno:.1f}%",
                "boja_g_g": "#dc2626" if proc_g_g_fiksno > 20 else "#16a34a",
                "boja_bilansa": boja_bilansa_fiksna
            },
            
            "statistike": statistika_po_periodima
        }

        # Kreiranje kockice TS na mapi
        kockica_html = kreiraj_2d_kockicu_html(boja_bilansa_fiksna, naziv)
        
        folium.Marker(
            location=[lat, lon],
            icon=DivIcon(icon_size=(120, 50), icon_anchor=(60, 30), html=kockica_html),
            alt=sifra 
        ).add_to(mapa)

    # --- 8. DINAMIČKI JAVASCRIPT ---
    potrosaci_json = json.dumps(js_baza_podataka)
    aktivni_period_pocetni = sve_kolone[-1]
    svi_periodi_json = json.dumps(sve_kolone)

    dinamicki_js = """
    <script>
        var tsPodaciBaza = TOK_ZA_PODATKE;
        var trenutniPeriod = "AKTIVNI_PERIOD_POCETNI";
        var sviPeriodi = SVI_PERIODI_LISTA;
        var iscrtaniSlojevi = {}; 
        var trenutnoIzabranaSifra = null;
        var pretrazeniMarker = null; 
        var potrosackiSlojeviMarker = {}; 

        function nadjiMapu() {
            var mapElement = document.querySelector('.folium-map');
            return mapElement ? window[mapElement.id] : null;
        }

        window.promijeniPeriod = function(noviPeriod) {
            trenutniPeriod = noviPeriod;

            if (trenutnoIzabranaSifra) {
                prikaziInfoPanel(trenutnoIzabranaSifra);
            }

            for (var aktivnaSifra in iscrtaniSlojevi) {
                prikaziMrezuZaTS(aktivnaSifra);
            }
        };

        window.prikaziInfoPanel = function(sifra) {
            var tsData = tsPodaciBaza[sifra];
            if (!tsData) return;

            trenutnoIzabranaSifra = sifra;
            var statTrenutna = tsData.statistike[trenutniPeriod];
            var fiksnaGodina = tsData.fiksno_godisnje;

            document.getElementById("panel-title").innerText = tsData.naziv;
            document.getElementById("panel-subtitle").innerHTML = "Šifra: <strong style='font-size: 1.05rem; color: #0f172a;'>" + tsData.sifra + "</strong> | Snaga: <strong style='font-size: 1.05rem; color: #0f172a;'>" + tsData.snaga + " kVA</strong>";

            var htmlSadrzaj = `
                <div class="section-title">Bilans energije</div>
                <table class="popup-table">
                    <thead>
                        <tr>
                            <th>Obračun</th>
                            <th>TS (kWh)</th>
                            <th>Kupci</th>
                            <th>Gubici</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td><b>Godišnji (Fiksno)</b></td>
                            <td style="font-weight: 600;">`+ fiksnaGodina.ts_g +`</td>
                            <td style="font-weight: 600;">`+ fiksnaGodina.kupci_g +`</td>
                            <td><span style="color:`+ fiksnaGodina.boja_g_g +`; font-weight: 800; font-size: 1.05rem;">`+ fiksnaGodina.proc_g_g +`</span></td>
                        </tr>
                        <tr>
                            <td><b>Mesečni (`+ trenutniPeriod +`)</b></td>
                            <td style="font-weight: 500;">`+ statTrenutna.ts_m +`</td>
                            <td style="font-weight: 500;">`+ statTrenutna.kupci_m +`</td>
                            <td><span style="color:`+ statTrenutna.boja_g_m +`; font-weight: 800; font-size: 1.05rem;">`+ statTrenutna.proc_g_m +`</span></td>
                        </tr>
                    </tbody>
                </table>

                <div class="section-title">Statistika kupaca</div>
                <table class="popup-table">
                    <tbody>
                        <tr>
                            <td><b>Ukupno prijavljenih:</b></td>
                            <td style="text-align: right; font-weight: 700; font-size: 1.05rem;">`+ tsData.ukupno_prijavljenih +`</td>
                        </tr>
                        <tr>
                            <td><b>Mapirani (geolocirani):</b></td>
                            <td style="text-align: right; font-weight: 700; font-size: 1.05rem; color: #16a34a;">`+ tsData.broj_mapiranih +`</td>
                        </tr>
                        <tr>
                            <td><b>Nemapirani (bez koord.):</b></td>
                            <td style="text-align: right; font-weight: 700; font-size: 1.05rem; color: `+ tsData.boja_nemapirano +`;">`+ tsData.broj_nemapiranih +`</td>
                        </tr>
                    </tbody>
                </table>

                <hr style="margin: 8px 0; border: 0; border-top: 1px solid #cbd5e1;">
                <div style="text-align: center; margin-bottom: 2px;">
                    <button class="action-btn" onclick="prikaziMrezuZaTS('`+ sifra +`')">Prikaži mrežu</button>
                    <button class="action-btn danger" onclick="ukloniMrezuZaTS('`+ sifra +`')">Sakrij</button>
                </div>
            `;

            document.getElementById("panel-content").innerHTML = htmlSadrzaj;
            document.getElementById("draggable-panel").style.display = "block";
        };

        window.zatvoriPanel = function() {
            document.getElementById("draggable-panel").style.display = "none";
            zatvoriPotrosace();
            trenutnoIzabranaSifra = null;
            if (pretrazeniMarker) {
                nadjiMapu().removeLayer(pretrazeniMarker);
                pretrazeniMarker = null;
            }
        };

        window.zatvoriPotrosace = function() {
            document.getElementById("customers-panel").style.display = "none";
        };

        window.kreirajSadrzajPotrosackogPopupa = function(potrosac, tsNaziv, jeMapiran) {
            var potrVrijednost = potrosac.potrosnje[trenutniPeriod];
            var potrPrikaz = (potrVrijednost !== null && potrVrijednost !== undefined) ? parseFloat(potrVrijednost.toString().replace(/,/g, '')).toLocaleString() + " kWh" : "Nema očitavanja";

            return `
                <div style="font-family:'Segoe UI',sans-serif; color:#1e293b; min-width:220px;">
                    <h4 style="margin: 0 0 5px 0; color:#0f172a; font-weight:700; font-size:1rem;">` + potrosac.ime + `</h4>
                    <p style="margin: 0 0 8px 0; font-size:0.85rem; color:#64748b;">Pretplatni broj: <b>` + potrosac.pretplatni + `</b></p>
                    
                    <div style="border-top:1px solid #cbd5e1; padding-top:6px; margin-top:6px; font-size:0.9rem;">
                        <div>Pripada TS: <b>` + tsNaziv + `</b></div>
                        <div style="margin-top:3px;">Potrošnja (` + trenutniPeriod + `): <b style="color:#2563eb;">` + potrPrikaz + `</b></div>
                        <div style="margin-top:4px; font-size:0.8rem; color:` + (jeMapiran ? '#16a34a' : '#dc2626') + `;">
                            <b>Status: ` + (jeMapiran ? 'Geolociran' : 'Nije geolociran') + `</b>
                        </div>
                    </div>
                </div>
            `;
        };

        window.prikaziMrezuZaTS = function(sifra) {
            var mapa = nadjiMapu();
            if (!mapa) return;

            if (iscrtaniSlojevi[sifra]) {
                mapa.removeLayer(iscrtaniSlojevi[sifra]);
            }

            var tsData = tsPodaciBaza[sifra];
            var slojGrupa = L.featureGroup();
            var tsCoords = tsData.koordinate;
            potrosackiSlojeviMarker[sifra] = {};

            // Uzimamo specifičnu heksadecimalnu boju dodijeljenu ovoj TS
            var bojaMreze = tsData.boja_topologije;

            tsData.potrosaci.forEach(function(p) {
                var lat = p.lat || tsCoords[0];
                var lon = p.lon || tsCoords[1];
                var jeMapiran = (p.lat !== null);

                if (jeMapiran) {
                    // Crtamo vodove u boji te mreže
                    L.polyline([tsCoords, [lat, lon]], {
                        color: bojaMreze, weight: 1.5, opacity: 0.6
                    }).addTo(slojGrupa);

                    // Crtamo krugove potrošača u boji te mreže
                    var m = L.circleMarker([lat, lon], {
                        radius: 5, 
                        fillColor: '#ffffff', 
                        color: bojaMreze,     
                        weight: 2, 
                        fillOpacity: 0.9
                    });

                    m.bindPopup(kreirajSadrzajPotrosackogPopupa(p, tsData.naziv, true));
                    m.addTo(slojGrupa);

                    potrosackiSlojeviMarker[sifra][p.pretplatni] = m;
                }
            });

            slojGrupa.addTo(mapa);
            iscrtaniSlojevi[sifra] = slojGrupa;
            
            document.getElementById("cust-panel-subtitle").innerText = tsData.naziv + " (" + sifra + ")";
            document.getElementById("cust-section-title").innerText = "Svi potrošači (" + tsData.potrosaci.length + ")";

            var tbody = document.getElementById("customers-list-body");
            tbody.innerHTML = ""; 

            var sortiraniPotrosaci = [...tsData.potrosaci].sort((a, b) => {
                var aMapiran = (a.lat !== null);
                var bMapiran = (b.lat !== null);
                if (aMapiran === bMapiran) return a.ime.localeCompare(b.ime);
                return aMapiran ? 1 : -1;
            });

            sortiraniPotrosaci.forEach(function(p) {
                var lat = p.lat || tsCoords[0];
                var lon = p.lon || tsCoords[1];
                var jeMapiran = (p.lat !== null);

                var row = document.createElement("tr");
                var canvasId = "chart-" + p.pretplatni;
                var stilImena = !jeMapiran ? 'style="color: #dc2626; font-weight: 800;"' : 'style="color: #1e293b;"';

                row.innerHTML = `
                    <td ${stilImena} style="font-size: 0.85rem;">
                        ` + p.ime + ` ` + (!jeMapiran ? '<br><small style="color: #dc2626;">(NEMAPIRAN NA MAPI!)</small>' : '') + `<br>
                        <small style="color: #64748b;">` + p.pretplatni + `</small>
                    </td>
                    <td style="width: 120px; padding: 2px; vertical-align: middle;">
                        <canvas id="` + canvasId + `" width="120" height="35" style="display:block; margin: auto;"></canvas>
                    </td>
                `;

                row.style.cursor = "pointer";
                
                row.onclick = function() {
                    // Resetuj sve druge pinove TE TRAFOSTANICE na njenu fabričku boju mreže
                    for (var pretNum in potrosackiSlojeviMarker[sifra]) {
                        potrosackiSlojeviMarker[sifra][pretNum].setStyle({
                            color: bojaMreze,
                            fillColor: '#ffffff',
                            radius: 5,
                            weight: 2
                        });
                    }

                    if (jeMapiran) {
                        mapa.setView([lat, lon], 18);
                        var izabraniMarker = potrosackiSlojeviMarker[sifra][p.pretplatni];
                        if (izabraniMarker) {
                            izabraniMarker.setStyle({
                                color: '#dc2626',      // Selektovani pin postaje jarko crven
                                fillColor: '#fca5a5',  
                                radius: 8,             
                                weight: 3
                            });
                            izabraniMarker.openPopup();
                        }
                    } else {
                        mapa.setView([lat, lon], 16);
                        var tempPopup = L.popup()
                            .setLatLng([lat, lon])
                            .setContent(kreirajSadrzajPotrosackogPopupa(p, tsData.naziv, false))
                            .openOn(mapa);
                    }
                };

                tbody.appendChild(row);
                setTimeout(function() { nacrtajMiniBarChart(canvasId, p.potrosnje); }, 10);
            });

            document.getElementById("customers-panel").style.display = "block";
        };

        window.nacrtajMiniBarChart = function(canvasId, potrosnjeKupca) {
            var canvas = document.getElementById(canvasId);
            if (!canvas) return;
            var ctx = canvas.getContext('2d');
            
            var poslednjih12Perioda = sviPeriodi.slice(-12);
            var podaci = poslednjih12Perioda.map(p => {
                var v = potrosnjeKupca[p];
                if (v === null || v === undefined) return 0;
                return parseFloat(v.toString().replace(/,/g, '')) || 0;
            });
            var maxVal = Math.max(...podaci, 10); 
            
            var w = canvas.width;
            var h = canvas.height;
            var barW = (w / 12) - 1;
            
            ctx.clearRect(0, 0, w, h);
            
            poslednjih12Perioda.forEach(function(p, idx) {
                var val = podaci[idx];
                var barH = (val / maxVal) * (h - 2);
                var x = idx * (w / 12);
                
                ctx.fillStyle = (p === trenutniPeriod) ? '#2563eb' : '#94a3b8';
                ctx.fillRect(x, h - barH, barW, barH);
            });
        };

        window.ukloniMrezuZaTS = function(sifra) {
            var mapa = nadjiMapu();
            if (!mapa) return;

            if (iscrtaniSlojevi[sifra]) {
                mapa.removeLayer(iscrtaniSlojevi[sifra]);
                delete iscrtaniSlojevi[sifra];
            }
            if (potrosackiSlojeviMarker[sifra]) {
                delete potrosackiSlojeviMarker[sifra];
            }
            zatvoriPotrosace();
        };

        window.pretrazi = function(tekst) {
            var mapa = nadjiMapu();
            if (!mapa) return;

            if (pretrazeniMarker) {
                mapa.removeLayer(pretrazeniMarker);
                pretrazeniMarker = null;
            }

            if (!tekst) return;
            tekst = tekst.toLowerCase();
            
            for (var sifra in tsPodaciBaza) {
                var ts = tsPodaciBaza[sifra];
                if (ts.naziv.toLowerCase().includes(tekst) || ts.sifra.toLowerCase().includes(tekst)) {
                    mapa.setView(ts.koordinate, 16);
                    prikaziInfoPanel(sifra);
                    return;
                }
                for (var i = 0; i < ts.potrosaci.length; i++) {
                    var p = ts.potrosaci[i];
                    if (p.ime.toLowerCase().includes(tekst) || p.pretplatni.toString().includes(tekst)) {
                        var lat = p.lat || ts.koordinate[0];
                        var lon = p.lon || ts.koordinate[1];
                        
                        pretrazeniMarker = L.circleMarker([lat, lon], {
                            radius: 14,
                            color: '#dc2626',
                            weight: 3,
                            fill: false,
                            dashArray: '5, 5'
                        }).addTo(mapa);

                        mapa.setView([lat, lon], p.lat ? 18 : 16);
                        prikaziInfoPanel(sifra);
                        prikaziMrezuZaTS(sifra);
                        return;
                    }
                }
            }
        };

        // --- DRAG & DROP ZA PANELE ---
        function omoguciPrevlacenje(panelId, headerId) {
            var panel = document.getElementById(panelId);
            var header = document.getElementById(headerId);
            
            var active = false;
            var currentX;
            var currentY;
            var initialX;
            var initialY;
            var xOffset = 0;
            var yOffset = 0;

            header.addEventListener("touchstart", dragStart, false);
            document.addEventListener("touchend", dragEnd, false);
            document.addEventListener("touchmove", drag, false);

            header.addEventListener("mousedown", dragStart, false);
            document.addEventListener("mouseup", dragEnd, false);
            document.addEventListener("mousemove", drag, false);

            function dragStart(e) {
                if (e.type === "touchstart") {
                    initialX = e.touches[0].clientX - xOffset;
                    initialY = e.touches[0].clientY - yOffset;
                } else {
                    initialX = e.clientX - xOffset;
                    initialY = e.clientY - yOffset;
                }

                if (e.target === header || header.contains(e.target)) {
                    active = true;
                }
            }

            function dragEnd() {
                initialX = currentX;
                initialY = currentY;
                active = false;
            }

            function drag(e) {
                if (active) {
                    e.preventDefault();

                    if (e.type === "touchmove") {
                        currentX = e.touches[0].clientX - initialX;
                        currentY = e.touches[0].clientY - initialY;
                    } else {
                        currentX = e.clientX - initialX;
                        currentY = e.clientY - initialY;
                    }

                    xOffset = currentX;
                    yOffset = currentY;

                    panel.style.transform = "translate3d(" + currentX + "px, " + currentY + "px, 0)";
                }
            }
        }

        omoguciPrevlacenje("draggable-panel", "panel-header-drag");
        omoguciPrevlacenje("customers-panel", "customers-header-drag");

        document.addEventListener("DOMContentLoaded", function() {
            var mapa = nadjiMapu();
            if (mapa) {
                mapa.eachLayer(function(layer) {
                    if (layer instanceof L.Marker && layer.options.alt) {
                        var sifra = layer.options.alt;
                        layer.on('click', function() {
                            prikaziInfoPanel(sifra);
                        });
                    }
                });
            }
        });
    </script>
    """.replace("TOK_ZA_PODATKE", potrosaci_json).replace("AKTIVNI_PERIOD_POCETNI", aktivni_period_pocetni).replace("SVI_PERIODI_LISTA", svi_periodi_json)

    mapa.get_root().html.add_child(Element(dinamicki_js))

    # --- 9. ČUVANJE MAPE ---
    mapa.save("bilans_mreze_danilovgrad.html")
    print("\n" + "="*50)
    print("USPJEH! Generisana je nova mapa.")
    print("Sada svaka TS i njeni pripadajući vodovi/potrošači koriste postojane i")
    print("različite kontrastne boje, što ti omogućava da bez miješanja upališ")
    print("više susjednih traforeona istovremeno!")
    print("="*50)

except Exception as e:
    print("Greška:", e)
finally:
    if 'conn' in locals() and conn:
        cursor.close()
        conn.close()
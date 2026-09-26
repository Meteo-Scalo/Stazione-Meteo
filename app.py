import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

# Nome del database SQLite condiviso
DB_NAME = "meteo_database.db"

st.set_page_config(page_title="Stazione meteo amatoriale di Monterotondo Scalo", layout="wide", page_icon="🌦️")

# Funzione per connettersi e caricare i dati dal database
@st.cache_data(ttl=30)
def load_data():
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql("SELECT * FROM misurazioni ORDER BY Data ASC", conn)
    except Exception:
        df = pd.DataFrame(columns=['Data', 'Temperatura_Min_C', 'Temperatura_Max_C', 'Temperatura_Media_C', 'Umidita_%', 'Pioggia_mm'])
    conn.close()
    if not df.empty:
        df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce')
    return df

st.title("🌦️ Stazione meteo amatoriale di Monterotondo Scalo")

df = load_data()

# Menu laterale con tutte le voci sempre visibili
menu = st.sidebar.radio("Menu Principale", [
    "📊 Dashboard & Record Mensili",
    "🔍 Dettaglio Giornaliero",
    "📅 Dettaglio & Estremi Mensili",
    "📈 Estremi Annuali",
    "➕ Inserisci Misura",
    "📁 Importa / Esporta Dati"
])

if df.empty:
    st.warning("Il database è attualmente vuoto. Utilizza la sezione 'Importa / Esporta Dati' o 'Inserisci Misura' per popolare le misurazioni.")
else:
    if 'Data_dt' not in df.columns:
        df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce')

# ==========================================
# 1. DASHBOARD & RECORD MENSILI E ASSOLUTI
# ==========================================
if menu == "📊 Dashboard & Record Mensili":
    st.header("Dashboard: Record Mensili e Assoluti")
    st.write("Tabella riepilogativa con le due temperature massime più alte e le due minime più basse per ogni mese, inclusi i record assoluti.")
    
    mesi_nomi = {
        1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
        5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
        9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
    }
    
    temp_df = df.copy()
    temp_df['Mese_Num'] = temp_df['Data_dt'].dt.month
    
    table_data = []
    
    for m_num in range(1, 13):
        m_data = temp_df[temp_df['Mese_Num'] == m_num]
        if not m_data.empty:
            # Prendi le 2 massime più alte
            top2_max = m_data.nlargest(2, 'Temperatura_Max_C')
            max_str_list = []
            for _, r in top2_max.iterrows():
                max_str_list.append(f"{r['Temperatura_Max_C']:.1f} °C ({str(r['Data']).split()[0]})")
            max_str = " | ".join(max_str_list)
            
            # Prendi le 2 minime più basse
            bot2_min = m_data.nsmallest(2, 'Temperatura_Min_C')
            min_str_list = []
            for _, r in bot2_min.iterrows():
                min_str_list.append(f"{r['Temperatura_Min_C']:.1f} °C ({str(r['Data']).split()[0]})")
            min_str = " | ".join(min_str_list)
            
            table_data.append({
                "Mese": mesi_nomi[m_num],
                "Top 2 Temp Max": max_str,
                "Top 2 Temp Min": min_str
            })
            
    summary_df = pd.DataFrame(table_data)
    if not summary_df.empty:
        st.dataframe(summary_df, use_container_width=True)
        
    # Riga record assoluti
    if not temp_df.empty:
        abs_max_idx = temp_df['Temperatura_Max_C'].idxmax()
        abs_max_val = temp_df.loc[abs_max_idx, 'Temperatura_Max_C']
        abs_max_date = str(temp_df.loc[abs_max_idx, 'Data']).split()[0]
        
        abs_min_idx = temp_df['Temperatura_Min_C'].idxmin()
        abs_min_val = temp_df.loc[abs_min_idx, 'Temperatura_Min_C']
        abs_min_date = str(temp_df.loc[abs_min_idx, 'Data']).split()[0]
        
        st.markdown("### 🌟 Record Assoluti Generali")
        col_a, col_b = st.columns(2)
        col_a.metric("Temperatura Max Assoluta", f"{abs_max_val:.1f} °C", f"Data: {abs_max_date}")
        col_b.metric("Temperatura Min Assoluta", f"{abs_min_val:.1f} °C", f"Data: {abs_min_date}")

# ==========================================
# 2. DETTAGLIO GIORNALIERO (RANGE)
# ==========================================
elif menu == "🔍 Dettaglio Giornaliero":
    st.header("Dettaglio Giornaliero (Intervallo Date)")
    
    min_d = df['Data_dt'].min().date()
    max_d = df['Data_dt'].max().date()
    
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Data Inizio", min_d)
    end_date = col2.date_input("Data Fine", max_d)
    
    filtered_df = df[(df['Data_dt'].dt.date >= start_date) & (df['Data_dt'].dt.date <= end_date)]
    st.dataframe(filtered_df.drop(columns=['Data_dt'], errors='ignore'), use_container_width=True)

# ==========================================
# 3. DETTAGLIO & ESTREMI MENSILI
# ==========================================
elif menu == "📅 Dettaglio & Estremi Mensili":
    st.header("Dettaglio & Estremi Mensili")
    
    col1, col2 = st.columns(2)
    anni_disp = sorted(df['Data_dt'].dt.year.dropna().unique())
    sel_anno = col1.selectbox("Seleziona Anno", anni_disp) if anni_disp else datetime.now().year
    
    mesi_dict = {
        "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4,
        "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8,
        "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
    }
    sel_mese_str = col2.selectbox("Seleziona Mese", list(mesi_dict.keys()))
    sel_mese_num = mesi_dict[sel_mese_str]
    
    m_data = df[(df['Data_dt'].dt.year == sel_anno) & (df['Data_dt'].dt.month == sel_mese_num)]
    
    if m_data.empty:
        st.info("Nessun dato trovato per il mese e anno selezionati.")
    else:
        st.subheader(f"📊 Riepilogo Estremi - {sel_mese_str} {sel_anno}")
        tmax_max = m_data['Temperatura_Max_C'].max()
        tmin_min = m_data['Temperatura_Min_C'].min()
        tmed_mean = m_data['Temperatura_Media_C'].mean()
        rain_sum = m_data['Pioggia_mm'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Temp Max Assoluta", f"{tmax_max:.1f} °C")
        c2.metric("Temp Min Assoluta", f"{tmin_min:.1f} °C")
        c3.metric("Temp Media Mese", f"{tmed_mean:.1f} °C")
        c4.metric("Pioggia Totale", f"{rain_sum:.1f} mm")
        
        st.subheader("📋 Tutte le misurazioni del mese")
        st.dataframe(m_data.drop(columns=['Data_dt'], errors='ignore'), use_container_width=True)

# ==========================================
# 4. ESTREMI ANNUALI
# ==========================================
elif menu == "📈 Estremi Annuali":
    st.header("Estremi Annuali")
    
    temp_df = df.copy()
    temp_df['Anno'] = temp_df['Data_dt'].dt.year
    
    annual_list = []
    for anno, group in temp_df.groupby('Anno'):
        if group.empty:
            continue
        max_idx = group['Temperatura_Max_C'].idxmax()
        max_val = group.loc[max_idx, 'Temperatura_Max_C']
        max_date = str(group.loc[max_idx, 'Data']).split()[0]
        
        min_idx = group['Temperatura_Min_C'].idxmin()
        min_val = group.loc[min_idx, 'Temperatura_Min_C']
        min_date = str(group.loc[min_idx, 'Data']).split()[0]
        
        rain_sum = group['Pioggia_mm'].sum()
        
        annual_list.append({
            "Anno": int(anno),
            "Temp Max Assoluta (°C)": f"{max_val:.1f}",
            "Data Max": max_date,
            "Temp Min Assoluta (°C)": f"{min_val:.1f}",
            "Data Min": min_date,
            "Pioggia Totale (mm)": f"{rain_sum:.1f}"
        })
        
    annual_df = pd.DataFrame(annual_list)
    st.dataframe(annual_df, use_container_width=True)

# ==========================================
# 5. INSERISCI MISURA MANUALE
# ==========================================
elif menu == "➕ Inserisci Misura":
    st.header("Inserimento Manuale Dati nel Database")
    with st.form("form_inserimento"):
        col1, col2 = st.columns(2)
        with col1:
            data_ins = st.date_input("Data", datetime.today())
            t_min = st.number_input("Temperatura Min (°C)", value=15.0, format="%.1f")
            t_max = st.number_input("Temperatura Max (°C)", value=25.0, format="%.1f")
        with col2:
            t_med = st.number_input("Temperatura Media (°C)", value=20.0, format="%.1f")
            hum = st.number_input("Umidità (%)", value=60.0, format="%.1f")
            rain = st.number_input("Pioggia (mm)", value=0.0, format="%.1f")
            
        submit = st.form_submit_button("Salva nel Database")
        if submit:
            try:
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS misurazioni (
                        Data TEXT PRIMARY KEY,
                        Temperatura_Min_C REAL,
                        Temperatura_Max_C REAL,
                        Temperatura_Media_C REAL,
                        Umidita_Perc REAL,
                        Pioggia_mm REAL
                    )
                ''')
                cursor.execute('''
                    INSERT OR REPLACE INTO misurazioni (Data, Temperatura_Min_C, Temperatura_Max_C, Temperatura_Media_C, Umidita_Perc, Pioggia_mm)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data_ins.strftime('%Y-%m-%d'), t_min, t_max, t_med, hum, rain))
                conn.commit()
                conn.close()
                st.cache_data.clear()
                st.success("Misura registrata con successo nel database!")
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

# ==========================================
# 6. IMPORTA / ESPORTA DATI
# ==========================================
elif menu == "📁 Importa / Esporta Dati":
    st.header("Gestione File (CSV / Excel)")
    
    st.subheader("📥 Importa da file esterno")
    uploaded_file = st.file_uploader("Carica file CSV o Excel", type=["csv", "xlsx", "xls"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(('.xlsx', '.xls')):
                df_up = pd.read_excel(uploaded_file)
            else:
                df_up = pd.read_csv(uploaded_file)
            
            conn = sqlite3.connect(DB_NAME)
            df_up.to_sql('misurazioni', conn, if_exists='replace', index=False)
            conn.close()
            st.cache_data.clear()
            st.success("Database aggiornato con successo tramite il file caricato!")
        except Exception as e:
            st.error(f"Errore nell'importazione: {e}")
            
    st.subheader("📤 Esporta database")
    if not df.empty:
        csv_bytes = df.drop(columns=['Data_dt'], errors='ignore').to_csv(index=False).encode('utf-8')
        st.download_button("Scarica dati in formato CSV", data=csv_bytes, file_name="export_meteo.csv", mime="text/csv")
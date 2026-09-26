import streamlit as st
import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
from datetime import datetime

# Nome del database SQLite condiviso con la versione PC
DB_NAME = "meteo_database.db"

st.set_page_config(page_title="Gestore Stazione Meteo - Web App", layout="wide", page_icon="🌦️")

# Funzione per connettersi e caricare i dati dal database
@st.cache_data(ttl=30)
def load_data():
    conn = sqlite3.connect(DB_NAME)
    try:
        df = pd.read_sql("SELECT * FROM misurazioni ORDER BY Data ASC", conn)
    except Exception:
        df = pd.DataFrame(columns=['Data', 'Temperatura_Min_C', 'Temperatura_Max_C', 'Temperatura_Media_C', 'Umidita_Perc', 'Pioggia_mm'])
    conn.close()
    if not df.empty:
        # Normalizzazione del campo data
        df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce')
    return df

st.title("🌦️ Gestore Statistiche Meteo (Versione Web)")
st.write("Applicazione speculare al software desktop, collegata allo stesso database SQLite[cite: 1].")

df = load_data()

# Menu di navigazione laterale speculare alle funzioni del tool PC
menu = st.sidebar.selectbox("Menu Principale", [
    "📊 Dashboard & Trend",
    "📈 Confronto Giornaliero",
    "📅 Storico Mese & Anno",
    "➕ Inserisci Misura",
    "📁 Importa / Esporta Dati",
    "📱 Card Social"
])

if df.empty:
    st.warning("Il database è attualmente vuoto. Utilizza la sezione 'Importa / Esporta Dati' o 'Inserisci Misura' per popolare le misurazioni[cite: 1].")
else:
    if 'Data_dt' not in df.columns:
        df['Data_dt'] = pd.to_datetime(df['Data'], errors='coerce')

# ==========================================
# 1. DASHBOARD & TREND
# ==========================================
if menu == "📊 Dashboard & Trend":
    st.header("Riepilogo e Andamento Generale")
    
    if not df.empty:
        max_assoluta = df['Temperatura_Max_C'].max()
        min_assoluta = df['Temperatura_Min_C'].min()
        media_generale = df['Temperatura_Media_C'].mean()
        total_rain = df['Pioggia_mm'].sum()
        avg_hum = df['Umidita_Perc'].mean()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Temp Max Assoluta", f"{max_assoluta:.1f} °C")
        col2.metric("Temp Min Assoluta", f"{min_assoluta:.1f} °C")
        col3.metric("Temperatura Media", f"{media_generale:.1f} °C")
        col4.metric("Pioggia Totale", f"{total_rain:.1f} mm")
        
        st.subheader("📈 Andamento Temperature nel Tempo")
        chart_data = df.set_index('Data')[['Temperatura_Max_C', 'Temperatura_Media_C', 'Temperatura_Min_C']]
        st.line_chart(chart_data)
        
        st.subheader("📋 Tabella Completa Dati")
        st.dataframe(df.drop(columns=['Data_dt'], errors='ignore'), use_container_width=True)

# ==========================================
# 2. CONFRONTO GIORNALIERO (Richiesta specifica)
# ==========================================
elif menu == "📈 Confronto Giornaliero":
    st.header("Confronto Giornaliero con la Media Storica")
    st.write("Seleziona un Anno e un Mese per confrontare le temperature giornaliere con la media storica dello stesso giorno negli anni precedenti.")
    
    if not df.empty:
        anni_disponibili = sorted(df['Data_dt'].dt.year.dropna().unique(), reverse=True)
        col_a, col_m = st.columns(2)
        sel_anno = col_a.selectbox("Seleziona Anno", anni_disponibili)
        
        mesi_dict = {
            "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4,
            "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8,
            "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
        }
        sel_mese_str = col_m.selectbox("Seleziona Mese", list(mesi_dict.keys()))
        m_num = mesi_dict[sel_mese_str]
        
        # Filtra dati del mese/anno selezionato
        df_target = df[(df['Data_dt'].dt.year == sel_anno) & (df['Data_dt'].dt.month == m_num)].copy()
        
        if df_target.empty:
            st.info(f"Nessun dato registrato per {sel_mese_str} {sel_anno}.")
        else:
            df_target['Giorno'] = df_target['Data_dt'].dt.day
            
            # Calcolo media storica dello stesso giorno negli altri anni
            df_storico = df[(df['Data_dt'].dt.month == m_num) & (df['Data_dt'].dt.year != sel_anno)].copy()
            if not df_storico.empty:
                df_storico['Giorno'] = df_storico['Data_dt'].dt.day
                storico_avg = df_storico.groupby('Giorno')['Temperatura_Media_C'].mean().reset_index()
                storico_avg =órico_avg.rename(columns={'Temperatura_Media_C': 'Media_Storica'}) if 'órico_avg' not in locals() else storico_avg
                storico_avg = storico_avg.rename(columns={'Temperatura_Media_C': 'Media_Storica'})
            else:
                storico_avg = pd.DataFrame(columns=['Giorno', 'Media_Storica'])
                
            # Uniamo per il grafico
            merged = pd.merge(df_target[['Giorno', 'Temperatura_Media_C', 'Temperatura_Max_C', 'Temperatura_Min_C']], storico_avg, on='Giorno', how='left')
            merged = merged.sort_values('Giorno').set_index('Giorno')
            
            fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
            ax.plot(merged.index, merged['Temperatura_Media_C'], marker='o', color='#1976d2', linewidth=2, label=f'Temp. Media {sel_mese_str} {sel_anno}')
            ax.plot(merged.index, merged['Temperatura_Max_C'], marker='^', color='#d32f2f', linestyle='--', alpha=0.7, label=f'Temp. Max {sel_anno}')
            ax.plot(merged.index, merged['Temperatura_Min_C'], marker='v', color='#388e3c', linestyle='--', alpha=0.7, label=f'Temp. Min {sel_anno}')
            
            if not storico_avg.empty:
                ax.plot(merged.index, merged['Media_Storica'], color='black', linestyle='-.', linewidth=2, label='Media Storica Giornaliera')
                
            ax.set_title(f"Confronto Giornaliero - {sel_mese_str} {sel_anno}", fontsize=12, fontweight='bold')
            ax.set_xlabel("Giorno del Mese")
            ax.set_ylabel("Temperatura (°C)")
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(loc='best')
            
            st.pyplot(fig)

# ==========================================
# 3. STORICO MESE & ANNO
# ==========================================
elif menu == "📅 Storico Mese & Anno":
    st.header("Analisi Storica Mensile e Annuale")
    tab_m, tab_a = st.tabs(["📊 Storico Mese", "📊 Storico Anno"])
    
    with tab_m:
        mesi_dict = {
            "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4,
            "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8,
            "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
        }
        sel_m_str = st.selectbox("Mese di riferimento:", list(mesi_dict.keys()), key="storico_m")
        m_val = mesi_dict[sel_m_str]
        
        temp_df = df.copy()
        temp_df['Anno'] = temp_df['Data_dt'].dt.year
        temp_df['Mese'] = temp_df['Data_dt'].dt.month
        m_data = temp_df[temp_df['Mese'] == m_val]
        
        if not m_data.empty:
            hist_m = m_data.groupby('Anno')['Temperatura_Media_C'].mean().reset_index()
            fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
            ax.plot(hist_m['Anno'].astype(str), hist_m['Temperatura_Media_C'], marker='o', color='#3f51b5', linewidth=2.5)
            ax.set_title(f"Temperatura Media Storica per il mese di {sel_m_str}", fontweight='bold')
            ax.set_ylabel("Temp (°C)")
            ax.grid(True, linestyle='--', alpha=0.6)
            st.pyplot(fig)
        else:
            st.info("Nessun dato disponibile per questo mese.")
            
    with tab_a:
        temp_df = df.copy()
        temp_df['Anno'] = temp_df['Data_dt'].dt.year
        hist_a = temp_df.groupby('Anno')['Temperatura_Media_C'].mean().reset_index()
        if not hist_a.empty:
            fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
            ax.plot(hist_a['Anno'].astype(str), hist_a['Temperatura_Media_C'], marker='s', color='#2e7d32', linewidth=2.5)
            ax.set_title("Temperatura Media Annua", fontweight='bold')
            ax.set_ylabel("Temp (°C)")
            ax.grid(True, linestyle='--', alpha=0.6)
            st.pyplot(fig)

# ==========================================
# 4. INSERISCI MISURA MANUALE
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
                st.success("Misura registrata con successo nel database[cite: 1]!")
            except Exception as e:
                st.error(f"Errore durante il salvataggio: {e}")

# ==========================================
# 5. IMPORTA / ESPORTA DATI
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
            st.success("Database aggiornato con successo tramite il file caricato[cite: 1]!")
        except Exception as e:
            st.error(f"Errore nell'importazione: {e}")
            
    st.subheader("📤 Esporta database")
    if not df.empty:
        csv_bytes = df.drop(columns=['Data_dt'], errors='ignore').to_csv(index=False).encode('utf-8')
        st.download_button("Scarica dati in formato CSV", data=csv_bytes, file_name="export_meteo.csv", mime="text/csv")

# ==========================================
# 6. CARD SOCIAL
# ==========================================
elif menu == "📱 Card Social":
    st.header("Riepilogo Dati per Social Network")
    if not df.empty:
        latest_row = df.iloc[-1]
        st.info("Ultima rilevazione disponibile nel database:")
        st.markdown(f"""
        * **Data:** {latest_row['Data']}
        * **Temp Min:** {latest_row['Temperatura_Min_C']} °C
        * **Temp Max:** {latest_row['Temperatura_Max_C']} °C
        * **Temp Media:** {latest_row['Temperatura_Media_C']} °C
        * **Umidità:** {latest_row['Umidita_Perc']} %
        * **Pioggia:** {latest_row['Pioggia_mm']} mm
        """)
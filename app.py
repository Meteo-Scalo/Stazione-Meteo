from datetime import datetime, timedelta
import io
import os
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import pandas as pd
import requests
import sqlite3
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Nome del database SQLite condiviso
DB_NAME = "meteo_database.db"

st.set_page_config(
    page_title="Stazione meteo amatoriale di Monterotondo Scalo",
    layout="wide",
    page_icon="🌦️",
)

# Stile CSS personalizzato per centrare titoli, metriche e tabelle in tutte le pagine
st.markdown(
    """
    <style>
    /* Centratura di titoli e sottotitoli */
    h1, h2, h3, h4 {
        text-align: center;
    }
    
    /* Centratura delle metriche */
    div[data-testid="stMetric"] {
        text-align: center;
        align-items: center;
    }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"], div[data-testid="stMetricDelta"] {
        text-align: center !important;
        justify-content: center !important;
    }

    /* Centratura tabelle e dataframe */
    div[data-testid="stDataFrame"] {
        display: flex;
        justify-content: center;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Configura il refresh automatico ogni 10 minuti (10 min * 60 sec * 1000 ms)
st_autorefresh(interval=10 * 60 * 1000, key="weather_autorefresh")


# Funzione per connettersi e caricare i dati dal database e inizializzare la tabella previsioni se non esiste
@st.cache_data(ttl=30)
def load_data():
  conn = sqlite3.connect(DB_NAME)
  cursor = conn.cursor()

  # Tabella misurazioni storiche
  try:
    df = pd.read_sql("SELECT * FROM misurazioni ORDER BY Data ASC", conn)
  except Exception:
    df = pd.DataFrame(columns=[
        "Data",
        "Temperatura_Min_C",
        "Temperatura_Max_C",
        "Temperatura_Media_C",
        "Umidita_%",
        "Pioggia_mm",
    ])

  # Tabella previsioni manuali a 3 giorni
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS previsioni (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Giorno_Label TEXT,
            Temp_Max REAL,
            Temp_Min REAL,
            Descrizione TEXT
        )
    """)
  cursor.execute("SELECT COUNT(*) FROM previsioni")
  if cursor.fetchone()[0] == 0:
    default_prev = [
        ("Oggi", 35.0, 20.0, "Soleggiato"),
        ("Venerdì 24", 35.0, 17.0, "Parzialmente soleggiato"),
        ("Sabato 25", 35.0, 21.0, "Parzialmente soleggiato"),
    ]
    cursor.executemany(
        """
            INSERT INTO previsioni (Giorno_Label, Temp_Max, Temp_Min, Descrizione)
            VALUES (?, ?, ?, ?)
        """,
        default_prev,
    )
    conn.commit()

  conn.close()
  if not df.empty:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")
  return df


# Funzione per caricare le previsioni dal database
def load_forecasts():
  conn = sqlite3.connect(DB_NAME)
  try:
    f_df = pd.read_sql("SELECT * FROM previsioni", conn)
  except Exception:
    f_df = pd.DataFrame(
        columns=["ID", "Giorno_Label", "Temp_Max", "Temp_Min", "Descrizione"]
    )
  conn.close()
  return f_df


# Funzione per recuperare i dati live da Weather Underground PWS API
def fetch_wunderground_data(station_id, api_key):
  if not station_id or not api_key:
    return None, "Credenziali Weather Underground mancanti nei Secrets."

  url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={api_key}"

  try:
    response = requests.get(url, timeout=10)
    if response.status_code == 200:
      return response.json(), "OK"
    else:
      return None, f"Errore HTTP {response.status_code}: {response.text}"
  except Exception as e:
    return None, f"Errore di connessione: {str(e)}"


# ==========================================
# FUNZIONE ICONE METEO AVANZATE & DETTAGLIATE
# ==========================================
def draw_weather_icon(draw, cx, cy, desc_lower):
  import math

  if "piogg" in desc_lower or "temporale" in desc_lower or "rovesci" in desc_lower:
    # Nuvola temporalesca/pioggia di qualità elevata
    # Ombra nuvola
    draw.ellipse([cx - 48, cy - 22, cx + 52, cy + 22], fill="#4A5568")
    # Corpo nuvola principale
    draw.ellipse([cx - 50, cy - 25, cx + 50, cy + 18], fill="#A0AEC0", outline="#2D3748", width=3)
    draw.ellipse([cx - 30, cy - 40, cx + 30, cy + 5], fill="#CBD5E0", outline="#2D3748", width=3)
    
    if "temporale" in desc_lower:
      # Saetta luminosa
      points = [(cx - 5, cy + 15), (cx + 10, cy + 15), (cx - 2, cy + 32), (cx + 12, cy + 32), (cx - 10, cy + 55), (cx + 2, cy + 35), (cx - 8, cy + 35)]
      draw.polygon(points, fill="#ECC94B", outline="#B7791F", width=2)
    else:
      # Gocce di pioggia multiple stilizzate
      for dx in [-20, 0, 20]:
        draw.ellipse([cx + dx - 4, cy + 22, cx + dx + 4, cy + 34], fill="#3182CE", outline="#2B6CB0", width=1)

  elif "neve" in desc_lower:
    draw.ellipse([cx - 50, cy - 25, cx + 50, cy + 18], fill="#E2E8F0", outline="#A0AEC0", width=3)
    draw.text((cx - 15, cy + 18), "❄️", fill="#3182CE")

  elif "nuvol" in desc_lower or "coperto" in desc_lower:
    # Nuvola soffice tridimensionale
    draw.ellipse([cx - 52, cy - 22, cx + 48, cy + 22], fill="#CBD5E0")
    draw.ellipse([cx - 50, cy - 25, cx + 50, cy + 18], fill="#EDF2F7", outline="#A0AEC0", width=3)
    draw.ellipse([cx - 30, cy - 42, cx + 25, cy + 2], fill="#FFFFFF", outline="#A0AEC0", width=3)

  elif "variabil" in desc_lower or "schiarite" in desc_lower or "parzialmente" in desc_lower:
    # Sole parzialmente coperto da nuvola
    # Raggi e corpo sole sullo sfondo
    for angle in range(0, 360, 45):
      rad = math.radians(angle)
      x1 = cx - 10 + int(35 * math.cos(rad))
      y1 = cy - 10 + int(35 * math.sin(rad))
      x2 = cx - 10 + int(45 * math.cos(rad))
      y2 = cy - 10 + int(45 * math.sin(rad))
      draw.line([x1, y1, x2, y2], fill="#ED8936", width=4)
    draw.ellipse([cx - 35, cy - 45, cx + 15, cy + 5], fill="#F6AD55", outline="#DD6B20", width=2)
    # Nuvola in primo piano
    draw.ellipse([cx - 20, cy - 10, cx + 52, cy + 32], fill="#EDF2F7", outline="#718096", width=3)

  else:
    # Sole splendente di alta qualità con raggi sfumati ed espressivo
    for angle in range(0, 360, 45):
      rad = math.radians(angle)
      x1 = cx + int(42 * math.cos(rad))
      y1 = cy + int(42 * math.sin(rad))
      x2 = cx + int(58 * math.cos(rad))
      y2 = cy + int(58 * math.sin(rad))
      draw.line([x1, y1, x2, y2], fill="#DD6B20", width=5)
    
    # Cerchio esterno e interno del sole
    draw.ellipse([cx - 38, cy - 38, cx + 38, cy + 38], fill="#DD6B20")
    draw.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill="#ED8936")
    draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill="#F6E05E")


# ==========================================
# GENERAZIONE INFOGRAFICA STILE CARD PREMIUM
# ==========================================
def create_comic_infographic(f_df):
  width, height = 1080, 1350
  # Sfondo notte stellata profonda ed elegante
  img = Image.new("RGB", (width, height), color="#0F172A")
  draw = ImageDraw.Draw(img)

  # Caricamento font sicuri
  try:
    font_title = ImageFont.truetype("arial.ttf", 46)
    font_sub = ImageFont.truetype("arial.ttf", 26)
    font_card_title = ImageFont.truetype("arial.ttf", 34)
    font_card_big = ImageFont.truetype("arial.ttf", 64)
    font_card_text = ImageFont.truetype("arial.ttf", 24)
  except:
    font_title = ImageFont.load_default()
    font_sub = ImageFont.load_default()
    font_card_title = ImageFont.load_default()
    font_card_big = ImageFont.load_default()
    font_card_text = ImageFont.load_default()

  # Intestazione superiore
  draw.text((width / 2, 65), "METEO MONTEROTONDO SCALO", fill="#FFFFFF", font=font_title, anchor="mm")
  today_str = datetime.now().strftime("Aggiornato al %A %d %B %Y").capitalize()
  draw.text((width / 2, 125), today_str, fill="#38BDF8", font=font_sub, anchor="mm")

  if f_df.empty:
    return img

  # 1. Card Principale Sinistra (Oggi)
  oggi_row = f_df.iloc[0]
  card_oggi_box = [50, 180, 510, 1300]
  # Effetto vetro / card metallizzata scura e raffinata
  draw.rounded_rectangle(card_oggi_box, radius=30, fill="#1E293B", outline="#475569", width=4)

  # Intestazione Card Oggi
  draw.text((280, 235), str(oggi_row["Giorno_Label"]).upper(), fill="#F8FAFC", font=font_card_title, anchor="mm")
  
  # Temperatura grande
  temp_str = f"{oggi_row['Temp_Max']:.0f}°C"
  draw.text((280, 345), temp_str, fill="#38BDF8", font=font_card_big, anchor="mm")

  # Icona meteo centrale grande in evidenza
  draw_weather_icon(draw, 280, 570, str(oggi_row["Descrizione"]).lower())

  # Dettagli Minima e Condizioni nella card principale
  draw.text((280, 780), f"Minima: {oggi_row['Temp_Min']:.1f}°C", fill="#94A3B8", font=font_card_text, anchor="mm")
  draw.text((280, 850), f"Condizioni: {oggi_row['Descrizione']}", fill="#F1F5F9", font=font_card_title, anchor="mm")

  # 2. Tre Card Laterali a Destra (Giorni successivi)
  right_cards_y = [180, 555, 930]
  card_height = 345
  rx1, rx2 = 540, 1030

  for i in range(1, min(len(f_df), 4)):
    row = f_df.iloc[i]
    ry = right_cards_y[i - 1]
    
    # Sfondo card destra in stile dark card
    draw.rounded_rectangle([rx1, ry, rx2, ry + card_height], radius=24, fill="#1E293B", outline="#475569", width=3)

    # Etichetta giorno
    draw.text((rx1 + 40, ry + 40), str(row["Giorno_Label"]).upper(), fill="#F8FAFC", font=font_card_title)

    # Temperature
    t_str = f"{row['Temp_Max']:.0f}°C / {row['Temp_Min']:.0f}°C"
    draw.text((rx1 + 40, ry + 105), t_str, fill="#38BDF8", font=font_card_title)

    # Descrizione
    draw.text((rx1 + 40, ry + 175), str(row["Descrizione"]), fill="#94A3B8", font=font_card_text)

    # Icona meteo avanzata a destra nella card
    draw_weather_icon(draw, rx2 - 110, ry + 190, str(row["Descrizione"]).lower())

  return img


# Intestazione grafica ridotta in altezza tagliando dalla parte superiore
image_filename = "684225363_1433769152096303_7382692641941825555_n.png"
if os.path.exists(image_filename):
  try:
    img = Image.open(image_filename)
    w, h = img.size
    new_h = int(h * 0.55)
    top = 0
    img_cropped = img.crop((0, top, w, top + new_h))
    st.image(img_cropped, use_container_width=True)
  except Exception:
    st.image(image_filename, use_container_width=True)
else:
  st.title("🌦️ Stazione meteo amatoriale di Monterotondo Scalo")
  st.warning(f"⚠️ Immagine di intestazione ('{image_filename}') non trovata nella cartella del repository.")

df = load_data()

# Menu laterale con la voce "Previsioni Meteo"
menu = st.sidebar.radio(
    "Menu Principale",
    [
        "📊 Dashboard",
        "🔮 Previsioni Meteo",
        "🔍 Consultazione Database",
        "📅 Dati Giornalieri",
        "📈 Dati Mensili",
        "📊 Grafici Annuali",
        "➕ Inserisci Misura",
        "📁 Importa / Esporta Dati",
    ],
)

# Gestione dello stato di autenticazione per le aree protette
if "auth_ok" not in st.session_state:
  st.session_state["auth_ok"] = False

try:
  wu_station_id = str(st.secrets["wunderground"]["station_id"])
  wu_api_key = str(st.secrets["wunderground"]["api_key"])
except Exception:
  wu_station_id = ""
  wu_api_key = ""

try:
  admin_password = str(st.secrets["admin"]["password"])
except Exception:
  admin_password = "admin123"

if df.empty:
  st.warning("Il database è attualmente vuoto. Utilizza la sezione 'Importa / Esporta Dati' o 'Inserisci Misura' per popolare le misurazioni.")
else:
  if "Data_dt" not in df.columns:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")

# ==========================================
# 1. DASHBOARD
# ==========================================
if menu == "📊 Dashboard":
  st.header("Condizioni in tempo reale")

  if wu_station_id and wu_api_key:
    wu_data, err_msg = fetch_wunderground_data(wu_station_id, wu_api_key)
    if wu_data and "observations" in wu_data and len(wu_data["observations"]) > 0:
      try:
        obs = wu_data["observations"][0]
        metric = obs.get("metric", {})

        temp_raw = metric.get("temp")
        heat_raw = metric.get("heatIndex")
        wind_chill_raw = metric.get("windChill")
        feels_raw = heat_raw if heat_raw is not None else (wind_chill_raw if wind_chill_raw is not None else temp_raw)

        hum_val = obs.get("humidity", "N.D.")
        pressure_raw = metric.get("pressure", "N.D.")
        rain_val = obs.get("precipTotal", 0.0)
        obs_time = obs.get("obsTimeLocal", "Aggiornato di recente")

        try:
          temp_val = f"{float(temp_raw):.1f} °C"
        except (ValueError, TypeError):
          temp_val = "N.D."

        try:
          feels_val = f"{float(feels_raw):.1f} °C"
        except (ValueError, TypeError):
          feels_val = "N.D."

        try:
          pressure_val = f"{float(pressure_raw):.1f} hPa"
        except (ValueError, TypeError):
          pressure_val = "N.D."

        if "pressure_history" not in st.session_state:
          st.session_state["pressure_history"] = []

        current_time = datetime.now()
        current_pressure = float(pressure_raw) if pressure_raw is not None else None

        if current_pressure is not None:
          st.session_state["pressure_history"].append((current_time, current_pressure))
          three_hours_ago = current_time - timedelta(hours=3)
          st.session_state["pressure_history"] = [(t, p) for t, p in st.session_state["pressure_history"] if t >= three_hours_ago]

        history = st.session_state["pressure_history"]
        if len(history) >= 2 and current_pressure is not None:
          oldest_pressure = history[0][1]
          diff = current_pressure - oldest_pressure
          if diff > 0.6:
            press_trend_str = "In aumento 🟢 ↗️"
          elif diff < -0.6:
            press_trend_str = "In calo 🔴 ↘️"
          else:
            press_trend_str = "Stabile ➡️"
        else:
          press_trend_str = "Stabile ➡️"

        col_l1, col_l2, col_l3, col_l4, col_l5, col_l6, col_l7 = st.columns(7)
        with col_l1:
          st.metric(label="🌡️ Temperatura", value=temp_val)
        with col_l2:
          st.metric(label="🌡️ Temp. Avvertita", value=feels_val)
        with col_l3:
          st.metric(label="💧 Umidità", value=f"{hum_val} %" if hum_val != "N.D." and hum_val is not None else "N.D.")
        with col_l4:
          st.metric(label="⏱️ Pressione", value=pressure_val)
        with col_l5:
          st.metric(label="📉 Trend Pressione", value=press_trend_str)
        with col_l6:
          st.metric(label="☔ Pioggia Odierna", value=f"{rain_val:.1f} mm")
        with col_l7:
          st.metric(label="🟢 Stato", value="Online")

        st.caption(f"Ultima rilevazione stazione: {obs_time}")

      except Exception as e:
        st.warning(f"Errore nell'elaborazione dei dati meteo: {e}")
    else:
      st.error(f"Impossibile recuperare i dati da Weather Underground. Dettaglio: {err_msg}")
  else:
    st.info("💡 Configura le credenziali Weather Underground (`station_id` e `api_key`) nella sezione [wunderground] dei Secrets di Streamlit.")

  st.markdown("---")
  st.subheader("Estremi Meteo")
  st.markdown("<p style='text-align: center;'>Tabella riepilogativa con le due temperature massime più alte e le due minime più basse per ogni mese, inclusi i record assoluti.</p>", unsafe_allow_html=True)

  mesi_nomi = {
      1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
      5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
      9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
  }

  temp_df = df.copy()
  temp_df["Mese_Num"] = temp_df["Data_dt"].dt.month

  table_data = []

  for m_num in range(1, 13):
    m_data = temp_df[temp_df["Mese_Num"] == m_num]
    if not m_data.empty:
      top2_max = m_data.nlargest(2, "Temperatura_Max_C")
      max_str_list = []
      for _, r in top2_max.iterrows():
        max_str_list.append(f"{r['Temperatura_Max_C']:.1f} °C ({str(r['Data']).split()[0]})")
      max_str = " | ".join(max_str_list)

      bot2_min = m_data.nsmallest(2, "Temperatura_Min_C")
      min_str_list = []
      for _, r in bot2_min.iterrows():
        min_str_list.append(f"{r['Temperatura_Min_C']:.1f} °C ({str(r['Data']).split()[0]})")
      min_str = " | ".join(min_str_list)

      table_data.append({
          "Mese": mesi_nomi[m_num],
          "Top 2 Temp Max": max_str,
          "Top 2 Temp Min": min_str,
      })

  summary_df = pd.DataFrame(table_data)
  if not summary_df.empty:
    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Mese": st.column_config.TextColumn("Mese", width="small"),
            "Top 2 Temp Max": st.column_config.TextColumn("🔥 Top 2 Temperature Massime (Valore e Data)", width="large"),
            "Top 2 Temp Min": st.column_config.TextColumn("❄️ Top 2 Temperature Minime (Valore e Data)", width="large"),
        },
    )

  if not temp_df.empty:
    abs_max_idx = temp_df["Temperatura_Max_C"].idxmax()
    abs_max_val = temp_df.loc[abs_max_idx, "Temperatura_Max_C"]
    abs_max_date = str(temp_df.loc[abs_max_idx, "Data"]).split()[0]

    abs_min_idx = temp_df["Temperatura_Min_C"].idxmin()
    abs_min_val = temp_df.loc[abs_min_idx, "Temperatura_Min_C"]
    abs_min_date = str(temp_df.loc[abs_min_idx, "Data"]).split()[0]

    st.markdown("### 🌟 Record Assoluti Generali")
    col_a, col_b = st.columns(2)
    col_a.metric("Temperatura Max Assoluta", f"{abs_max_val:.1f} °C", f"Data: {abs_max_date}")
    col_b.metric("Temperatura Min Assoluta", f"{abs_min_val:.1f} °C", f"Data: {abs_min_date}")

# ==========================================
# 2. PREVISIONI METEO (STILE CARD PREMIUM)
# ==========================================
elif menu == "🔮 Previsioni Meteo":
  st.header("🔮 Previsioni Meteo (Prossimi 3 Giorni)")
  st.write("Previsioni meteorologiche configurate e aggiornate per la stazione di Monterotondo Scalo.")

  f_df = load_forecasts()

  if not f_df.empty:
    cols = st.columns(len(f_df))
    for i, row in f_df.iterrows():
      with cols[i]:
        st.metric(
            label=f"📅 {row['Giorno_Label']}",
            value=f"Max: {row['Temp_Max']:.1f}°C",
            delta=f"Min: {row['Temp_Min']:.1f}°C",
            delta_color="off",
        )
        st.caption(row["Descrizione"])

    st.markdown("---")
    st.subheader("🎨 Infografica in Stile Card Premium (4:5)")
    st.write("Anteprima dell'infografica con icone avanzate e layout a card in stile moderno:")

    comic_img = create_comic_infographic(f_df)
    st.image(comic_img, use_container_width=True)

    buf_fc = io.BytesIO()
    comic_img.save(buf_fc, format="png")
    buf_fc.seek(0)

    st.download_button(
        label="📥 Scarica Infografica Stile Card Premium (PNG 4:5)",
        data=buf_fc,
        file_name="previsioni_meteo_card_premium.png",
        mime="image/png",
    )

  st.markdown("---")
  st.subheader("⚙️ Modifica Previsioni (Area Riservata)")

  if not st.session_state["auth_ok"]:
    pwd_prev = st.text_input("Inserisci la password amministratore per modificare le previsioni:", type="password", key="pwd_prev_input")
    if st.button("Accedi per Modificare", key="btn_prev_login"):
      if pwd_prev == admin_password:
        st.session_state["auth_ok"] = True
        st.rerun()
      else:
        st.error("❌ Password errata.")
  else:
    st.success("🔓 Accesso autorizzato per la modifica previsioni")
    if st.button("🔒 Esci dall'area protetta", key="btn_prev_logout"):
      st.session_state["auth_ok"] = False
      st.rerun()

    with st.form("form_modifica_previsioni"):
      st.write("Aggiorna i dati per i giorni successivi:")
      updated_rows = []

      current_f = load_forecasts()
      for idx, row in current_f.iterrows():
        st.markdown(f"**Giorno {idx+1}**")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
          g_label = st.text_input(f"Etichetta {idx+1}", value=row["Giorno_Label"], key=f"label_{idx}")
        with c2:
          t_max = st.number_input(f"Max (°C) {idx+1}", value=float(row["Temp_Max"]), format="%.1f", key=f"tmax_{idx}")
        with c3:
          t_min = st.number_input(f"Min (°C) {idx+1}", value=float(row["Temp_Min"]), format="%.1f", key=f"tmin_{idx}")
        with c4:
          desc = st.text_input(f"Descrizione {idx+1}", value=row["Descrizione"], key=f"desc_{idx}")
        updated_rows.append((row["ID"], g_label, t_max, t_min, desc))

      submit_prev = st.form_submit_button("Salva Nuove Previsioni")
      if submit_prev:
        try:
          conn = sqlite3.connect(DB_NAME)
          cursor = conn.cursor()
          for r_id, g_label, t_max, t_min, desc in updated_rows:
            cursor.execute("""
                            UPDATE previsioni 
                            SET Giorno_Label = ?, Temp_Max = ?, Temp_Min = ?, Descrizione = ?
                            WHERE ID = ?
                        """, (g_label, t_max, t_min, desc, r_id))
          conn.commit()
          conn.close()
          st.cache_data.clear()
          st.success("Previsioni aggiornate con successo!")
          st.rerun()
        except Exception as e:
          st.error(f"Errore durante il salvataggio delle previsioni: {e}")

# ==========================================
# 3. CONSULTAZIONE DATABASE
# ==========================================
elif menu == "🔍 Consultazione Database":
  st.header("Consultazione Database (Intervallo Date)")

  min_d = df["Data_dt"].min().date()
  max_d = df["Data_dt"].max().date()

  col1, col2 = st.columns(2)
  start_date = col1.date_input("Data Inizio", min_d)
  end_date = col2.date_input("Data Fine", max_d)

  filtered_df = df[(df["Data_dt"].dt.date >= start_date) & (df["Data_dt"].dt.date <= end_date)]
  st.dataframe(filtered_df.drop(columns=["Data_dt"], errors="ignore"), use_container_width=True, hide_index=True)

# ==========================================
# 4. DATI GIORNALIERI
# ==========================================
elif menu == "📅 Dati Giornalieri":
  st.header("Dati Giornalieri & Grafico con Confronto Storico")

  current_year = datetime.now().year
  current_month = datetime.now().month

  col1, col2 = st.columns(2)
  anni_disp = sorted(df["Data_dt"].dt.year.dropna().unique())

  default_anno_idx = anni_disp.index(current_year) if current_year in anni_disp else (len(anni_disp) - 1 if anni_disp else 0)
  sel_anno = col1.selectbox("Seleziona Anno", anni_disp, index=default_anno_idx) if anni_disp else current_year

  mesi_dict = {
      "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4,
      "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8,
      "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
  }
  mesi_list = list(mesi_dict.keys())
  default_mese_name = [k for k, v in mesi_dict.items() if v == current_month][0]
  default_mese_idx = mesi_list.index(default_mese_name) if default_mese_name in mesi_list else 0

  sel_mese_str = col2.selectbox("Seleziona Mese", mesi_list, index=default_mese_idx)
  sel_mese_num = mesi_dict[sel_mese_str]

  m_data = df[(df["Data_dt"].dt.year == sel_anno) & (df["Data_dt"].dt.month == sel_mese_num)]

  if m_data.empty:
    st.info("Nessun dato trovato per il mese e anno selezionati.")
  else:
    st.subheader(f"📊 Riepilogo Estremi - {sel_mese_str} {sel_anno}")
    tmax_max = m_data["Temperatura_Max_C"].max()
    tmin_min = m_data["Temperatura_Min_C"].min()
    tmed_mean = m_data["Temperatura_Media_C"].mean()
    rain_sum = m_data["Pioggia_mm"].sum()

    hist_mese_data = df[df["Data_dt"].dt.month == sel_mese_num]
    hist_tmed_mean = hist_mese_data["Temperatura_Media_C"].mean()
    delta_tmed = tmed_mean - hist_tmed_mean

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Temp Max Assoluta", f"{tmax_max:.1f} °C")
    c2.metric("Temp Min Assoluta", f"{tmin_min:.1f} °C")
    c3.metric("Temp Media Mese", f"{tmed_mean:.1f} °C", delta=f"{delta_tmed:+.1f} °C vs storica", delta_color="inverse")
    c4.metric("Pioggia Totale", f"{rain_sum:.1f} mm")

    st.caption(f"💡 Media storica di {sel_mese_str} calcolata sul totale degli anni: {hist_tmed_mean:.1f} °C")

    st.markdown("---")
    st.subheader("📱 Grafico Formato Instagram (4:5) - Temperatura & Pioggia")

    hist_prev = df[(df["Data_dt"].dt.month == sel_mese_num) & (df["Data_dt"].dt.year < sel_anno)]
    if hist_prev.empty:
      hist_prev = hist_mese_data

    hist_daily_mean = hist_prev.groupby(hist_prev["Data_dt"].dt.day)["Temperatura_Media_C"].mean().reset_index()
    hist_daily_mean.columns = ["Giorno", "Temp_Media_Storica"]

    m_data_plot = m_data.copy()
    m_data_plot["Giorno"] = m_data_plot["Data_dt"].dt.day
    m_data_plot = pd.merge(m_data_plot, hist_daily_mean, on="Giorno", how="left")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(5.5, 6.8), dpi=180, sharex=True)

    ax1.plot(m_data_plot["Giorno"], m_data_plot["Temperatura_Media_C"], label=f"Media Misurata {sel_anno} (°C)", color="#2ca02c", linewidth=1.8, marker="o", markersize=3)
    ax1.plot(m_data_plot["Giorno"], m_data_plot["Temp_Media_Storica"], label="Media Storica (Anni Prec.) (°C)", color="#ff7f0e", linewidth=1.8, linestyle="--")
    ax1.set_title(f"Confronto Temperatura Media & Pioggia\n{sel_mese_str} {sel_anno}", fontsize=11, fontweight="bold", pad=10)
    ax1.set_ylabel("Temperatura (°C)", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=7)

    ax2.bar(m_data_plot["Giorno"], m_data_plot["Pioggia_mm"], label="Pioggia (mm)", color="#1c83e1", alpha=0.8, width=0.8)
    ax2.set_xlabel("Giorno del mese", fontsize=9)
    ax2.set_ylabel("Pioggia (mm)", fontsize=9)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper right", fontsize=7)

    plt.tight_layout()
    st.pyplot(fig)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)

    st.download_button(
        label="📥 Scarica Grafico per Instagram (PNG 4:5)",
        data=buf,
        file_name=f"meteo_{sel_mese_str}_{sel_anno}.png",
        mime="image/png",
    )
    plt.close(fig)

    st.subheader("📋 Tutte le misurazioni del mese")
    st.dataframe(m_data.drop(columns=["Data_dt"], errors="ignore"), use_container_width=True, hide_index=True)

# ==========================================
# 5. DATI MENSILI
# ==========================================
elif menu == "📈 Dati Mensili":
  st.header("Dati Mensili & Grafici con Confronto Storico")

  current_year = datetime.now().year
  temp_df = df.copy()
  temp_df["Anno"] = temp_df["Data_dt"].dt.year
  overall_hist_tmed = temp_df["Temperatura_Media_C"].mean()

  annual_list = []
  for anno, group in temp_df.groupby("Anno"):
    if group.empty:
      continue
    max_idx = group["Temperatura_Max_C"].idxmax()
    max_val = group.loc[max_idx, "Temperatura_Max_C"]
    max_date = str(group.loc[max_idx, "Data"]).split()[0]

    min_idx = group["Temperatura_Min_C"].idxmin()
    min_val = group.loc[min_idx, "Temperatura_Min_C"]
    min_date = str(group.loc[min_idx, "Data"]).split()[0]

    ann_tmed = group["Temperatura_Media_C"].mean()
    rain_sum = group["Pioggia_mm"].sum()

    annual_list.append({
        "Anno": int(anno),
        "Temp Max Assoluta (°C)": f"{max_val:.1f}",
        "Data Max": max_date,
        "Temp Min Assoluta (°C)": f"{min_val:.1f}",
        "Data Min": min_date,
        "Temp Media (°C)": f"{ann_tmed:.1f}",
        "vs Storica (°C)": f"{(ann_tmed - overall_hist_tmed):+.1f}",
        "Pioggia Totale (mm)": f"{rain_sum:.1f}",
    })

  annual_df = pd.DataFrame(annual_list)
  st.markdown(f"💡 **Media storica generale (tutti gli anni):** {overall_hist_tmed:.1f} °C")
  st.dataframe(annual_df, use_container_width=True, hide_index=True)

  if not annual_df.empty:
    st.markdown("---")
    st.subheader("📱 Grafico Annuale Formato Instagram (4:5)")
    anni_disponibili = annual_df["Anno"].tolist()
    default_grafico_idx = anni_disponibili.index(current_year) if current_year in anni_disponibili else (len(anni_disponibili) - 1 if anni_disponibili else 0)

    sel_anno_grafico = st.selectbox("Seleziona Anno per il Grafico", anni_disponibili, index=default_grafico_idx)
    anno_data = temp_df[temp_df["Anno"] == sel_anno_grafico]

    if not anno_data.empty:
      mensile_anno = anno_data.groupby(anno_data["Data_dt"].dt.month).agg({
          "Temperatura_Max_C": "max",
          "Temperatura_Min_C": "min",
          "Temperatura_Media_C": "mean",
          "Pioggia_mm": "sum"
      }).reset_index()

      hist_prev_annuale = temp_df[temp_df["Anno"] < sel_anno_grafico]
      if hist_prev_annuale.empty:
        hist_prev_annuale = temp_df

      hist_monthly_mean = hist_prev_annuale.groupby(hist_prev_annuale["Data_dt"].dt.month)["Temperatura_Media_C"].mean().reset_index()
      hist_monthly_mean.columns = ["Data_dt", "Temp_Media_Storica"]

      mensile_anno = pd.merge(mensile_anno, hist_monthly_mean, on="Data_dt", how="left")

      fig_ann, (ax1_ann, ax2_ann) = plt.subplots(2, 1, figsize=(5.5, 6.8), dpi=180, sharex=True)
      mesi_brevi = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
      x_labels = [mesi_brevi[int(m) - 1] for m in mensile_anno["Data_dt"]]

      ax1_ann.plot(x_labels, mensile_anno["Temperatura_Media_C"], label=f"Media Misurata {sel_anno_grafico} (°C)", color="#2ca02c", marker="s", linewidth=1.8, markersize=4)
      ax1_ann.plot(x_labels, mensile_anno["Temp_Media_Storica"], label="Media Storica (Anni Prec.) (°C)", color="#ff7f0e", marker="o", linewidth=1.8, markersize=4, linestyle="--")
      ax1_ann.set_title(f"Confronto Temperatura Media Mensile & Pioggia\nAnno {sel_anno_grafico}", fontsize=11, fontweight="bold", pad=10)
      ax1_ann.set_ylabel("Temperatura (°C)", fontsize=9)
      ax1_ann.grid(True, linestyle="--", alpha=0.5)
      ax1_ann.legend(loc="upper right", fontsize=7)

      ax2_ann.bar(x_labels, mensile_anno["Pioggia_mm"], label="Pioggia Totale (mm)", color="#1c83e1", alpha=0.8, width=0.6)
      ax2_ann.set_ylabel("Pioggia (mm)", fontsize=9)
      ax2_ann.grid(True, linestyle="--", alpha=0.5)
      ax2_ann.legend(loc="upper right", fontsize=7)

      plt.tight_layout()
      st.pyplot(fig_ann)

      buf_ann = io.BytesIO()
      fig_ann.savefig(buf_ann, format="png", bbox_inches="tight")
      buf_ann.seek(0)

      st.download_button(
          label=f"📥 Scarica Grafico Anno {sel_anno_grafico} per Instagram (PNG 4:5)",
          data=buf_ann,
          file_name=f"meteo_anno_{sel_anno_grafico}.png",
          mime="image/png",
      )
      plt.close(fig_ann)

# ==========================================
# 6. GRAFICI ANNUALI (GLOBALE)
# ==========================================
elif menu == "📊 Grafici Annuali":
  st.header("Grafici Annuali Globali (Temperatura & Pioggia)")
  st.write("Panoramica complessiva di tutti gli anni registrati nel database.")

  temp_df = df.copy()
  temp_df["Anno"] = temp_df["Data_dt"].dt.year

  annuale_globale = temp_df.groupby("Anno").agg({"Temperatura_Media_C": "mean", "Pioggia_mm": "sum"}).reset_index()

  if annuale_globale.empty:
    st.info("Nessun dato disponibile per generare i grafici annuali.")
  else:
    fig_glob, (ax1_g, ax2_g) = plt.subplots(2, 1, figsize=(8, 7), dpi=180, sharex=True)

    ax1_g.plot(annuale_globale["Anno"], annuale_globale["Temperatura_Media_C"], label="Temperatura Media Annua (°C)", color="#2ca02c", marker="o", linewidth=2, markersize=6)
    ax1_g.set_title("Andamento Storico - Temperatura Media Annua & Pioggia Totale", fontsize=12, fontweight="bold", pad=12)
    ax1_g.set_ylabel("Temperatura Media (°C)", fontsize=10)
    ax1_g.grid(True, linestyle="--", alpha=0.5)
    ax1_g.legend(loc="upper right", fontsize=8)

    ax2_g.bar(annuale_globale["Anno"], annuale_globale["Pioggia_mm"], label="Pioggia Totale Annua (mm)", color="#1c83e1", alpha=0.8, width=0.6)
    ax2_g.set_xlabel("Anno", fontsize=10)
    ax2_g.set_ylabel("Pioggia Totale (mm)", fontsize=10)
    ax2_g.grid(True, linestyle="--", alpha=0.5)
    ax2_g.legend(loc="upper right", fontsize=8)
    ax2_g.set_xticks(annuale_globale["Anno"])

    plt.tight_layout()
    st.pyplot(fig_glob)

    buf_glob = io.BytesIO()
    fig_glob.savefig(buf_glob, format="png", bbox_inches="tight")
    buf_glob.seek(0)

    st.download_button(
        label="📥 Scarica Grafico Annuale Globale (PNG)",
        data=buf_glob,
        file_name="meteo_grafico_annuale_globale.png",
        mime="image/png",
    )
    plt.close(fig_glob)

# ==========================================
# 7. INSERISCI MISURA MANUALE (PROTETTO)
# ==========================================
elif menu == "➕ Inserisci Misura":
  st.header("➕ Inserimento Manuale Dati (Area Riservata)")

  if not st.session_state["auth_ok"]:
    pwd = st.text_input("Inserisci la password amministratore per sbloccare questa sezione:", type="password")
    if st.button("Accedi"):
      if pwd == admin_password:
        st.session_state["auth_ok"] = True
        st.rerun()
      else:
        st.error("❌ Password errata.")
    st.stop()

  st.success("🔓 Accesso autorizzato")
  if st.button("🔒 Esci dall'area protetta"):
    st.session_state["auth_ok"] = False
    st.rerun()

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
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS misurazioni (
                        Data TEXT PRIMARY KEY,
                        Temperatura_Min_C REAL,
                        Temperatura_Max_C REAL,
                        Temperatura_Media_C REAL,
                        Umidita_Perc REAL,
                        Pioggia_mm REAL
                    )
                """)
        cursor.execute("""
                    INSERT OR REPLACE INTO misurazioni (Data, Temperatura_Min_C, Temperatura_Max_C, Temperatura_Media_C, Umidita_Perc, Pioggia_mm)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (data_ins.strftime("%Y-%m-%d"), t_min, t_max, t_med, hum, rain))
        conn.commit()
        conn.close()
        st.cache_data.clear()
        st.success("Misura registrata con successo nel database!")
      except Exception as e:
        st.error(f"Errore durante il salvataggio: {e}")

# ==========================================
# 8. IMPORTA / ESPORTA DATI (PROTETTO)
# ==========================================
elif menu == "📁 Importa / Esporta Dati":
  st.header("📁 Gestione File & Backup (Area Riservata)")

  if not st.session_state["auth_ok"]:
    pwd = st.text_input("Inserisci la password amministratore per sbloccare questa sezione:", type="password", key="pwd_import")
    if st.button("Accedi", key="btn_import"):
      if pwd == admin_password:
        st.session_state["auth_ok"] = True
        st.rerun()
      else:
        st.error("❌ Password errata.")
    st.stop()

  st.success("🔓 Accesso autorizzato")
  if st.button("🔒 Esci dall'area protetta", key="btn_out_import"):
    st.session_state["auth_ok"] = False
    st.rerun()

  st.subheader("📥 Importa da file esterno")
  uploaded_file = st.file_uploader("Carica file CSV o Excel", type=["csv", "xlsx", "xls"])
  if uploaded_file is not None:
    try:
      if uploaded_file.name.endswith((".xlsx", ".xls")):
        df_up = pd.read_excel(uploaded_file)
      else:
        df_up = pd.read_csv(uploaded_file)

      conn = sqlite3.connect(DB_NAME)
      df_up.to_sql("misurazioni", conn, if_exists="replace", index=False)
      conn.close()
      st.cache_data.clear()
      st.success("Database aggiornato con successo tramite il file caricato!")
    except Exception as e:
      st.error(f"Errore nell'importazione: {e}")

  st.subheader("📤 Esporta database")
  if not df.empty:
    csv_bytes = df.drop(columns=["Data_dt"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        "Scarica dati in formato CSV",
        data=csv_bytes,
        file_name="export_meteo.csv",
        mime="text/csv",
    )
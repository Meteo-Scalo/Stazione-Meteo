from datetime import datetime
import io
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from PIL import Image
import pandas as pd
import requests
import sqlite3
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# Nome del database SQLite condiviso
DB_NAME = "meteo_database.db"

# URL del file Excel raw su GitHub
URL_GITHUB_FILE = "https://raw.githubusercontent.com/Meteo-Scalo/Stazione-Meteo/main/dati_meteo_esempio.xlsx"

st.set_page_config(
    page_title="Stazione meteo amatoriale di Monterotondo Scalo",
    layout="wide",
    page_icon="🌦️",
)


# Funzione per inizializzare il database
def init_db():
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
  try:
    cursor.execute("ALTER TABLE misurazioni ADD COLUMN Umidita_Perc REAL;")
  except sqlite3.OperationalError:
    pass
  conn.commit()
  conn.close()


init_db()


# Funzione per sincronizzare automaticamente i dati dal file Excel di GitHub all'avvio
def sync_from_github():
  try:
    df_github = pd.read_excel(URL_GITHUB_FILE)
    conn = sqlite3.connect(DB_NAME)
    df_github.to_sql("misurazioni", conn, if_exists="replace", index=False)
    conn.close()
  except Exception:
    pass


sync_from_github()

# Stile CSS personalizzato
st.markdown(
    """
    <style>
    h2, h3, h4 { text-align: center; }
    div[data-testid="stMetric"] { text-align: center; align-items: center; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"], div[data-testid="stMetricDelta"] {
        text-align: center !important;
        justify-content: center !important;
    }
    div[data-testid="stDataFrame"] { display: flex; justify-content: center; }
    </style>
""",
    unsafe_allow_html=True,
)

st_autorefresh(interval=10 * 60 * 1000, key="weather_autorefresh")


# Funzione per connettersi e caricare i dati dal database
@st.cache_data(ttl=30)
def load_data():
  conn = sqlite3.connect(DB_NAME)
  try:
    df = pd.read_sql("SELECT * FROM misurazioni ORDER BY Data ASC", conn)
  except Exception:
    df = pd.DataFrame(columns=[
        "Data",
        "Temperatura_Min_C",
        "Temperatura_Max_C",
        "Temperatura_Media_C",
        "Umidita_Perc",
        "Pioggia_mm",
    ])
  conn.close()
  if not df.empty and "Data" in df.columns:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Data"] = df["Data_dt"].dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["Data_dt"]).sort_values("Data_dt")
  else:
    df["Data_dt"] = pd.to_datetime([], errors="coerce")
  return df


# Funzione per recuperare i dati live dall'endpoint standard 'current'
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
  st.warning(
      f"⚠️ Immagine di intestazione ('{image_filename}') non trovata nella"
      " cartella del repository."
  )

df = load_data()

menu = st.sidebar.radio(
    "Menu Principale",
    [
        "📊 Dashboard",
        "🔍 Consultazione Database",
        "📅 Dati Giornalieri",
        "📈 Dati Mensili",
        "📊 Grafici Annuali",
        "📁 Esporta Dati",
    ],
)

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

if df.empty or "Data_dt" not in df.columns:
  st.warning(
      "Il database è attualmente vuoto o il file Excel su GitHub non contiene"
      " dati validi."
  )
  st.stop()
else:
  if "Data_dt" not in df.columns:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")

# ==========================================
# 1. DASHBOARD
# ==========================================
if menu == "📊 Dashboard":
  is_online = False
  wu_data, err_msg = None, "Credenziali mancanti"
  if wu_station_id and wu_api_key:
    wu_data, err_msg = fetch_wunderground_data(wu_station_id, wu_api_key)
    if wu_data and "observations" in wu_data and len(wu_data["observations"]) > 0:
      is_online = True

  status_badge = "🟢 Online" if is_online else "🔴 Offline"
  st.markdown(
      f"""
        <div style="display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 10px; margin-bottom: 20px;">
            <h2 style="margin: 0; padding: 0;">Condizioni in tempo reale</h2>
            <span style="font-weight: bold; font-size: 16px; white-space: nowrap;">{status_badge}</span>
        </div>
    """,
      unsafe_allow_html=True,
  )

  if is_online:
    try:
      obs = wu_data["observations"][0]
      metric = obs.get("metric", {})

      temp_raw = metric.get("temp")
      heat_raw = metric.get("heatIndex")
      wind_chill_raw = metric.get("windChill")
      feels_raw = (
          heat_raw
          if heat_raw is not None
          else (
              wind_chill_raw if wind_chill_raw is not None else temp_raw
          )
      )

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

      col_l1, col_l2, col_l3, col_l4, col_l5 = st.columns(5)
      with col_l1:
        st.metric(label="🌡️ Temperatura", value=temp_val)
      with col_l2:
        st.metric(label="🌡️ Temp. Avvertita", value=feels_val)
      with col_l3:
        st.metric(
            label="💧 Umidità",
            value=(
                f"{hum_val} %"
                if hum_val != "N.D." and hum_val is not None
                else "N.D."
            ),
        )
      with col_l4:
        st.metric(label="⏱️ Pressione", value=pressure_val)
      with col_l5:
        st.metric(label="☔ Pioggia Odierna", value=f"{rain_val:.1f} mm")

      st.markdown(
          f"<p style='text-align: center; color: gray;'>Ultima rilevazione"
          f" stazione: {obs_time}</p>",
          unsafe_allow_html=True,
      )

    except Exception as e:
      st.warning(f"Errore nell'elaborazione dei dati meteo: {e}")
  else:
    if not wu_station_id or not wu_api_key:
      st.info(
          "💡 Configura le credenziali Weather Underground (`station_id` e"
          " `api_key`) nella sezione [wunderground] dei Secrets di Streamlit."
      )
    else:
      st.error(
          "Impossibile recuperare i dati da Weather Underground. Dettaglio:"
          f" {err_msg}"
      )

  st.markdown("---")
  st.subheader("Estremi Meteo")
  st.markdown(
      "<p style='text-align: center;'>Tabella riepilogativa con le due"
      " temperature massime più alte e le due minime più basse per ogni"
      " mese, inclusi i record assoluti.</p>",
      unsafe_allow_html=True,
  )

  mesi_nomi = {
      1: "Gennaio",
      2: "Febbraio",
      3: "Marzo",
      4: "Aprile",
      5: "Maggio",
      6: "Giugno",
      7: "Luglio",
      8: "Agosto",
      9: "Settembre",
      10: "Ottobre",
      11: "Novembre",
      12: "Dicembre",
  }

  temp_df = df.copy()
  temp_df["Mese_Num"] = temp_df["Data_dt"].dt.month

  table_data = []
  for m_num in range(1, 13):
    m_data = temp_df[temp_df["Mese_Num"] == m_num]
    if not m_data.empty:
      tmax_ser = pd.to_numeric(m_data["Temperatura_Max_C"], errors="coerce")
      tmin_ser = pd.to_numeric(m_data["Temperatura_Min_C"], errors="coerce")

      m_data_clean = m_data.copy()
      m_data_clean["T_Max_Num"] = tmax_ser
      m_data_clean["T_Min_Num"] = tmin_ser

      top2_max = m_data_clean.nlargest(2, "T_Max_Num")
      max_str_list = []
      for _, r in top2_max.iterrows():
        max_str_list.append(
            f"{r['Temperatura_Max_C']} °C ({str(r['Data']).split()[0]})"
        )
      max_str = " | ".join(max_str_list)

      bot2_min = m_data_clean.nsmallest(2, "T_Min_Num")
      min_str_list = []
      for _, r in bot2_min.iterrows():
        min_str_list.append(
            f"{r['Temperatura_Min_C']} °C ({str(r['Data']).split()[0]})"
        )
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
            "Top 2 Temp Max": st.column_config.TextColumn(
                "🔥 Top 2 Temperature Massime (Valore e Data)", width="large"
            ),
            "Top 2 Temp Min": st.column_config.TextColumn(
                "❄️ Top 2 Temperature Minime (Valore e Data)", width="large"
            ),
        },
    )

  if not temp_df.empty:
    temp_df["T_Max_Num"] = pd.to_numeric(
        temp_df["Temperatura_Max_C"], errors="coerce"
    )
    temp_df["T_Min_Num"] = pd.to_numeric(
        temp_df["Temperatura_Min_C"], errors="coerce"
    )

    abs_max_idx = temp_df["T_Max_Num"].idxmax()
    abs_max_val = temp_df.loc[abs_max_idx, "Temperatura_Max_C"]
    abs_max_date = str(temp_df.loc[abs_max_idx, "Data"]).split()[0]

    abs_min_idx = temp_df["T_Min_Num"].idxmin()
    abs_min_val = temp_df.loc[abs_min_idx, "Temperatura_Min_C"]
    abs_min_date = str(temp_df.loc[abs_min_idx, "Data"]).split()[0]

    st.markdown("### 🌟 Record Assoluti Generali")
    col_a, col_b = st.columns(2)
    col_a.metric(
        "Temperatura Max Assoluta", f"{abs_max_val} °C", f"Data: {abs_max_date}"
    )
    col_b.metric(
        "Temperatura Min Assoluta", f"{abs_min_val} °C", f"Data: {abs_min_date}"
    )

# ==========================================
# 2. CONSULTAZIONE DATABASE
# ==========================================
elif menu == "🔍 Consultazione Database":
  st.header("Consultazione Database (Intervallo Date)")

  if df.empty:
    st.info("Il database è attualmente vuoto.")
  else:
    min_d = df["Data_dt"].min().date()
    max_d = df["Data_dt"].max().date()

    col1, col2 = st.columns(2)
    start_date = col1.date_input(
        "Data Inizio", min_d, min_value=min_d, max_value=max_d
    )
    end_date = col2.date_input(
        "Data Fine", max_d, min_value=min_d, max_value=max_d
    )

    filtered_df = df[
        (df["Data_dt"].dt.date >= start_date)
        & (df["Data_dt"].dt.date <= end_date)
    ]
    st.dataframe(
        filtered_df.drop(
            columns=["Data_dt", "T_Max_Num", "T_Min_Num"], errors="ignore"
        ),
        use_container_width=True,
        hide_index=True,
    )

# ==========================================
# 3. DATI GIORNALIERI
# ==========================================
elif menu == "📅 Dati Giornalieri":
  st.header("Dati Giornalieri & Grafico con Confronto Storico")

  current_year = datetime.now().year
  current_month = datetime.now().month

  col1, col2 = st.columns(2)
  anni_disp = sorted(df["Data_dt"].dt.year.dropna().unique())

  default_anno_idx = (
      anni_disp.index(current_year)
      if current_year in anni_disp
      else (len(anni_disp) - 1 if anni_disp else 0)
  )
  sel_anno = (
      col1.selectbox("Seleziona Anno", anni_disp, index=default_anno_idx)
      if anni_disp
      else current_year
  )

  mesi_dict = {
      "Gennaio": 1,
      "Febbraio": 2,
      "Marzo": 3,
      "Aprile": 4,
      "Maggio": 5,
      "Giugno": 6,
      "Luglio": 7,
      "Agosto": 8,
      "Settembre": 9,
      "Ottobre": 10,
      "Novembre": 11,
      "Dicembre": 12,
  }
  mesi_list = list(mesi_dict.keys())
  default_mese_name = [k for k, v in mesi_dict.items() if v == current_month][0]
  default_mese_idx = (
      mesi_list.index(default_mese_name) if default_mese_name in mesi_list else 0
  )

  sel_mese_str = col2.selectbox(
      "Seleziona Mese", mesi_list, index=default_mese_idx
  )
  sel_mese_num = mesi_dict[sel_mese_str]

  m_data = df[
      (df["Data_dt"].dt.year == sel_anno)
      & (df["Data_dt"].dt.month == sel_mese_num)
  ]

  if m_data.empty:
    st.info("Nessun dato trovato per il mese e anno selezionati.")
  else:
    st.subheader(f"📊 Riepilogo Estremi - {sel_mese_str} {sel_anno}")

    tmax_max = pd.to_numeric(m_data["Temperatura_Max_C"], errors="coerce").max()
    tmin_min = pd.to_numeric(m_data["Temperatura_Min_C"], errors="coerce").min()
    tmed_mean = pd.to_numeric(
        m_data["Temperatura_Media_C"], errors="coerce"
    ).mean()
    rain_sum = pd.to_numeric(m_data["Pioggia_mm"], errors="coerce").sum()

    hist_mese_data = df[df["Data_dt"].dt.month == sel_mese_num]
    hist_tmed_mean = pd.to_numeric(
        hist_mese_data["Temperatura_Media_C"], errors="coerce"
    ).mean()
    delta_tmed = (
        tmed_mean - hist_tmed_mean
        if not pd.isna(hist_tmed_mean) and not pd.isna(tmed_mean)
        else 0.0
    )

    hist_rain_df = df[df["Data_dt"].dt.month == sel_mese_num].copy()
    hist_rain_df["Anno_Val"] = hist_rain_df["Data_dt"].dt.year
    hist_rain_df["Rain_Num"] = pd.to_numeric(
        hist_rain_df["Pioggia_mm"], errors="coerce"
    ).fillna(0)
    yearly_rain_sums = hist_rain_df.groupby("Anno_Val")["Rain_Num"].sum()
    hist_rain_mean = (
        yearly_rain_sums.mean() if not yearly_rain_sums.empty else 0.0
    )
    delta_rain = (
        rain_sum - hist_rain_mean
        if not pd.isna(rain_sum) and not pd.isna(hist_rain_mean)
        else 0.0
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Temp Max Assoluta",
        f"{tmax_max:.1f} °C" if not pd.isna(tmax_max) else "N.D.",
    )
    c2.metric(
        "Temp Min Assoluta",
        f"{tmin_min:.1f} °C" if not pd.isna(tmin_min) else "N.D.",
    )
    c3.metric(
        "Temp Media Mese",
        f"{tmed_mean:.1f} °C" if not pd.isna(tmed_mean) else "N.D.",
        delta=(
            f"{delta_tmed:+.1f} °C vs storica"
            if not pd.isna(tmed_mean)
            else None
        ),
        delta_color="inverse",
    )
    c4.metric(
        "Pioggia Totale",
        f"{rain_sum:.1f} mm" if not pd.isna(rain_sum) else "0.0 mm",
        delta=(
            f"{delta_rain:+.1f} mm vs storica"
            if not pd.isna(rain_sum) and not pd.isna(hist_rain_mean)
            else None
        ),
    )

    if not pd.isna(hist_tmed_mean):
      st.markdown(
          f"<p style='text-align: center; color: gray;'>💡 Media storica di {sel_mese_str} calcolata sul totale degli anni: {hist_tmed_mean:.1f} °C | Pioggia media storica: {hist_rain_mean:.1f} mm</p>",
          unsafe_allow_html=True,
      )

    st.markdown("---")

    st.markdown(
        "<p style='text-align: center;'><b>Confronto tra la temperatura"
        " media misurata e la media storica, insieme all'andamento dell'accumulo"
        " di pioggia (corrente vs storico).</b></p>",
        unsafe_allow_html=True,
    )

    hist_prev = df[
        (df["Data_dt"].dt.month == sel_mese_num)
        & (df["Data_dt"].dt.year < sel_anno)
    ]
    if hist_prev.empty:
      hist_prev = hist_mese_data

    hist_prev["T_Med_Num"] = pd.to_numeric(
        hist_prev["Temperatura_Media_C"], errors="coerce"
    )
    hist_daily_mean = (
        hist_prev.groupby(hist_prev["Data_dt"].dt.day)["T_Med_Num"]
        .mean()
        .reset_index()
    )
    hist_daily_mean.columns = ["Giorno", "Temp_Media_Storica"]

    hist_prev["Rain_Num"] = pd.to_numeric(
        hist_prev["Pioggia_mm"], errors="coerce"
    ).fillna(0)
    hist_prev["Anno_Storico"] = hist_prev["Data_dt"].dt.year
    hist_prev["Giorno_Mese"] = hist_prev["Data_dt"].dt.day

    cum_rain_list = []
    for y, group in hist_prev.groupby("Anno_Storico"):
      g_sorted = group.sort_values("Giorno_Mese")
      g_sorted["Cum_Rain"] = g_sorted["Rain_Num"].cumsum()
      cum_rain_list.append(
          g_sorted[["Giorno_Mese", "Cum_Rain"]].rename(
              columns={"Giorno_Mese": "Giorno"}
          )
      )

    if cum_rain_list:
      all_hist_cum = pd.concat(cum_rain_list)
      hist_cum_mean = (
          all_hist_cum.groupby("Giorno")["Cum_Rain"].mean().reset_index()
      )
      hist_cum_mean.columns = ["Giorno", "Pioggia_Cumulata_Storica"]
    else:
      hist_cum_mean = pd.DataFrame(
          {"Giorno": range(1, 32), "Pioggia_Cumulata_Storica": 0}
      )

    m_data_plot = m_data.copy()
    m_data_plot["Giorno"] = m_data_plot["Data_dt"].dt.day
    m_data_plot["T_Med_Num"] = pd.to_numeric(
        m_data_plot["Temperatura_Media_C"], errors="coerce"
    )
    m_data_plot["Rain_Num"] = pd.to_numeric(
        m_data_plot["Pioggia_mm"], errors="coerce"
    ).fillna(0)
    m_data_plot["Pioggia_Cumulata_Corrente"] = m_data_plot["Rain_Num"].cumsum()

    m_data_plot = pd.merge(
        m_data_plot, hist_daily_mean, on="Giorno", how="left"
    )
    m_data_plot = pd.merge(
        m_data_plot, hist_cum_mean, on="Giorno", how="left"
    )

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(5.5, 6.8), dpi=180, sharex=True
    )

    ax1.plot(
        m_data_plot["Giorno"],
        m_data_plot["T_Med_Num"],
        label=f"Media Misurata {sel_anno} (°C)",
        color="#2ca02c",
        linewidth=1.8,
        marker="o",
        markersize=3,
    )
    ax1.plot(
        m_data_plot["Giorno"],
        m_data_plot["Temp_Media_Storica"],
        label="Media Storica (Anni Prec.) (°C)",
        color="#ff7f0e",
        linewidth=1.8,
        linestyle="--",
    )
    ax1.set_title(
        f"Confronto Temperatura & Accumulo Pioggia\n{sel_mese_str} {sel_anno}",
        fontsize=11,
        fontweight="bold",
        pad=10,
    )
    ax1.set_ylabel("Temperatura (°C)", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="upper right", fontsize=7)

    ax2.plot(
        m_data_plot["Giorno"],
        m_data_plot["Pioggia_Cumulata_Corrente"],
        label=f"Accumulo {sel_anno} (mm)",
        color="#1c83e1",
        linewidth=1.8,
        marker="o",
        markersize=3,
    )
    ax2.plot(
        m_data_plot["Giorno"],
        m_data_plot["Pioggia_Cumulata_Storica"],
        label="Accumulo Medio Storico (mm)",
        color="#d62728",
        linewidth=1.8,
        linestyle="--",
    )
    ax2.set_xlabel("Giorno del mese", fontsize=9)
    ax2.set_ylabel("Pioggia Cumulata (mm)", fontsize=9)
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", fontsize=7)

    # Forza l'asse X a mostrare solo numeri interi (giorni)
    ax2.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

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
    st.dataframe(
        m_data.drop(
            columns=["Data_dt", "T_Max_Num", "T_Min_Num"], errors="ignore"
        ),
        use_container_width=True,
        hide_index=True,
    )

# ==========================================
# 4. DATI MENSILI
# ==========================================
elif menu == "📈 Dati Mensili":
  st.header("Dati Mensili & Grafici con Confronto Storico")

  current_year = datetime.now().year
  temp_df = df.copy()
  temp_df["Anno"] = temp_df["Data_dt"].dt.year
  temp_df["T_Med_Num"] = pd.to_numeric(
      temp_df["Temperatura_Media_C"], errors="coerce"
  )
  overall_hist_tmed = temp_df["T_Med_Num"].mean()

  annual_list = []
  for anno, group in temp_df.groupby("Anno"):
    if group.empty:
      continue

    g_max = pd.to_numeric(group["Temperatura_Max_C"], errors="coerce")
    g_min = pd.to_numeric(group["Temperatura_Min_C"], errors="coerce")
    g_med = pd.to_numeric(group["Temperatura_Media_C"], errors="coerce")
    g_rain = pd.to_numeric(group["Pioggia_mm"], errors="coerce")

    max_idx = g_max.idxmax() if not g_max.dropna().empty else None
    max_val = (
        group.loc[max_idx, "Temperatura_Max_C"]
        if max_idx is not None
        else "N.D."
    )
    max_date = (
        str(group.loc[max_idx, "Data"]).split()[0]
        if max_idx is not None
        else ""
    )

    min_idx = g_min.idxmin() if not g_min.dropna().empty else None
    min_val = (
        group.loc[min_idx, "Temperatura_Min_C"]
        if min_idx is not None
        else "N.D."
    )
    min_date = (
        str(group.loc[min_idx, "Data"]).split()[0]
        if min_idx is not None
        else ""
    )

    ann_tmed = g_med.mean()
    rain_sum = g_rain.sum()

    annual_list.append({
        "Anno": int(anno),
        "Temp Max Assoluta (°C)": str(max_val),
        "Data Max": max_date,
        "Temp Min Assoluta (°C)": str(min_val),
        "Data Min": min_date,
        "Temp Media (°C)": (
            f"{ann_tmed:.1f}" if not pd.isna(ann_tmed) else "N.D."
        ),
        "vs Storica (°C)": (
            f"{(ann_tmed - overall_hist_tmed):+.1f}"
            if not pd.isna(ann_tmed) and not pd.isna(overall_hist_tmed)
            else "0.0"
        ),
        "Pioggia Totale (mm)": (
            f"{rain_sum:.1f}" if not pd.isna(rain_sum) else "0.0"
        ),
    })

  annual_df = pd.DataFrame(annual_list)
  if not pd.isna(overall_hist_tmed):
    st.markdown(
        f"<p style='text-align: center;'>💡 <b>Media storica generale (tutti gli anni):</b> {overall_hist_tmed:.1f} °C</p>",
        unsafe_allow_html=True,
    )
  st.dataframe(annual_df, use_container_width=True, hide_index=True)

  if not annual_df.empty:
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center;'><b>Confronto tra la temperatura"
        " media mensile misurata nell'anno selezionato e la media storica,"
        " insieme al totale delle piogge mensili e alla media storica.</b></p>",
        unsafe_allow_html=True,
    )

    anni_disponibili = annual_df["Anno"].tolist()
    default_grafico_idx = (
        anni_disponibili.index(current_year)
        if current_year in anni_disponibili
        else (len(anni_disponibili) - 1 if anni_disponibili else 0)
    )

    sel_anno_grafico = st.selectbox(
        "Seleziona Anno per il Grafico",
        anni_disponibili,
        index=default_grafico_idx,
    )
    anno_data = temp_df[temp_df["Anno"] == sel_anno_grafico]

    if not anno_data.empty:
      anno_data_clean = anno_data.copy()
      anno_data_clean["T_Max_Num"] = pd.to_numeric(
          anno_data_clean["Temperatura_Max_C"], errors="coerce"
      )
      anno_data_clean["T_Min_Num"] = pd.to_numeric(
          anno_data_clean["Temperatura_Min_C"], errors="coerce"
      )
      anno_data_clean["T_Med_Num"] = pd.to_numeric(
          anno_data_clean["Temperatura_Media_C"], errors="coerce"
      )
      anno_data_clean["Rain_Num"] = pd.to_numeric(
          anno_data_clean["Pioggia_mm"], errors="coerce"
      )

      mensile_anno = (
          anno_data_clean.groupby(anno_data_clean["Data_dt"].dt.month)
          .agg({
              "T_Max_Num": "max",
              "T_Min_Num": "min",
              "T_Med_Num": "mean",
              "Rain_Num": "sum",
          })
          .reset_index()
      )

      hist_prev_annuale = temp_df[temp_df["Anno"] < sel_anno_grafico]
      if hist_prev_annuale.empty:
        hist_prev_annuale = temp_df

      hist_monthly_mean = (
          hist_prev_annuale.groupby(hist_prev_annuale["Data_dt"].dt.month)[
              "T_Med_Num"
          ]
          .mean()
          .reset_index()
      )
      hist_monthly_mean.columns = ["Data_dt", "Temp_Media_Storica"]

      hist_prev_annuale_rain = hist_prev_annuale.copy()
      hist_prev_annuale_rain["Rain_Num"] = pd.to_numeric(
          hist_prev_annuale_rain["Pioggia_mm"], errors="coerce"
      ).fillna(0)
      hist_prev_annuale_rain["Mese"] = hist_prev_annuale_rain["Data_dt"].dt.month
      hist_prev_annuale_rain["Anno_Val"] = hist_prev_annuale_rain[
          "Data_dt"
      ].dt.year

      monthly_by_year = (
          hist_prev_annuale_rain.groupby(["Anno_Val", "Mese"])["Rain_Num"]
          .sum()
          .reset_index()
      )
      hist_monthly_rain = (
          monthly_by_year.groupby("Mese")["Rain_Num"].mean().reset_index()
      )
      hist_monthly_rain.columns = ["Data_dt", "Pioggia_Media_Storica"]

      mensile_anno = pd.merge(
          mensile_anno, hist_monthly_mean, on="Data_dt", how="left"
      )
      mensile_anno = pd.merge(
          mensile_anno, hist_monthly_rain, on="Data_dt", how="left"
      )

      fig_ann, (ax1_ann, ax2_ann) = plt.subplots(
          2, 1, figsize=(5.5, 6.8), dpi=180, sharex=True
      )
      mesi_brevi = [
          "Gen",
          "Feb",
          "Mar",
          "Apr",
          "Mag",
          "Giu",
          "Lug",
          "Ago",
          "Set",
          "Ott",
          "Nov",
          "Dic",
      ]
      x_labels = [mesi_brevi[int(m) - 1] for m in mensile_anno["Data_dt"]]
      x = np.arange(len(x_labels))

      ax1_ann.plot(
          x,
          mensile_anno["T_Med_Num"],
          label=f"Media Misurata {sel_anno_grafico} (°C)",
          color="#2ca02c",
          marker="s",
          linewidth=1.8,
          markersize=4,
      )
      ax1_ann.plot(
          x,
          mensile_anno["Temp_Media_Storica"],
          label="Media Storica (Anni Prec.) (°C)",
          color="#ff7f0e",
          marker="o",
          linewidth=1.8,
          markersize=4,
          linestyle="--",
      )
      ax1_ann.set_title(
          f"Confronto Temperatura Media Mensile & Pioggia\nAnno {sel_anno_grafico}",
          fontsize=11,
          fontweight="bold",
          pad=10,
      )
      ax1_ann.set_ylabel("Temperatura (°C)", fontsize=9)
      ax1_ann.grid(True, linestyle="--", alpha=0.5)
      ax1_ann.legend(loc="upper right", fontsize=7)

      width = 0.35
      ax2_ann.bar(
          x - width / 2,
          mensile_anno["Rain_Num"],
          width,
          label=f"Pioggia {sel_anno_grafico} (mm)",
          color="#1c83e1",
          alpha=0.8,
      )
      ax2_ann.bar(
          x + width / 2,
          mensile_anno["Pioggia_Media_Storica"],
          width,
          label="Media Storica (mm)",
          color="#d62728",
          alpha=0.8,
      )
      ax2_ann.set_ylabel("Pioggia (mm)", fontsize=9)
      ax2_ann.grid(True, linestyle="--", alpha=0.5)
      ax2_ann.legend(loc="upper right", fontsize=7)
      ax2_ann.set_xticks(x)
      ax2_ann.set_xticklabels(x_labels)

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
# 5. GRAFICI ANNUALI (GLOBALE)
# ==========================================
elif menu == "📊 Grafici Annuali":
  st.header("Grafici Annuali Globali (Temperatura & Pioggia)")
  st.write(
      "Panoramica complessiva di tutti gli anni registrati nel database:"
      " temperatura media annua e pioggia totale annua, senza alcuna"
      " selezione richiesta."
  )

  temp_df = df.copy()
  temp_df["Anno"] = temp_df["Data_dt"].dt.year
  temp_df["T_Med_Num"] = pd.to_numeric(
      temp_df["Temperatura_Media_C"], errors="coerce"
  )
  temp_df["Rain_Num"] = pd.to_numeric(temp_df["Pioggia_mm"], errors="coerce")

  annuale_globale = (
      temp_df.groupby("Anno")
      .agg({"T_Med_Num": "mean", "Rain_Num": "sum"})
      .reset_index()
  )

  if annuale_globale.empty:
    st.info("Nessun dato disponibile per generare i grafici annuali.")
  else:
    fig_glob, (ax1_g, ax2_g) = plt.subplots(
        2, 1, figsize=(8, 7), dpi=180, sharex=True
    )

    ax1_g.plot(
        annuale_globale["Anno"],
        annuale_globale["T_Med_Num"],
        label="Temperatura Media Annua (°C)",
        color="#2ca02c",
        marker="o",
        linewidth=2,
        markersize=6,
    )
    ax1_g.set_title(
        "Andamento Storico - Temperatura Media Annua & Pioggia Totale",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    ax1_g.set_ylabel("Temperatura Media (°C)", fontsize=10)
    ax1_g.grid(True, linestyle="--", alpha=0.5)
    ax1_g.legend(loc="upper right", fontsize=8)

    ax2_g.bar(
        annuale_globale["Anno"],
        annuale_globale["Rain_Num"],
        label="Pioggia Totale Annua (mm)",
        color="#1c83e1",
        alpha=0.8,
        width=0.6,
    )
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
        mime="application/octet-stream",
    )
    plt.close(fig_glob)

# ==========================================
# 6. ESPORTA DATI (PROTETTO)
# ==========================================
elif menu == "📁 Esporta Dati":
  st.header("📁 Esporta Dati & Backup (Area Riservata)")

  if not st.session_state["auth_ok"]:
    pwd = st.text_input(
        "Inserisci la password amministratore per sbloccare questa sezione:",
        type="password",
        key="pwd_import",
    )
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

  st.subheader("📤 Esporta database")
  col_exp1, col_exp2 = st.columns(2)

  with col_exp1:
    if not df.empty:
      csv_bytes = (
          df.drop(
              columns=["Data_dt", "T_Max_Num", "T_Min_Num"], errors="ignore"
          )
          .to_csv(index=False)
          .encode("utf-8")
      )
      st.download_button(
          "📥 Scarica dati in CSV",
          data=csv_bytes,
          file_name="export_meteo.csv",
          mime="text/csv",
      )

  with col_exp2:
    if os.path.exists(DB_NAME):
      with open(DB_NAME, "rb") as f:
        db_bytes = f.read()
      st.download_button(
          "📥 Scarica Database (.db)",
          data=db_bytes,
          file_name="meteo_database.db",
          mime="application/octet-stream",
      )
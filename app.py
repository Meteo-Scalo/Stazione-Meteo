from datetime import datetime
import io
import matplotlib.pyplot as plt
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

# Configura il refresh automatico ogni 10 minuti (10 min * 60 sec * 1000 ms)
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
        "Umidita_%",
        "Pioggia_mm",
    ])
  conn.close()
  if not df.empty:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")
  return df


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


st.title("🌦️ Stazione meteo amatoriale di Monterotondo Scalo")

df = load_data()

# Menu laterale con le etichette aggiornate
menu = st.sidebar.radio(
    "Menu Principale",
    [
        "📊 Dashboard & Record Mensili",
        "🔍 Consultazione Database",
        "📅 Dati Giornalieri",
        "📈 Dati Mensili",
        "➕ Inserisci Misura",
        "📁 Importa / Esporta Dati",
    ],
)

# Lettura sicura delle credenziali Weather Underground dai Secrets di Streamlit
try:
  wu_station_id = str(st.secrets["wunderground"]["station_id"])
  wu_api_key = str(st.secrets["wunderground"]["api_key"])
except Exception:
  wu_station_id = ""
  wu_api_key = ""

if df.empty:
  st.warning(
      "Il database è attualmente vuoto. Utilizza la sezione 'Importa / Esporta"
      " Dati' o 'Inserisci Misura' per popolare le misurazioni."
  )
else:
  if "Data_dt" not in df.columns:
    df["Data_dt"] = pd.to_datetime(df["Data"], errors="coerce")

# ==========================================
# 1. DASHBOARD & RECORD MENSILI E ASSOLUTI
# ==========================================
if menu == "📊 Dashboard & Record Mensili":
  st.header("Dashboard: Condizioni Live e Record Mensili")

  # Sezione Dati Live Weather Underground
  st.markdown("### 🔴 Dati in Tempo Reale (Weather Underground)")

  if wu_station_id and wu_api_key:
    wu_data, err_msg = fetch_wunderground_data(wu_station_id, wu_api_key)
    if (
        wu_data
        and "observations" in wu_data
        and len(wu_data["observations"]) > 0
    ):
      try:
        obs = wu_data["observations"][0]
        metric = obs.get("metric", {})

        temp_raw = metric.get("temp")
        hum_val = obs.get("humidity", "N.D.")
        pressure_raw = metric.get("pressure", "N.D.")
        rain_val = obs.get("precipTotal", 0.0)
        obs_time = obs.get("obsTimeLocal", "Aggiornato di recente")

        # Conversione e formattazione sicura della temperatura con 1 decimale
        try:
          temp_val = f"{float(temp_raw):.1f} °C"
        except (ValueError, TypeError):
          temp_val = "N.D."

        # Conversione e formattazione sicura della pressione con 1 decimale
        try:
          pressure_val = f"{float(pressure_raw):.1f} hPa"
        except (ValueError, TypeError):
          pressure_val = "N.D."

        # Layout a 5 colonne: Temperatura, Umidità, Pressione, Pioggia, Stato
        col_l1, col_l2, col_l3, col_l4, col_l5 = st.columns(5)

        with col_l1:
          st.metric(label="🌡️ Temperatura", value=temp_val)
        with col_l2:
          st.metric(
              label="💧 Umidità",
              value=(
                  f"{hum_val} %"
                  if hum_val != "N.D." and hum_val is not None
                  else "N.D."
              ),
          )
        with col_l3:
          st.metric(label="⏱️ Pressione", value=pressure_val)
        with col_l4:
          st.metric(label="☔ Pioggia Odierna", value=f"{rain_val:.1f} mm")
        with col_l5:
          st.metric(label="🟢 Stato", value="Online")

        st.caption(f"Ultima rilevazione stazione: {obs_time}")

      except Exception as e:
        st.warning(f"Errore nell'elaborazione dei dati meteo: {e}")
    else:
      st.error(
          "Impossibile recuperare i dati da Weather Underground. Dettaglio:"
          f" {err_msg}"
      )
  else:
    st.info(
        "💡 Configura le credenziali Weather Underground (`station_id` e"
        " `api_key`) nella sezione [wunderground] dei Secrets di Streamlit."
    )

  st.markdown("---")
  st.write(
      "Tabella riepilogativa con le due temperature massime più alte e le due"
      " minime più basse per ogni mese, inclusi i record assoluti."
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
      top2_max = m_data.nlargest(2, "Temperatura_Max_C")
      max_str_list = []
      for _, r in top2_max.iterrows():
        max_str_list.append(
            f"{r['Temperatura_Max_C']:.1f} °C ({str(r['Data']).split()[0]})"
        )
      max_str = " | ".join(max_str_list)

      bot2_min = m_data.nsmallest(2, "Temperatura_Min_C")
      min_str_list = []
      for _, r in bot2_min.iterrows():
        min_str_list.append(
            f"{r['Temperatura_Min_C']:.1f} °C ({str(r['Data']).split()[0]})"
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

  # Riga record assoluti
  if not temp_df.empty:
    abs_max_idx = temp_df["Temperatura_Max_C"].idxmax()
    abs_max_val = temp_df.loc[abs_max_idx, "Temperatura_Max_C"]
    abs_max_date = str(temp_df.loc[abs_max_idx, "Data"]).split()[0]

    abs_min_idx = temp_df["Temperatura_Min_C"].idxmin()
    abs_min_val = temp_df.loc[abs_min_idx, "Temperatura_Min_C"]
    abs_min_date = str(temp_df.loc[abs_min_idx, "Data"]).split()[0]

    st.markdown("### 🌟 Record Assoluti Generali")
    col_a, col_b = st.columns(2)
    col_a.metric(
        "Temperatura Max Assoluta",
        f"{abs_max_val:.1f} °C",
        f"Data: {abs_max_date}",
    )
    col_b.metric(
        "Temperatura Min Assoluta",
        f"{abs_min_val:.1f} °C",
        f"Data: {abs_min_date}",
    )

# ==========================================
# 2. CONSULTAZIONE DATABASE
# ==========================================
elif menu == "🔍 Consultazione Database":
  st.header("Consultazione Database (Intervallo Date)")

  min_d = df["Data_dt"].min().date()
  max_d = df["Data_dt"].max().date()

  col1, col2 = st.columns(2)
  start_date = col1.date_input("Data Inizio", min_d)
  end_date = col2.date_input("Data Fine", max_d)

  filtered_df = df[
      (df["Data_dt"].dt.date >= start_date)
      & (df["Data_dt"].dt.date <= end_date)
  ]
  st.dataframe(
      filtered_df.drop(columns=["Data_dt"], errors="ignore"),
      use_container_width=True,
      hide_index=True,
  )

# ==========================================
# 3. DATI GIORNALIERI
# ==========================================
elif menu == "📅 Dati Giornalieri":
  st.header("Dati Giornalieri & Grafico con Confronto Storico")

  col1, col2 = st.columns(2)
  anni_disp = sorted(df["Data_dt"].dt.year.dropna().unique())
  sel_anno = (
      col1.selectbox("Seleziona Anno", anni_disp)
      if anni_disp
      else datetime.now().year
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
  sel_mese_str = col2.selectbox("Seleziona Mese", list(mesi_dict.keys()))
  sel_mese_num = mesi_dict[sel_mese_str]

  m_data = df[
      (df["Data_dt"].dt.year == sel_anno)
      & (df["Data_dt"].dt.month == sel_mese_num)
  ]

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
    c3.metric(
        "Temp Media Mese",
        f"{tmed_mean:.1f} °C",
        delta=f"{delta_tmed:+.1f} °C vs storica",
        delta_color="inverse",
    )
    c4.metric("Pioggia Totale", f"{rain_sum:.1f} mm")

    st.caption(
        f"💡 Media storica di {sel_mese_str} calcolata sul totale degli anni:"
        f" {hist_tmed_mean:.1f} °C"
    )

    st.markdown("---")
    st.subheader("📱 Grafico Formato Instagram (4:5)")
    st.write(
        "Confronto tra la temperatura media misurata e la media storica"
        " giornaliera registrata negli anni precedenti nello stesso periodo."
    )

    hist_prev = df[
        (df["Data_dt"].dt.month == sel_mese_num)
        & (df["Data_dt"].dt.year < sel_anno)
    ]
    if hist_prev.empty:
      hist_prev = hist_mese_data

    hist_daily_mean = (
        hist_prev.groupby(hist_prev["Data_dt"].dt.day)["Temperatura_Media_C"]
        .mean()
        .reset_index()
    )
    hist_daily_mean.columns = ["Giorno", "Temp_Media_Storica"]

    m_data_plot = m_data.copy()
    m_data_plot["Giorno"] = m_data_plot["Data_dt"].dt.day
    m_data_plot = pd.merge(
        m_data_plot, hist_daily_mean, on="Giorno", how="left"
    )

    fig, ax = plt.subplots(figsize=(6, 7.5), dpi=200)
    ax.plot(
        m_data_plot["Giorno"],
        m_data_plot["Temperatura_Max_C"],
        label="Temp Max Anno Corrente (°C)",
        color="#ff4b4b",
        linewidth=1.5,
        alpha=0.7,
    )
    ax.plot(
        m_data_plot["Giorno"],
        m_data_plot["Temperatura_Min_C"],
        label="Temp Min Anno Corrente (°C)",
        color="#1c83e1",
        linewidth=1.5,
        alpha=0.7,
    )
    ax.plot(
        m_data_plot["Giorno"],
        m_data_plot["Temperatura_Media_C"],
        label=f"Media Misurata {sel_anno} (°C)",
        color="#2ca02c",
        linewidth=2,
        marker="o",
        markersize=4,
    )
    ax.plot(
        m_data_plot["Giorno"],
        m_data_plot["Temp_Media_Storica"],
        label="Media Storica (Anni Prec.) (°C)",
        color="#ff7f0e",
        linewidth=2,
        linestyle="--",
    )

    ax.set_title(
        f"Confronto Temperatura Media\n{sel_mese_str} {sel_anno} vs Storico",
        fontsize=14,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Giorno del mese", fontsize=10)
    ax.set_ylabel("Temperatura (°C)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper right", fontsize=8)

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
        m_data.drop(columns=["Data_dt"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

# ==========================================
# 4. DATI MENSILI
# ==========================================
elif menu == "📈 Dati Mensili":
  st.header("Dati Mensili & Grafici Social con Confronto Storico")

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
  st.markdown(
      f"💡 **Media storica generale (tutti gli anni):**"
      f" {overall_hist_tmed:.1f} °C"
  )
  st.dataframe(annual_df, use_container_width=True, hide_index=True)

  if not annual_df.empty:
    st.markdown("---")
    st.subheader("📱 Grafico Annuale Formato Instagram (4:5)")
    st.write(
        "Confronto tra la temperatura media mensile misurata nell'anno"
        " selezionato e la media storica mensile degli anni precedenti."
    )

    sel_anno_grafico = st.selectbox(
        "Seleziona Anno per il Grafico Social", annual_df["Anno"].tolist()
    )
    anno_data = temp_df[temp_df["Anno"] == sel_anno_grafico]

    if not anno_data.empty:
      mensile_anno = (
          anno_data.groupby(anno_data["Data_dt"].dt.month)
          .agg({
              "Temperatura_Max_C": "max",
              "Temperatura_Min_C": "min",
              "Temperatura_Media_C": "mean",
              "Pioggia_mm": "sum",
          })
          .reset_index()
      )

      # Calcolo media storica mensile per gli anni precedenti (o fallback su tutti)
      hist_prev_annuale = temp_df[temp_df["Anno"] < sel_anno_grafico]
      if hist_prev_annuale.empty:
        hist_prev_annuale = temp_df

      hist_monthly_mean = (
          hist_prev_annuale.groupby(hist_prev_annuale["Data_dt"].dt.month)[
              "Temperatura_Media_C"
          ]
          .mean()
          .reset_index()
      )
      hist_monthly_mean.columns = ["Data_dt", "Temp_Media_Storica"]

      mensile_anno = pd.merge(
          mensile_anno, hist_monthly_mean, on="Data_dt", how="left"
      )

      # Grafico verticale 4:5 con confronto storico
      fig_ann, ax_ann = plt.subplots(figsize=(6, 7.5), dpi=200)
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

      ax_ann.plot(
          x_labels,
          mensile_anno["Temperatura_Max_C"],
          label="Max Assoluta Anno Corrente (°C)",
          color="#ff4b4b",
          linewidth=1.5,
          alpha=0.7,
      )
      ax_ann.plot(
          x_labels,
          mensile_anno["Temperatura_Min_C"],
          label="Min Assoluta Anno Corrente (°C)",
          color="#1c83e1",
          linewidth=1.5,
          alpha=0.7,
      )
      ax_ann.plot(
          x_labels,
          mensile_anno["Temperatura_Media_C"],
          label=f"Media Misurata {sel_anno_grafico} (°C)",
          color="#2ca02c",
          marker="s",
          linewidth=2,
      )
      ax_ann.plot(
          x_labels,
          mensile_anno["Temp_Media_Storica"],
          label="Media Storica (Anni Prec.) (°C)",
          color="#ff7f0e",
          marker="o",
          linewidth=2,
          linestyle="--",
      )

      ax_ann.set_title(
          f"Confronto Temperatura Media Mensile\nAnno {sel_anno_grafico} vs Storico",
          fontsize=14,
          fontweight="bold",
          pad=15,
      )
      ax_ann.set_ylabel("Temperatura (°C)", fontsize=10)
      ax_ann.grid(True, linestyle="--", alpha=0.5)
      ax_ann.legend(loc="upper right", fontsize=8)

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
# 5. INSERISCI MISURA MANUALE
# ==========================================
elif menu == "➕ Inserisci Misura":
  st.header("Inserimento Manuale Dati nel Database")
  with st.form("form_inserimento"):
    col1, col2 = st.columns(2)
    with col1:
      data_ins = st.date_input("Data", datetime.today())
      t_min = st.number_input(
          "Temperatura Min (°C)", value=15.0, format="%.1f"
      )
      t_max = st.number_input(
          "Temperatura Max (°C)", value=25.0, format="%.1f"
      )
    with col2:
      t_med = st.number_input(
          "Temperatura Media (°C)", value=20.0, format="%.1f"
      )
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
        cursor.execute(
            """
                    INSERT OR REPLACE INTO misurazioni (Data, Temperatura_Min_C, Temperatura_Max_C, Temperatura_Media_C, Umidita_Perc, Pioggia_mm)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
            (
                data_ins.strftime("%Y-%m-%d"),
                t_min,
                t_max,
                t_med,
                hum,
                rain,
            ),
        )
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
  uploaded_file = st.file_uploader(
      "Carica file CSV o Excel", type=["csv", "xlsx", "xls"]
  )
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
      st.success(
          "Database aggiornato con successo tramite il file caricato!"
      )
    except Exception as e:
      st.error(f"Errore nell'importazione: {e}")

  st.subheader("📤 Esporta database")
  if not df.empty:
    csv_bytes = (
        df.drop(columns=["Data_dt"], errors="ignore")
        .to_csv(index=False)
        .encode("utf-8")
    )
    st.download_button(
        "Scarica dati in formato CSV",
        data=csv_bytes,
        file_name="export_meteo.csv",
        mime="text/csv",
    )
# Estrazione sicura dei valori con forzatura dei decimali per la temperatura
        temp_raw = metric.get("temp")
        hum_val = obs.get("humidity", "N.D.")
        pressure_raw = metric.get("pressure", "N.D.")
        rain_val = metric.get("precipTotal", 0.0)
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

        # Layout a 5 colonne
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
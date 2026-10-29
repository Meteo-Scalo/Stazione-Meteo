import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Toplevel
import pandas as pd
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

DB_NAME = "meteo_database.db"

# Tabella climatica di riferimento 1991-2000
CLIMA_1991_2000 = {
    1: {"Temp_Media": 6.1, "Pioggia": 67},
    2: {"Temp_Media": 6.9, "Pioggia": 75},
    3: {"Temp_Media": 10.1, "Pioggia": 77},
    4: {"Temp_Media": 13.7, "Pioggia": 83},
    5: {"Temp_Media": 17.9, "Pioggia": 60},
    6: {"Temp_Media": 22.9, "Pioggia": 34},
    7: {"Temp_Media": 25.7, "Pioggia": 24},
    8: {"Temp_Media": 25.9, "Pioggia": 23},
    9: {"Temp_Media": 20.9, "Pioggia": 84},
    10: {"Temp_Media": 16.6, "Pioggia": 122},
    11: {"Temp_Media": 11.6, "Pioggia": 135},
    12: {"Temp_Media": 7.2, "Pioggia": 94}
}

class MeteoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestore Statistiche Meteo con Database")
        self.root.geometry("1050x880")
        self.root.minsize(950, 720)
        
        self.df = None
        
        # Inizializza il database SQLite
        self.init_database()
        
        # Titolo principale
        self.title_label = tk.Label(root, text="Stazione Meteo Amatoriale Monterotondo Scalo", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=10)
        
        # Barra dei comandi superiore
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(pady=5)
        
        self.btn_load = tk.Button(self.btn_frame, text="📁 Importa Excel/CSV", command=self.load_file, bg="#2e7d32", fg="white", font=("Arial", 10, "bold"), padx=6, pady=5)
        self.btn_load.grid(row=0, column=0, padx=4)
        
        self.btn_manual = tk.Button(self.btn_frame, text="➕ Inserisci Misura", command=self.open_manual_entry, bg="#1565c0", fg="white", font=("Arial", 10, "bold"), padx=6, pady=5)
        self.btn_manual.grid(row=0, column=1, padx=4)

        self.btn_daily_comp = tk.Button(self.btn_frame, text="📈 Confronto Giornaliero", command=self.open_daily_comparison_dialog, bg="#00838f", fg="white", font=("Arial", 10, "bold"), padx=6, pady=5)
        self.btn_daily_comp.grid(row=0, column=2, padx=4)

        self.btn_history = tk.Button(self.btn_frame, text="📊 Storico Mese", command=self.show_monthly_history, bg="#4527a0", fg="white", font=("Arial", 10, "bold"), padx=6, pady=5)
        self.btn_history.grid(row=0, column=3, padx=4)

        self.btn_year_history = tk.Button(self.btn_frame, text="📊 Storico Anno", command=self.show_yearly_history, bg="#6a1b9a", fg="white", font=("Arial", 10, "bold"), padx=6, pady=5)
        self.btn_year_history.grid(row=0, column=4, padx=4)
        
        # --- SEZIONE VISUALIZZAZIONE DATI E FILTRI ---
        self.view_frame = tk.LabelFrame(root, text=" Visualizzazione Dati e Filtri ", font=("Arial", 11, "bold"), padx=10, pady=8)
        self.view_frame.pack(fill="x", padx=20, pady=8)
        
        mode_frame = tk.Frame(self.view_frame)
        mode_frame.pack(fill="x", pady=2)
        
        tk.Label(mode_frame, text="Modalità Visualizzazione:", font=("Arial", 9, "bold")).grid(row=0, column=0, padx=4, sticky="w")
        self.view_mode_var = tk.StringVar(root)
        self.view_mode_var.set("Record Mensili e Assoluti")
        modes = [
            "Record Mensili e Assoluti", 
            "Consultazione Database", 
            "Dati Giornalieri", 
            "Dati Mensili"
        ]
        self.view_mode_menu = tk.OptionMenu(mode_frame, self.view_mode_var, *modes, command=self.on_view_mode_changed)
        self.view_mode_menu.config(font=("Arial", 9), width=32)
        self.view_mode_menu.grid(row=0, column=1, padx=4)
        
        # Frame dinamico per i parametri aggiuntivi della modalità scelta
        self.params_frame = tk.Frame(self.view_frame)
        self.params_frame.pack(fill="x", pady=5)

        # Sezione Tabella Principale / Container Dati
        self.table_frame = tk.LabelFrame(root, text=" Tabella Dati ", font=("Arial", 11, "bold"), padx=10, pady=10)
        self.table_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Configurazione Stile Moderno per Treeview
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview.Heading", background="#1565c0", foreground="white", font=("Arial", 10, "bold"), relief="flat")
        style.map("Treeview.Heading", background=[('active', '#0d47a1')])
        style.configure("Treeview", rowheight=26, font=("Arial", 9), fieldbackground="white", background="white")
        style.map("Treeview", background=[('selected', '#bbdefb')], foreground=[('selected', 'black')])

        # Crea la Treeview iniziale di default
        self.setup_default_treeview()
        
        # Carica i dati dal DB all'avvio
        self.load_from_db()

    def setup_default_treeview(self):
        """Pulisce il container e imposta una Treeview standard"""
        for w in self.table_frame.winfo_children():
            w.destroy()
            
        self.tree = ttk.Treeview(self.table_frame, show="headings", height=12)
        scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def init_database(self):
        """Crea la tabella nel database se non esiste già"""
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
        conn.commit()
        conn.close()

    def load_from_db(self):
        """Carica tutti i dati dal database nel DataFrame dell'applicazione"""
        try:
            conn = sqlite3.connect(DB_NAME)
            self.df = pd.read_sql("SELECT * FROM misurazioni ORDER BY Data ASC", conn)
            conn.close()
            
            if not self.df.empty:
                self.df['Data_dt'] = pd.to_datetime(self.df['Data'], errors='coerce')
                self.update_view()
            else:
                if hasattr(self, 'tree') and self.tree.winfo_exists():
                    for row in self.tree.get_children():
                        self.tree.delete(row)
        except Exception as e:
            messagebox.showerror("Errore DB", f"Impossibile leggere dal database:\n{str(e)}")

    def load_file(self):
        """Importa un file Excel o CSV e lo unisce/salva nel database"""
        file_path = filedialog.askopenfilename(
            title="Seleziona file dati meteo",
            filetypes=[("File Excel", "*.xlsx;*.xls"), ("File CSV", "*.csv"), ("Tutti i file", "*.*")]
        )
        if not file_path:
            return
        
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                df_temp = pd.read_excel(file_path)
            else:
                df_temp = pd.read_csv(file_path, sep=None, engine='python')
            
            required_cols = ['Data', 'Temperatura_Min_C', 'Temperatura_Max_C', 'Temperatura_Media_C', 'Umidita_%', 'Pioggia_mm']
            for col in required_cols:
                if col not in df_temp.columns:
                    raise ValueError(f"Colonna mancante nel file: '{col}'")
            
            df_temp['Data'] = pd.to_datetime(df_temp['Data'], errors='coerce').dt.strftime('%Y-%m-%d')
            numeric_cols = ['Temperatura_Min_C', 'Temperatura_Max_C', 'Temperatura_Media_C', 'Umidita_%', 'Pioggia_mm']
            
            for col in numeric_cols:
                if df_temp[col].dtype == object or str(df_temp[col].dtype).startswith('str'):
                    df_temp[col] = df_temp[col].astype(str).str.replace(',', '.', regex=False)
                df_temp[col] = pd.to_numeric(df_temp[col], errors='coerce')
            
            df_temp = df_temp.rename(columns={'Umidita_%': 'Umidita_Perc'})
            
            conn = sqlite3.connect(DB_NAME)
            df_temp.to_sql('misurazioni', conn, if_exists='replace', index=False)
            conn.close()
            
            self.load_from_db()
            messagebox.showinfo("Successo", "File importato e salvato nel database con successo!")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile elaborare il file:\n{str(e)}")

    def update_view(self):
        if self.df is None or self.df.empty:
            return
        mode = self.view_mode_var.get()
        if mode == "Record Mensili e Assoluti":
            self.setup_default_treeview()
            self.populate_monthly_table()
        elif mode == "Consultazione Database":
            self.setup_default_treeview()
            self.filter_daily_range()
        elif mode == "Dati Giornalieri":
            self.filter_monthly_extremes()
        elif mode == "Dati Mensili":
            self.setup_default_treeview()
            self.filter_yearly_extremes()

    def on_view_mode_changed(self, mode):
        """Gestisce il cambio di modalità di visualizzazione aggiornando i controlli e la tabella"""
        for widget in self.params_frame.winfo_children():
            widget.destroy()
            
        if mode == "Record Mensili e Assoluti":
            self.setup_default_treeview()
            self.populate_monthly_table()
            
        elif mode == "Consultazione Database":
            self.setup_default_treeview()
            tk.Label(self.params_frame, text="Da (YYYY-MM-DD):", font=("Arial", 9)).grid(row=0, column=0, padx=2)
            self.entry_start_date = tk.Entry(self.params_frame, font=("Arial", 9), width=12)
            self.entry_start_date.grid(row=0, column=1, padx=2)
            if self.df is not None and not self.df.empty:
                self.entry_start_date.insert(0, self.df['Data'].min())
            
            tk.Label(self.params_frame, text="A (YYYY-MM-DD):", font=("Arial", 9)).grid(row=0, column=2, padx=2)
            self.entry_end_date = tk.Entry(self.params_frame, font=("Arial", 9), width=12)
            self.entry_end_date.grid(row=0, column=3, padx=2)
            if self.df is not None and not self.df.empty:
                self.entry_end_date.insert(0, self.df['Data'].max())
                
            btn_filter = tk.Button(self.params_frame, text="🔍 Visualizza Dettaglio", command=self.filter_daily_range, bg="#00695c", fg="white", font=("Arial", 9, "bold"), padx=6, pady=2)
            btn_filter.grid(row=0, column=4, padx=10)
            self.filter_daily_range()
            
        elif mode == "Dati Giornalieri":
            tk.Label(self.params_frame, text="Anno:", font=("Arial", 9)).grid(row=0, column=0, padx=2)
            self.param_anno_var = tk.StringVar(self.params_frame)
            anni = sorted(self.df['Data_dt'].dt.year.dropna().unique().astype(int).tolist()) if self.df is not None and not self.df.empty else [datetime.now().year]
            self.param_anno_var.set(str(anni[-1]))
            menu_a = tk.OptionMenu(self.params_frame, self.param_anno_var, *[str(a) for a in anni])
            menu_a.config(font=("Arial", 9), width=8)
            menu_a.grid(row=0, column=1, padx=2)
            
            tk.Label(self.params_frame, text="Mese:", font=("Arial", 9)).grid(row=0, column=2, padx=2)
            self.param_mese_var = tk.StringVar(self.params_frame)
            self.param_mese_var.set("Gennaio")
            mesi_nomi_list = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
            menu_m = tk.OptionMenu(self.params_frame, self.param_mese_var, *mesi_nomi_list)
            menu_m.config(font=("Arial", 9), width=11)
            menu_m.grid(row=0, column=3, padx=2)
            
            btn_filter = tk.Button(self.params_frame, text="🔍 Visualizza Dettaglio & Estremi", command=self.filter_monthly_extremes, bg="#00695c", fg="white", font=("Arial", 9, "bold"), padx=6, pady=2)
            btn_filter.grid(row=0, column=4, padx=6)

            btn_pdf = tk.Button(self.params_frame, text="📄 Esporta PDF", command=self.export_monthly_pdf_action, bg="#c62828", fg="white", font=("Arial", 9, "bold"), padx=6, pady=2)
            btn_pdf.grid(row=0, column=5, padx=6)

            self.filter_monthly_extremes()
            
        elif mode == "Dati Mensili":
            self.setup_default_treeview()
            tk.Label(self.params_frame, text="Anno:", font=("Arial", 9)).grid(row=0, column=0, padx=2)
            self.param_anno_y_var = tk.StringVar(self.params_frame)
            anni = sorted(self.df['Data_dt'].dt.year.dropna().unique().astype(int).tolist()) if self.df is not None and not self.df.empty else [datetime.now().year]
            self.param_anno_y_var.set("Tutti")
            menu_ay = tk.OptionMenu(self.params_frame, self.param_anno_y_var, "Tutti", *[str(a) for a in anni])
            menu_ay.config(font=("Arial", 9), width=10)
            menu_ay.grid(row=0, column=1, padx=2)
            
            btn_filter = tk.Button(self.params_frame, text="🔍 Visualizza Estremi Annuali", command=self.filter_yearly_extremes, bg="#00695c", fg="white", font=("Arial", 9, "bold"), padx=6, pady=2)
            btn_filter.grid(row=0, column=2, padx=6)

            btn_pdf = tk.Button(self.params_frame, text="📄 Esporta PDF", command=self.export_yearly_pdf_action, bg="#c62828", fg="white", font=("Arial", 9, "bold"), padx=6, pady=2)
            btn_pdf.grid(row=0, column=3, padx=6)

            self.filter_yearly_extremes()

    def populate_monthly_table(self):
        """Popola la tabella principale con i record mensili e la riga dei record assoluti"""
        columns = ("Mese", "1° Max (°C)", "Data 1° Max", "2° Max (°C)", "Data 2° Max", "1° Min (°C)", "Data 1° Min", "2° Min (°C)", "Data 2° Min")
        self.tree.config(columns=columns, show="headings")
        
        col_widths = [120, 95, 105, 95, 105, 95, 105, 95, 105]
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
            
        self.tree.tag_configure("assoluti", background="#fff9c4", font=("Arial", 9, "bold"))
        
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        temp_df = self.df.copy()
        temp_df['Mese_Num'] = temp_df['Data_dt'].dt.month
        
        mesi_nomi = {
            1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
            5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
            9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
        }
        
        for m_num in range(1, 13):
            m_data = temp_df[temp_df['Mese_Num'] == m_num]
            if m_data.empty:
                continue
            
            top_max = m_data.sort_values(by='Temperatura_Max_C', ascending=False).head(2)
            top_min = m_data.sort_values(by='Temperatura_Min_C', ascending=True).head(2)
            
            max_vals = top_max['Temperatura_Max_C'].tolist()
            max_dates = top_max['Data'].tolist()
            min_vals = top_min['Temperatura_Min_C'].tolist()
            min_dates = top_min['Data'].tolist()
            
            m1_t = f"{max_vals[0]:.1f}" if len(max_vals) > 0 else "-"
            m1_d = f"{max_dates[0]}" if len(max_dates) > 0 else "-"
            m2_t = f"{max_vals[1]:.1f}" if len(max_vals) > 1 else "-"
            m2_d = f"{max_dates[1]}" if len(max_dates) > 1 else "-"
            
            min1_t = f"{min_vals[0]:.1f}" if len(min_vals) > 0 else "-"
            min1_d = f"{min_dates[0]}" if len(min_dates) > 0 else "-"
            min2_t = f"{min_vals[1]:.1f}" if len(min_vals) > 1 else "-"
            min2_d = f"{min_dates[1]}" if len(min_dates) > 1 else "-"
            
            row_values = (mesi_nomi[m_num], m1_t, m1_d, m2_t, m2_d, min1_t, min1_d, min2_t, min2_d)
            self.tree.insert("", "end", values=row_values)
            
        if not temp_df.empty:
            abs_max_row = temp_df.loc[temp_df['Temperatura_Max_C'].idxmax()]
            abs_min_row = temp_df.loc[temp_df['Temperatura_Min_C'].idxmin()]
            
            abs_row_values = (
                "⭐ RECORD ASSOLUTI",
                f"{abs_max_row['Temperatura_Max_C']:.1f}", abs_max_row['Data'],
                "-", "-",
                f"{abs_min_row['Temperatura_Min_C']:.1f}", abs_min_row['Data'],
                "-", "-"
            )
            self.tree.insert("", "end", values=abs_row_values, tags=("assoluti",))

    def filter_daily_range(self):
        """Filtra e visualizza i dati giorno per giorno in base al range temporale selezionato"""
        if self.df is None or self.df.empty:
            return
        start_str = self.entry_start_date.get().strip()
        end_str = self.entry_end_date.get().strip()
        
        try:
            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
        except Exception as ex:
            messagebox.showerror("Errore", f"Formato data non valido (usa YYYY-MM-DD):\n{str(ex)}")
            return
            
        filtered = self.df[(self.df['Data_dt'] >= start_dt) & (self.df['Data_dt'] <= end_dt)].sort_values('Data_dt')
        
        columns = ("Data", "Temp Min (°C)", "Temp Max (°C)", "Temp Media (°C)", "Umidità (%)", "Pioggia (mm)")
        col_widths = [140, 120, 120, 120, 120, 120]
        
        self.tree.config(columns=columns, show="headings")
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
            
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        for _, row in filtered.iterrows():
            self.tree.insert("", "end", values=(
                row['Data'],
                f"{row['Temperatura_Min_C']:.1f}",
                f"{row['Temperatura_Max_C']:.1f}",
                f"{row['Temperatura_Media_C']:.1f}",
                f"{row['Umidita_Perc']:.0f}",
                f"{row['Pioggia_mm']:.1f}"
            ))

    def filter_monthly_extremes(self):
        """Visualizza in alto il pannello card degli estremi/riepilogo e sotto la tabella con le misure giornaliere del mese"""
        if self.df is None or self.df.empty:
            return
        try:
            anno = int(self.param_anno_var.get())
        except ValueError:
            return
        mese_str = self.param_mese_var.get()
        mesi_dict = {"Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4, "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8, "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12}
        m = mesi_dict[mese_str]
        
        t_df = self.df.copy()
        t_df['Anno'] = t_df['Data_dt'].dt.year
        t_df['Mese'] = t_df['Data_dt'].dt.month
        
        month_data = t_df[(t_df['Anno'] == anno) & (t_df['Mese'] == m)].sort_values('Data_dt')
        
        for w in self.table_frame.winfo_children():
            w.destroy()
            
        if month_data.empty:
            tk.Label(self.table_frame, text=f"Nessun dato trovato per {mese_str} {anno}.", font=("Arial", 11), fg="red").pack(pady=20)
            return
            
        min_row = month_data.loc[month_data['Temperatura_Min_C'].idxmin()]
        max_row = month_data.loc[month_data['Temperatura_Max_C'].idxmax()]
        mean_temp = month_data['Temperatura_Media_C'].mean()
        mean_hum = month_data['Umidita_Perc'].mean()
        tot_rain = month_data['Pioggia_mm'].sum()
        
        # Riferimento Tabella 1991-2000
        hist_tmed = CLIMA_1991_2000[m]["Temp_Media"]
        hist_rain = CLIMA_1991_2000[m]["Pioggia"]
        delta_t = mean_temp - hist_tmed
        delta_rain = tot_rain - hist_rain
        
        card_frame = tk.LabelFrame(self.table_frame, text=f" Riepilogo ed Estremi: {mese_str} {anno} (vs Storico 1991-2000) ", font=("Arial", 10, "bold"), bg="#fffde7", fg="#f57f17", padx=10, pady=8)
        card_frame.pack(fill="x", padx=5, pady=5)
        
        lbl_min = tk.Label(card_frame, text=f"❄️ T. Minima Assoluta: {min_row['Temperatura_Min_C']:.1f} °C (Data: {min_row['Data']})", font=("Arial", 9, "bold"), bg="#fffde7", anchor="w")
        lbl_min.grid(row=0, column=0, sticky="w", padx=10, pady=2)
        
        lbl_max = tk.Label(card_frame, text=f"🔥 T. Massima Assoluta: {max_row['Temperatura_Max_C']:.1f} °C (Data: {max_row['Data']})", font=("Arial", 9, "bold"), bg="#fffde7", anchor="w")
        lbl_max.grid(row=0, column=1, sticky="w", padx=10, pady=2)
        
        lbl_avg = tk.Label(card_frame, text=f"📊 Temp. Media Mese: {mean_temp:.1f} °C ({delta_t:+.1f} °C vs storico 1991-2000)  |  Umidità Media: {mean_hum:.0f}%", font=("Arial", 9, "bold"), bg="#fffde7", anchor="w")
        lbl_avg.grid(row=1, column=0, sticky="w", padx=10, pady=2)
        
        lbl_rain = tk.Label(card_frame, text=f"🌧️ Pioggia Totale Mese: {tot_rain:.1f} mm ({delta_rain:+.1f} mm vs storico 1991-2000)", font=("Arial", 9, "bold"), bg="#fffde7", anchor="w")
        lbl_rain.grid(row=1, column=1, sticky="w", padx=10, pady=2)
        
        bottom_container = tk.Frame(self.table_frame)
        bottom_container.pack(fill="both", expand=True, pady=5)
        
        columns = ("Data", "Temp Min (°C)", "Temp Max (°C)", "Temp Media (°C)", "Umidità (%)", "Pioggia (mm)")
        col_widths = [150, 120, 120, 120, 120, 130]
        
        self.tree = ttk.Treeview(bottom_container, columns=columns, show="headings", height=9)
        scrollbar = ttk.Scrollbar(bottom_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
            
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        for _, row in month_data.iterrows():
            self.tree.insert("", "end", values=(
                row['Data'],
                f"{row['Temperatura_Min_C']:.1f}",
                f"{row['Temperatura_Max_C']:.1f}",
                f"{row['Temperatura_Media_C']:.1f}",
                f"{row['Umidita_Perc']:.0f}",
                f"{row['Pioggia_mm']:.1f}"
            ))

    def filter_yearly_extremes(self):
        """Visualizza gli estremi annuali con grafica ottimizzata"""
        if self.df is None or self.df.empty:
            return
        sel_anno = self.param_anno_y_var.get()
        
        t_df = self.df.copy()
        t_df['Anno'] = t_df['Data_dt'].dt.year
        
        if sel_anno != "Tutti":
            try:
                anni = [int(sel_anno)]
            except ValueError:
                anni = sorted(t_df['Anno'].dropna().unique().astype(int).tolist())
        else:
            anni = sorted(t_df['Anno'].dropna().unique().astype(int).tolist())
            
        columns = ("Anno", "Temp Min (°C)", "Data Min", "Temp Max (°C)", "Data Max", "Temp Media (°C)", "Pioggia Totale (mm)")
        col_widths = [100, 115, 115, 115, 115, 115, 140]
        
        self.tree.config(columns=columns, show="headings")
        for col, width in zip(columns, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=width, anchor="center")
            
        for row in self.tree.get_children():
            self.tree.delete(row)
            
        for a in anni:
            y_data = t_df[t_df['Anno'] == a]
            if y_data.empty:
                continue
            min_row = y_data.loc[y_data['Temperatura_Min_C'].idxmin()]
            max_row = y_data.loc[y_data['Temperatura_Max_C'].idxmax()]
            mean_temp = y_data['Temperatura_Media_C'].mean()
            tot_rain = y_data['Pioggia_mm'].sum()
            
            self.tree.insert("", "end", values=(
                str(a),
                f"{min_row['Temperatura_Min_C']:.1f}",
                min_row['Data'],
                f"{max_row['Temperatura_Max_C']:.1f}",
                max_row['Data'],
                f"{mean_temp:.1f}",
                f"{tot_rain:.1f}"
            ))

    def export_monthly_pdf_action(self):
        """Esporta il report mensile corrente in formato PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            
            anno = int(self.param_anno_var.get())
            mese_str = self.param_mese_var.get()
            mesi_dict = {"Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4, "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8, "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12}
            m = mesi_dict[mese_str]
            
            t_df = self.df.copy()
            t_df['Anno'] = t_df['Data_dt'].dt.year
            t_df['Mese'] = t_df['Data_dt'].dt.month
            month_data = t_df[(t_df['Anno'] == anno) & (t_df['Mese'] == m)].sort_values('Data_dt')
            
            if month_data.empty:
                messagebox.showwarning("Attenzione", "Nessun dato da esportare per il mese selezionato.")
                return
                
            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], title="Salva Report Mensile in PDF")
            if not file_path:
                return
                
            doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1565c0'), alignment=1, spaceAfter=10)
            subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#333333'), alignment=1, spaceAfter=15)
            normal_style = styles['Normal']
            
            elements.append(Paragraph("Stazione Meteo Amatoriale Monterotondo Scalo", title_style))
            elements.append(Paragraph(f"Report Dettagliato e Riepilogo Mensile: {mese_str} {anno}", subtitle_style))
            elements.append(Spacer(1, 5))
            
            min_row = month_data.loc[month_data['Temperatura_Min_C'].idxmin()]
            max_row = month_data.loc[month_data['Temperatura_Max_C'].idxmax()]
            mean_temp = month_data['Temperatura_Media_C'].mean()
            mean_hum = month_data['Umidita_Perc'].mean()
            tot_rain = month_data['Pioggia_mm'].sum()
            
            summary_data = [
                [Paragraph("<b>Riepilogo ed Estremi del Mese</b>", normal_style), ""],
                [Paragraph(f"<b>T. Minima Assoluta:</b> {min_row['Temperatura_Min_C']:.1f} °C ({min_row['Data']})", normal_style),
                 Paragraph(f"<b>T. Massima Assoluta:</b> {max_row['Temperatura_Max_C']:.1f} °C ({max_row['Data']})", normal_style)],
                [Paragraph(f"<b>Temperatura Media:</b> {mean_temp:.1f} °C", normal_style),
                 Paragraph(f"<b>Umidità Media:</b> {mean_hum:.0f} %", normal_style)],
                [Paragraph(f"<b>Pioggia Totale:</b> {tot_rain:.1f} mm", normal_style), ""]
            ]
            t_summary = Table(summary_data, colWidths=[260, 260])
            t_summary.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fffde7')),
                ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#fbc02d')),
                ('SPAN', (0,0), (1,0)),
                ('SPAN', (0,3), (1,3)),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(t_summary)
            elements.append(Spacer(1, 15))
            
            table_data = [["Data", "Temp Min (°C)", "Temp Max (°C)", "Temp Media (°C)", "Umidità (%)", "Pioggia (mm)"]]
            for _, r in month_data.iterrows():
                table_data.append([
                    str(r['Data']),
                    f"{r['Temperatura_Min_C']:.1f}",
                    f"{r['Temperatura_Max_C']:.1f}",
                    f"{r['Temperatura_Media_C']:.1f}",
                    f"{r['Umidita_Perc']:.0f}",
                    f"{r['Pioggia_mm']:.1f}"
                ])
            
            t_daily = Table(table_data, colWidths=[95, 85, 85, 85, 75, 95])
            t_daily.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1565c0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f2f2f2')]),
            ]))
            elements.append(t_daily)
            
            doc.build(elements)
            messagebox.showinfo("Successo", "Report mensile esportato in PDF con successo!")
        except ImportError:
            messagebox.showerror("Libreria Mancante", "La libreria 'reportlab' non è installata.\nEsegui da terminale: pip install reportlab")
        except Exception as ex:
            messagebox.showerror("Errore", f"Impossibile generare il PDF:\n{str(ex)}")

    def export_yearly_pdf_action(self):
        """Esporta gli estremi annuali correnti in formato PDF"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            
            sel_anno = self.param_anno_y_var.get()
            t_df = self.df.copy()
            t_df['Anno'] = t_df['Data_dt'].dt.year
            
            if sel_anno != "Tutti":
                anni = [int(sel_anno)]
            else:
                anni = sorted(t_df['Anno'].dropna().unique().astype(int).tolist())
                
            file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")], title="Salva Report Annuale in PDF")
            if not file_path:
                return
                
            doc = SimpleDocTemplate(file_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#1565c0'), alignment=1, spaceAfter=10)
            subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor('#333333'), alignment=1, spaceAfter=15)
            
            elements.append(Paragraph("Stazione Meteo Amatoriale Monterotondo Scalo", title_style))
            elements.append(Paragraph(f"Report Estremi Annuali (Filtro Anno: {sel_anno})", subtitle_style))
            elements.append(Spacer(1, 10))
            
            table_data = [["Anno", "Temp Min (°C)", "Data Min", "Temp Max (°C)", "Data Max", "Temp Media (°C)", "Pioggia Totale (mm)"]]
            for a in anni:
                y_data = t_df[t_df['Anno'] == a]
                if y_data.empty:
                    continue
                min_row = y_data.loc[y_data['Temperatura_Min_C'].idxmin()]
                max_row = y_data.loc[y_data['Temperatura_Max_C'].idxmax()]
                mean_temp = y_data['Temperatura_Media_C'].mean()
                tot_rain = y_data['Pioggia_mm'].sum()
                
                table_data.append([
                    str(a),
                    f"{min_row['Temperatura_Min_C']:.1f}",
                    str(min_row['Data']),
                    f"{max_row['Temperatura_Max_C']:.1f}",
                    str(max_row['Data']),
                    f"{mean_temp:.1f}",
                    f"{tot_rain:.1f}"
                ])
            
            t_yearly = Table(table_data, colWidths=[65, 80, 90, 80, 90, 85, 90])
            t_yearly.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1565c0')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f2f2f2')]),
            ]))
            elements.append(t_yearly)
            
            doc.build(elements)
            messagebox.showinfo("Successo", "Report annuale esportato in PDF con successo!")
        except ImportError:
            messagebox.showerror("Libreria Mancante", "La libreria 'reportlab' non è installata.\nEsegui da terminale: pip install reportlab")
        except Exception as ex:
            messagebox.showerror("Errore", f"Impossibile generare il PDF:\n{str(ex)}")

    def open_manual_entry(self):
        win = Toplevel(self.root)
        win.title("Inserisci Nuova Misura nel DB")
        win.geometry("300x350")
        win.resizable(False, False)
        
        fields = [
            ("Data (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d")),
            ("Temp Min (°C)", "15.0"),
            ("Temp Max (°C)", "25.0"),
            ("Temp Media (°C)", "20.0"),
            ("Umidità (%)", "60"),
            ("Pioggia (mm)", "0.0")
        ]
        
        entries = {}
        for label, default_val in fields:
            tk.Label(win, text=label, font=("Arial", 9)).pack(anchor="w", padx=20)
            e = tk.Entry(win, font=("Arial", 10), width=25)
            e.insert(0, default_val)
            e.pack(padx=20, pady=2)
            entries[label] = e
            
        def save_entry():
            try:
                data_str = entries["Data (YYYY-MM-DD)"].get().strip()
                t_min = float(entries["Temp Min (°C)"].get().replace(',', '.'))
                t_max = float(entries["Temp Max (°C)"].get().replace(',', '.'))
                t_med = float(entries["Temp Media (°C)"].get().replace(',', '.'))
                hum = float(entries["Umidità (%)"].get().replace(',', '.'))
                rain = float(entries["Pioggia (mm)"].get().replace(',', '.'))
                
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO misurazioni (Data, Temperatura_Min_C, Temperatura_Max_C, Temperatura_Media_C, Umidita_Perc, Pioggia_mm)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (data_str, t_min, t_max, t_med, hum, rain))
                conn.commit()
                conn.close()
                
                self.load_from_db()
                win.destroy()
                messagebox.showinfo("Successo", "Misura salvata permanentemente nel database!")
            except Exception as ex:
                messagebox.showerror("Errore", f"Controlla i valori inseriti:\n{str(ex)}")

        tk.Button(win, text="Salva nel Database", command=save_entry, bg="#1565c0", fg="white", font=("Arial", 10, "bold")).pack(pady=12)

    def export_figure(self, fig):
        """Metodo di servizio per esportare qualsiasi figura matplotlib in alta definizione (formato Instagram 4:5)"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("Immagine PNG", "*.png"), ("Immagine JPEG", "*.jpg"), ("Tutti i file", "*.*")],
            title="Salva Grafico per Instagram"
        )
        if file_path:
            try:
                fig.savefig(file_path, dpi=300, bbox_inches='tight')
                messagebox.showinfo("Successo", "Elemento esportato con successo in formato ottimizzato per Instagram (4:5)!")
            except Exception as ex:
                messagebox.showerror("Errore", f"Impossibile salvare il file:\n{str(ex)}")

    def open_daily_comparison_dialog(self):
        if self.df is None or self.df.empty:
            messagebox.showwarning("Attenzione", "Nessun dato disponibile nel database!")
            return
        
        win = Toplevel(self.root)
        win.title("Seleziona Periodo per Confronto Giornaliero")
        win.geometry("320x210")
        win.resizable(False, False)
        
        tk.Label(win, text="Seleziona Anno:", font=("Arial", 10, "bold")).pack(pady=5)
        temp_df = self.df.copy()
        temp_df['Anno'] = temp_df['Data_dt'].dt.year
        anni_disponibili = sorted(temp_df['Anno'].dropna().unique().astype(int).tolist())
        
        if not anni_disponibili:
            messagebox.showwarning("Attenzione", "Nessun anno valido trovato nei dati.")
            win.destroy()
            return
            
        selected_anno = tk.StringVar(win)
        selected_anno.set(str(anni_disponibili[-1]))
        dropdown_anno = tk.OptionMenu(win, selected_anno, *[str(a) for a in anni_disponibili])
        dropdown_anno.config(font=("Arial", 10), width=15)
        dropdown_anno.pack(pady=2)
        
        tk.Label(win, text="Seleziona Mese:", font=("Arial", 10, "bold")).pack(pady=5)
        mesi_nomi = [
            "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
            "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
        ]
        selected_mese = tk.StringVar(win)
        selected_mese.set(mesi_nomi[0])
        dropdown_mese = tk.OptionMenu(win, selected_mese, *mesi_nomi)
        dropdown_mese.config(font=("Arial", 10), width=15)
        dropdown_mese.pack(pady=2)
        
        def generate_daily_comparison():
            anno = int(selected_anno.get())
            mese_str = selected_mese.get()
            mesi_dict = {
                "Gennaio": 1, "Febbraio": 2, "Marzo": 3, "Aprile": 4,
                "Maggio": 5, "Giugno": 6, "Luglio": 7, "Agosto": 8,
                "Settembre": 9, "Ottobre": 10, "Novembre": 11, "Dicembre": 12
            }
            m = mesi_dict[mese_str]
            
            try:
                t_df = self.df.copy()
                t_df['Anno'] = t_df['Data_dt'].dt.year
                t_df['Mese'] = t_df['Data_dt'].dt.month
                t_df['Giorno'] = t_df['Data_dt'].dt.day
                
                sel_data = t_df[(t_df['Anno'] == anno) & (t_df['Mese'] == m)].sort_values('Giorno')
                
                if sel_data.empty:
                    messagebox.showinfo("Info", f"Nessun dato trovato per {mese_str} {anno}.")
                    return
                
                win.destroy()
                
                chart_win = Toplevel(self.root)
                chart_win.title(f"Confronto Giornaliero - {mese_str} {anno} vs Storico 1991-2000")
                chart_win.geometry("800x860")
                
                top_toolbar = tk.Frame(chart_win)
                top_toolbar.pack(fill="x", padx=10, pady=10)
                
                btn_export = tk.Button(top_toolbar, text="📸 Esporta Grafico per Instagram (4:5)", command=lambda: self.export_figure(fig), bg="#00695c", fg="white", font=("Arial", 10, "bold"), padx=10, pady=6)
                btn_export.pack(side="left")
                
                container = tk.Frame(chart_win)
                container.pack(fill="both", expand=True, padx=10, pady=5)
                
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 10), dpi=100)
                
                days = list(range(1, 32))
                sel_med_dict = dict(zip(sel_data['Giorno'], sel_data['Temperatura_Media_C']))
                sel_rain_dict = dict(zip(sel_data['Giorno'], sel_data['Pioggia_mm']))
                
                d_list = []
                s_med_list = []
                s_rain_list = []
                
                for d in days:
                    try:
                        datetime(anno, m, d)
                    except ValueError:
                        continue
                        
                    d_list.append(d)
                    s_med_list.append(sel_med_dict.get(d, float('nan')))
                    s_rain_list.append(sel_rain_dict.get(d, 0.0))
                
                # Valori climatici 1991-2000 dalla tabella
                clima_temp = CLIMA_1991_2000[m]["Temp_Media"]
                clima_rain_tot = CLIMA_1991_2000[m]["Pioggia"]
                
                # --- Sottografo 1: Temperatura Media ---
                ax1.plot(d_list, s_med_list, marker='o', color='#3f51b5', linewidth=2.5, label=f'Temp. Media {mese_str} {anno}')
                ax1.axhline(clima_temp, color='#d32f2f', linestyle='--', linewidth=2, label=f'Media Storica Temp. 1991-2000 ({clima_temp} °C)')
                ax1.set_title(f"Stazione Meteo Amatoriale Monterotondo Scalo\nConfronto Temperatura Media - {mese_str} {anno}", fontsize=14, fontweight='bold', pad=15)
                ax1.set_ylabel("Temp. Media (°C)", fontsize=10)
                ax1.set_xticks(d_list)
                ax1.grid(True, linestyle='--', alpha=0.6)
                ax1.legend(loc='upper right', fontsize=9)
                
                # --- Sottografo 2: Pioggia ---
                ax2.bar(d_list, s_rain_list, color='#00acc1', alpha=0.8, label=f'Pioggia Giornaliera {mese_str} {anno}')
                # Linea retta costante per il totale mensile storico 1991-2000 convertito in quota giornaliera equivalente di riferimento
                num_giorni = len(d_list)
                pioggia_media_quotidiana_storica = clima_rain_tot / num_giorni
                ax2.axhline(pioggia_media_quotidiana_storica, color='#d32f2f', linestyle='--', linewidth=2, label=f'Media Storica 1991-2000 (Tot. Mensile: {clima_rain_tot} mm)')
                ax2.set_title(f"Precipitazioni - {mese_str} {anno} (Tot. Mese: {sum(s_rain_list):.1f} mm vs Storico 1991-2000: {clima_rain_tot} mm)", fontsize=14, fontweight='bold', pad=15)
                ax2.set_xlabel("Giorno del Mese", fontsize=10)
                ax2.set_ylabel("Pioggia (mm)", fontsize=10)
                ax2.set_xticks(d_list)
                ax2.grid(True, axis='y', linestyle='--', alpha=0.6)
                ax2.legend(loc='upper right', fontsize=9)
                
                fig.subplots_adjust(top=0.88, bottom=0.1, left=0.12, right=0.92, hspace=0.35)
                
                canvas = FigureCanvasTkAgg(fig, master=container)
                canvas.draw()
                canvas.get_tk_widget().pack(fill="both", expand=True)
                
            except Exception as ex:
                messagebox.showerror("Errore", f"Errore durante la generazione del grafico:\n{str(ex)}")

        tk.Button(win, text="Genera Grafico", command=generate_daily_comparison, bg="#2e7d32", fg="white", font=("Arial", 10, "bold")).pack(pady=12)

    def show_monthly_history(self):
        if self.df is None or self.df.empty:
            messagebox.showwarning("Attenzione", "Nessun dato disponibile nel database!")
            return
        
        win = Toplevel(self.root)
        win.title("Storico Mese")
        win.geometry("300x160")
        win.resizable(False, False)
        
        tk.Label
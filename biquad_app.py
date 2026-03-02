"""
Instrucciones de instalación:
pip install matplotlib numpy

Este script es una aplicación de escritorio para Windows diseñada para el
cálculo y prueba de antenas tipo Biquad.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import threading
import time
import subprocess
import re
import math
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import os

# Constantes de diseño
C = 299792458  # Velocidad de la luz en m/s

# Canales y frecuencias (MHz)
WIFI_CHANNELS_24 = {
    1: 2412, 2: 2417, 3: 2422, 4: 2427, 5: 2432, 6: 2437,
    7: 2442, 8: 2447, 9: 2452, 10: 2457, 11: 2462, 12: 2467,
    13: 2472, 14: 2484
}

WIFI_CHANNELS_5 = {
    36: 5180, 40: 5200, 44: 5220, 48: 5240,
    52: 5260, 56: 5280, 60: 5300, 64: 5320,
    100: 5500, 104: 5520, 108: 5540, 112: 5560,
    116: 5580, 120: 5600, 124: 5620, 128: 5640,
    132: 5660, 136: 5680, 140: 5700, 144: 5720,
    149: 5745, 153: 5765, 157: 5785, 161: 5805, 165: 5825
}

# Regulaciones por país (Canales permitidos)
REGULATIONS = {
    "España (ETSI)": {
        "2.4G": list(range(1, 14)), # 1-13
        "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]
    },
    "EE. UU. (FCC)": {
        "2.4G": list(range(1, 12)), # 1-11
        "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
    },
    "Japón (MKK)": {
        "2.4G": list(range(1, 15)), # 1-14
        "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144]
    },
    "Canadá (IC)": {
        "2.4G": list(range(1, 12)), # 1-11
        "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165]
    },
    "Australia (RCM)": {
        "2.4G": list(range(1, 14)), # 1-13
        "5G": [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 149, 153, 157, 161, 165]
    }
}

def calcular_dimensiones(frecuencia_mhz):
    """
    Calcula las dimensiones de la antena Biquad para una frecuencia dada.
    Retorna un diccionario con los valores en mm.
    """
    wavelength = (C / (frecuencia_mhz * 1e6)) * 1000  # en mm
    lado_elemento = wavelength / 4
    lado_reflector = wavelength / 2
    separacion = wavelength / 8
    perimetro_total = lado_elemento * 8

    return {
        "wavelength": round(wavelength, 2),
        "lado_elemento": round(lado_elemento, 2),
        "lado_reflector": round(lado_reflector, 2),
        "separacion": round(separacion, 2),
        "perimetro_total": round(perimetro_total, 2)
    }

class BiquadApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Diseño y Prueba de Antenas Biquad")
        self.root.geometry("900x700")

        # Variables de estado
        self.selected_country = tk.StringVar(value="España (ETSI)")
        self.selected_band = tk.StringVar(value="2.4G")
        self.selected_channel = tk.StringVar()
        self.custom_freq = tk.StringVar()

        self.setup_ui()
        self.update_clock()
        self.update_channels()
        # Iniciar escaneo inicial para poblar la lista de SSIDs
        threading.Thread(target=self.initial_scan, daemon=True).start()

    def initial_scan(self):
        self.label_status.config(text="Buscando redes iniciales...")
        data = self.perform_wifi_scan()
        if data:
            self.root.after(0, lambda d=data: self.update_spectrum_plot(d))
            self.label_status.config(text="Redes detectadas.")
        else:
            self.label_status.config(text="No se detectaron redes en el inicio.")

    def setup_ui(self):
        # Notebook para pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        self.tab_design = ttk.Frame(self.notebook)
        self.tab_spectrum = ttk.Frame(self.notebook)
        self.tab_meter = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_design, text="Diseño de Antena")
        self.notebook.add(self.tab_spectrum, text="Espectrómetro")
        self.notebook.add(self.tab_meter, text="Medidor de Señal")

        self.setup_design_tab()
        self.setup_spectrum_tab()
        self.setup_meter_tab()
        self.setup_status_bar()

    def setup_meter_tab(self):
        # Frame superior para selección de red
        ctrl_frame = ttk.Frame(self.tab_meter, padding=10)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(ctrl_frame, text="Seleccionar Red WiFi:").pack(side=tk.LEFT, padx=5)
        self.selected_ssid = tk.StringVar()
        self.combo_ssid = ttk.Combobox(ctrl_frame, textvariable=self.selected_ssid, state="readonly", width=30)
        self.combo_ssid.pack(side=tk.LEFT, padx=5)

        self.btn_measure = ttk.Button(ctrl_frame, text="Medir Intensidad", command=self.toggle_measure)
        self.btn_measure.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="Refrescar Lista", command=self.manual_refresh).pack(side=tk.LEFT, padx=5)

        # Indicadores visuales
        info_frame = ttk.Frame(self.tab_meter, padding=10)
        info_frame.pack(side=tk.TOP, fill=tk.X)

        self.label_rssi = ttk.Label(info_frame, text="RSSI: -- dBm", font=('Arial', 14, 'bold'))
        self.label_rssi.pack(side=tk.LEFT, padx=20)

        self.progress_signal = ttk.Progressbar(info_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress_signal.pack(side=tk.LEFT, padx=20)

        # Gráfico de historial
        self.fig_hist = Figure(figsize=(8, 3))
        self.ax_hist = self.fig_hist.add_subplot(111)
        self.canvas_hist = FigureCanvasTkAgg(self.fig_hist, master=self.tab_meter)
        self.canvas_hist.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.measure_running = False
        self.rssi_history = []
        self.update_history_plot()

    def setup_spectrum_tab(self):
        # Frame superior para controles de escaneo
        ctrl_frame = ttk.Frame(self.tab_spectrum, padding=10)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X)

        self.btn_scan = ttk.Button(ctrl_frame, text="Iniciar Escaneo", command=self.toggle_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        self.scan_running = False
        self.networks_data = []

        # Area de gráfico
        self.fig = Figure(figsize=(8, 4))
        self.ax = self.fig.add_subplot(111)
        self.canvas_plt = FigureCanvasTkAgg(self.fig, master=self.tab_spectrum)
        self.canvas_plt.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.update_spectrum_plot([])

    def setup_status_bar(self):
        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(5, 2))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.label_clock = ttk.Label(self.status_bar, text="")
        self.label_clock.pack(side=tk.RIGHT)

        self.label_status = ttk.Label(self.status_bar, text="Listo")
        self.label_status.pack(side=tk.LEFT)

    def update_clock(self):
        now = datetime.datetime.now()
        self.label_clock.config(text=now.strftime("%d/%m/%Y %H:%M:%S"))
        self.root.after(1000, self.update_clock)

    def setup_design_tab(self):
        # Panel izquierdo: Controles
        control_frame = ttk.LabelFrame(self.tab_design, text="Parámetros de Diseño", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        ttk.Label(control_frame, text="País/Regulación:").grid(row=0, column=0, sticky='w', pady=5)
        self.combo_country = ttk.Combobox(control_frame, textvariable=self.selected_country, values=list(REGULATIONS.keys()), state="readonly")
        self.combo_country.grid(row=0, column=1, pady=5)
        self.combo_country.bind("<<ComboboxSelected>>", lambda e: self.update_channels())

        ttk.Label(control_frame, text="Banda:").grid(row=1, column=0, sticky='w', pady=5)
        band_frame = ttk.Frame(control_frame)
        band_frame.grid(row=1, column=1, pady=5, sticky='w')
        ttk.Radiobutton(band_frame, text="2.4 GHz", variable=self.selected_band, value="2.4G", command=self.update_channels).pack(side=tk.LEFT)
        ttk.Radiobutton(band_frame, text="5 GHz", variable=self.selected_band, value="5G", command=self.update_channels).pack(side=tk.LEFT)

        ttk.Label(control_frame, text="Canal:").grid(row=2, column=0, sticky='w', pady=5)
        self.combo_channel = ttk.Combobox(control_frame, textvariable=self.selected_channel, state="readonly")
        self.combo_channel.grid(row=2, column=1, pady=5)
        self.combo_channel.bind("<<ComboboxSelected>>", lambda e: self.on_channel_selected())

        ttk.Separator(control_frame, orient='horizontal').grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)

        ttk.Label(control_frame, text="Frecuencia personalizada (MHz):").grid(row=4, column=0, sticky='w', pady=5)
        self.entry_freq = ttk.Entry(control_frame, textvariable=self.custom_freq)
        self.entry_freq.grid(row=4, column=1, pady=5)
        ttk.Button(control_frame, text="Calcular", command=self.on_custom_freq).grid(row=5, column=0, columnspan=2, pady=5)

        # Resultados
        self.result_frame = ttk.LabelFrame(self.tab_design, text="Dimensiones Calculadas (mm)", padding=10)
        self.result_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.labels_dims = {}
        fields = [("Longitud de onda (λ)", "wavelength"),
                  ("Lado del elemento (λ/4)", "lado_elemento"),
                  ("Lado del reflector (λ/2)", "lado_reflector"),
                  ("Separación elemento-reflector (λ/8)", "separacion"),
                  ("Perímetro total del alambre", "perimetro_total")]

        for i, (label, key) in enumerate(fields):
            ttk.Label(self.result_frame, text=label).grid(row=i, column=0, sticky='w')
            var = tk.StringVar(value="0.00")
            ttk.Label(self.result_frame, textvariable=var, font=('Arial', 10, 'bold')).grid(row=i, column=1, sticky='e', padx=10)
            self.labels_dims[key] = var

        # Dibujo esquemático
        self.canvas_frame = ttk.LabelFrame(self.tab_design, text="Esquema de la Antena", padding=10)
        self.canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(self.canvas_frame, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        # Redibujar cuando el canvas cambie de tamaño
        self.canvas.bind("<Configure>", lambda e: self.on_channel_selected())

    def update_channels(self):
        country = self.selected_country.get()
        band = self.selected_band.get()
        allowed = REGULATIONS[country][band]

        ch_dict = WIFI_CHANNELS_24 if band == "2.4G" else WIFI_CHANNELS_5
        values = []
        for ch in sorted(ch_dict.keys()):
            freq = ch_dict[ch]
            status = "" if ch in allowed else " (No permitido)"
            values.append(f"CH {ch} - {freq} MHz{status}")

        self.combo_channel['values'] = values
        if values:
            self.combo_channel.current(0)
            self.on_channel_selected()

    def on_channel_selected(self):
        val = self.selected_channel.get()
        if not val: return
        try:
            ch_num = int(re.search(r"CH (\d+)", val).group(1))
            band = self.selected_band.get()
            freq = WIFI_CHANNELS_24[ch_num] if band == "2.4G" else WIFI_CHANNELS_5[ch_num]
            self.calculate_and_display(freq)
        except Exception as e:
            messagebox.showerror("Error", f"Error al seleccionar canal: {e}")

    def on_custom_freq(self):
        try:
            freq = float(self.custom_freq.get())
            if freq < 2000 or freq > 6000:
                raise ValueError("Frecuencia fuera de rango típico (2-6 GHz)")
            self.calculate_and_display(freq)

            # Buscar canal más cercano
            band = "2.4G" if freq < 4000 else "5G"
            ch_dict = WIFI_CHANNELS_24 if band == "2.4G" else WIFI_CHANNELS_5
            closest_ch = min(ch_dict.keys(), key=lambda k: abs(ch_dict[k] - freq))
            self.label_status.config(text=f"Frecuencia personalizada: {freq} MHz (Cercana a CH {closest_ch})")
        except ValueError as e:
            messagebox.showwarning("Valor inválido", str(e))

    def toggle_scan(self):
        if not self.scan_running:
            self.scan_running = True
            self.btn_scan.config(text="Detener Escaneo")
            self.label_status.config(text="Escaneando redes WiFi...")
            threading.Thread(target=self.scan_loop, daemon=True).start()
        else:
            self.scan_running = False
            self.btn_scan.config(text="Iniciar Escaneo")
            self.label_status.config(text="Escaneo detenido")

    def scan_loop(self):
        try:
            while self.scan_running:
                data = self.perform_wifi_scan()
                self.networks_data = data
                self.root.after(0, lambda d=data: self.update_spectrum_plot(d))
                time.sleep(5) # Escaneo cada 5 segundos
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self.label_status.config(text=f"Error en escaneo: {msg}"))
            self.scan_running = False

    def perform_wifi_scan(self):
        """
        Ejecuta el escaneo de redes WiFi usando netsh en Windows.
        """
        if os.name != 'nt':
            # Mock para sistemas no Windows (Linux/Mac)
            mock_data = []
            for i in range(5):
                mock_data.append({
                    'ssid': f'MockWiFi_{i}',
                    'channel': np.random.choice(list(WIFI_CHANNELS_24.keys())),
                    'signal': np.random.randint(30, 95)
                })
            return mock_data

        try:
            # Usar subprocess.run para mejor control de errores y encoding
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                encoding='latin-1',
                errors='ignore',
                shell=False
            )

            if result.returncode != 0:
                print(f"Error de netsh (code {result.returncode}): {result.stderr}")
                return []

            return self.parse_netsh_output(result.stdout)
        except Exception as e:
            print(f"Error en escaneo: {e}")
            return []

    def parse_netsh_output(self, output):
        """
        Parsea la salida de netsh de forma robusta usando expresiones regulares.
        Soporta múltiples BSSIDs por SSID y localizaciones en inglés/español.
        """
        networks = []
        current_ssid = None
        current_signal = None

        # Patrones para SSID, Señal y Canal
        re_ssid = re.compile(r"^SSID\s+\d+\s*:\s*(.*)$", re.IGNORECASE)
        re_signal = re.compile(r"(?:Signal|Señal|Intensidad)\s*:\s*(\d+)\s*%", re.IGNORECASE)
        re_channel = re.compile(r"(?:Channel|Canal)\s*:\s*(\d+)", re.IGNORECASE)

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Buscar SSID
            ssid_match = re_ssid.match(line)
            if ssid_match:
                current_ssid = ssid_match.group(1).strip()
                if not current_ssid:
                    current_ssid = "<Hidden>"
                continue

            # Buscar Señal
            sig_match = re_signal.search(line)
            if sig_match:
                current_signal = int(sig_match.group(1))
                continue

            # Buscar Canal
            chan_match = re_channel.search(line)
            if chan_match:
                current_channel = int(chan_match.group(1))
                if current_ssid and current_signal is not None:
                    networks.append({
                        'ssid': current_ssid,
                        'signal': current_signal,
                        'channel': current_channel
                    })
                    # Resetear señal para el próximo BSSID bajo el mismo SSID
                    current_signal = None
                continue

        return networks

    def manual_refresh(self):
        """Dispara un escaneo único para refrescar la lista de SSIDs."""
        threading.Thread(target=self.initial_scan, daemon=True).start()

    def toggle_measure(self):
        if not self.measure_running:
            if not self.selected_ssid.get():
                messagebox.showwarning("Selección necesaria", "Por favor, seleccione una red WiFi primero (realice un escaneo si es necesario).")
                return
            self.measure_running = True
            self.btn_measure.config(text="Detener Medición")
            self.rssi_history = []
            threading.Thread(target=self.measure_loop, daemon=True).start()
        else:
            self.measure_running = False
            self.btn_measure.config(text="Medir Intensidad")

    def measure_loop(self):
        """
        Bucle de medición continua para la red seleccionada.
        Busca el BSSID con señal más fuerte para el SSID elegido.
        """
        try:
            while self.measure_running:
                ssid = self.selected_ssid.get()
                data = self.perform_wifi_scan()

                # Actualizar lista de SSIDs en el combo mientras tanto
                ssids = sorted(list(set(net['ssid'] for net in data)))
                self.root.after(0, lambda s=ssids: self.update_ssid_list(s))

                # Buscar la red seleccionada (la señal más fuerte si hay múltiples BSSIDs)
                strongest_net = None
                for net in data:
                    if net['ssid'] == ssid:
                        if strongest_net is None or net['signal'] > strongest_net['signal']:
                            strongest_net = net

                if strongest_net:
                    dbm = (strongest_net['signal'] / 2) - 100
                    self.rssi_history.append(dbm)
                    if len(self.rssi_history) > 50: self.rssi_history.pop(0)

                    self.root.after(0, lambda d=dbm, p=strongest_net['signal']: self.update_meter_ui(d, p))
                else:
                    self.root.after(0, lambda: self.label_rssi.config(text="Red no detectada"))

                time.sleep(2) # Actualización cada 2 segundos
        except Exception as e:
            self.root.after(0, lambda msg=str(e): self.label_status.config(text=f"Error en medición: {msg}"))
            self.measure_running = False

    def update_ssid_list(self, ssids):
        current = self.selected_ssid.get()
        self.combo_ssid['values'] = ssids
        if current not in ssids and ssids:
            pass # Mantener selección actual si es posible

    def update_meter_ui(self, dbm, perc):
        self.label_rssi.config(text=f"RSSI: {dbm:.1f} dBm")
        self.progress_signal['value'] = perc
        self.update_history_plot()

    def update_history_plot(self):
        self.ax_hist.clear()
        if self.rssi_history:
            self.ax_hist.plot(self.rssi_history, marker='o', color='green')
        self.ax_hist.set_ylim(-100, -20)
        self.ax_hist.set_ylabel("RSSI (dBm)")
        self.ax_hist.set_title("Variación de Señal en el Tiempo")
        self.ax_hist.grid(True, linestyle='--', alpha=0.7)
        self.fig_hist.tight_layout()
        self.canvas_hist.draw()

    def update_spectrum_plot(self, data):
        # Actualizar también la lista de SSIDs para el medidor
        ssids = sorted(list(set(net['ssid'] for net in data)))
        self.root.after(0, lambda s=ssids: self.update_ssid_list(s))

        self.ax.clear()

        band = self.selected_band.get()
        if band == "2.4G":
            channels = list(range(1, 15))
            intensities = [-100] * 14
            for net in data:
                ch = net['channel']
                if 1 <= ch <= 14:
                    dbm = (net['signal'] / 2) - 100
                    if dbm > intensities[ch-1]: intensities[ch-1] = dbm

            # Para que la barra se vea correctamente, el height debe ser (dbm - bottom)
            heights = [i + 100 for i in intensities]
            self.ax.bar(channels, heights, bottom=-100, color='skyblue')
            self.ax.set_xticks(channels)
            self.ax.set_xlabel("Canal WiFi (2.4 GHz)")
        else:
            # Para 5GHz mostramos solo los canales que tienen datos para no saturar el eje X
            detected_5g = [net for net in data if net['channel'] >= 36]
            if not detected_5g:
                channels = [36, 40, 44, 48] # Mostrar algunos por defecto
                heights = [0] * 4
            else:
                channels = sorted(list(set(net['channel'] for net in detected_5g)))
                heights = []
                for ch in channels:
                    max_sig = max(net['signal'] for net in detected_5g if net['channel'] == ch)
                    dbm = (max_sig / 2) - 100
                    heights.append(dbm + 100)

            self.ax.bar(channels, heights, bottom=-100, color='lightgreen', width=2)
            self.ax.set_xticks(channels)
            self.ax.set_xlabel("Canal WiFi (5 GHz)")

        self.ax.set_ylim(-100, -20)
        self.ax.set_ylabel("Intensidad (dBm)")
        self.ax.set_title(f"Espectro WiFi Detectado ({band})")
        self.fig.tight_layout()
        self.canvas_plt.draw()

    def calculate_and_display(self, freq):
        dims = calcular_dimensiones(freq)
        for key, var in self.labels_dims.items():
            var.set(f"{dims[key]:.2f}")
        self.draw_schematic(dims)

    def draw_schematic(self, dims):
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10: w, h = 400, 300 # Fallback inicial

        cx, cy = w // 2, h // 2

        # Escalar para que quepa (el reflector es lo más grande, λ/2)
        scale = min(w, h) / (dims['lado_reflector'] * 1.5)

        # Dibujar reflector (fondo)
        r_size = dims['lado_reflector'] * scale
        self.canvas.create_rectangle(cx - r_size/2, cy - r_size/2, cx + r_size/2, cy + r_size/2,
                                     fill="#DDDDDD", outline="gray", dash=(4, 4))
        self.canvas.create_text(cx, cy - r_size/2 - 10, text=f"Reflector: {dims['lado_reflector']} mm x {dims['lado_reflector']} mm", fill="gray")

        # Dibujar elemento radiante (dos cuadrados unidos en forma de 8)
        # Cada lado es L = λ/4. Inclinados 45 grados para formar un diamante.
        L = dims['lado_elemento'] * scale
        # Puntos del "8"
        # El centro es donde se unen.
        # Cuadrado 1 (Izquierda)
        pts1 = [
            (cx, cy),
            (cx - L/math.sqrt(2), cy - L/math.sqrt(2)),
            (cx - 2*L/math.sqrt(2), cy),
            (cx - L/math.sqrt(2), cy + L/math.sqrt(2)),
            (cx, cy)
        ]
        # Cuadrado 2 (Derecha)
        pts2 = [
            (cx, cy),
            (cx + L/math.sqrt(2), cy - L/math.sqrt(2)),
            (cx + 2*L/math.sqrt(2), cy),
            (cx + L/math.sqrt(2), cy + L/math.sqrt(2)),
            (cx, cy)
        ]

        self.canvas.create_line(pts1, fill="#B87333", width=3) # Color cobre (hex)
        self.canvas.create_line(pts2, fill="#B87333", width=3)

        self.canvas.create_text(cx, cy + r_size/2 + 20,
                                text=f"Lado elemento: {dims['lado_elemento']} mm | Separación: {dims['separacion']} mm",
                                font=('Arial', 9, 'bold'))

if __name__ == "__main__":
    root = tk.Tk()
    app = BiquadApp(root)
    # Pequeño delay para que el canvas tenga dimensiones al dibujar la primera vez
    root.after(100, lambda: app.on_channel_selected())
    root.mainloop()

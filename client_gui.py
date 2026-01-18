# pyinstaller --noconsole --onefile --name="BroadcastClient" client_gui.py

import sys
import os
import json
import time
import threading
import logging
import io
import socket
import requests
from PIL import Image, ImageDraw

# GUI Imports
import customtkinter as ctk
import pystray
from pystray import MenuItem as Item

# --- THEME SETUP ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Farben
COLOR_BG_DARK = "#0f172a"      # Slate-950
COLOR_HEADER = "#1e293b"       # Slate-800
COLOR_ACCENT = "#06b6d4"       # Cyan-500
COLOR_ACCENT_HOVER = "#0891b2" # Cyan-600
COLOR_TEXT_MAIN = "#f1f5f9"    # Slate-100
COLOR_TEXT_DIM = "#94a3b8"     # Slate-400

CONFIG_FILENAME = 'client_config.json'
LAST_ID_FILENAME = 'last_id.txt'

# --- LOGGING SETUP (FIXED) ---
# Wir nutzen einen String-Buffer für das GUI-Fenster
LOG_STREAM = io.StringIO()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler explizit hinzufügen, statt basicConfig zu nutzen
# Damit umgehen wir Probleme, falls 'requests' das Logging blockiert
handler = logging.StreamHandler(LOG_STREAM)
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

class NetNotifyClient:
    def __init__(self):
        self.app_path = self.get_app_path()
        self.config = self.load_config()
        self.running = True
        self.icon = None
        self.last_seen_timestamp = 0.0
        self.hostname = socket.gethostname()
        
        self.root = ctk.CTk()
        self.root.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)

    # --- HELPER ---
    def get_app_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def get_file_path(self, filename):
        return os.path.join(self.app_path, filename)

    # --- CONFIG ---
    def load_config(self):
        config_path = self.get_file_path(CONFIG_FILENAME)
        default_config = {
            "server_ip": "127.0.0.1", 
            "server_port": 8080, 
            "check_interval": 5
        }
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    loaded = json.load(f)
                    for k, v in default_config.items():
                        if k not in loaded: loaded[k] = v
                    return loaded
            except: pass
        return default_config

    def save_config(self, new_conf):
        try:
            with open(self.get_file_path(CONFIG_FILENAME), 'w') as f:
                json.dump(new_conf, f, indent=4)
            self.config = new_conf
            logging.info(f"Config gespeichert. Intervall: {new_conf['check_interval']}s")
            return True
        except Exception as e:
            logging.error(f"Config Fehler: {e}")
            return False

    def get_last_seen_id(self):
        path = self.get_file_path(LAST_ID_FILENAME)
        if os.path.exists(path):
            try: return int(open(path).read().strip())
            except: return 0
        return 0

    def save_last_seen_id(self, msg_id):
        try:
            with open(self.get_file_path(LAST_ID_FILENAME), 'w') as f: f.write(str(msg_id))
            self.last_seen_id = msg_id
        except: pass

    # --- NETZWERK LOGIK ---
    def check_for_messages(self):
        logging.info(f"Client gestartet. Host: {self.hostname}")
        
        while self.running:
            start_time = time.time()
            current_interval = int(self.config.get('check_interval', 5))
            
            try:
                url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
                resp = requests.get(url, timeout=3)
                
                if resp.status_code == 200:
                    messages = resp.json()
                    
                    if messages:
                        # Sortieren: Älteste zuerst
                        messages.sort(key=lambda x: x['timestamp'])
                        
                        # Neue Nachrichten filtern
                        new_msgs = [m for m in messages if m['timestamp'] > self.last_seen_timestamp]
                        
                        
                        for msg in new_msgs:
                            logging.info(f"Neue Nachricht empfangen (Zeit: {msg['timestamp']})")
                            self.root.after(0, lambda m=msg: self.show_popup(m))
                            self.last_seen_timestamp = msg['timestamp']
                            self.save_last_seen_timestamp = msg ['timestamp']
                            
            except requests.exceptions.ConnectionError:
                pass # Still bleiben bei Verbindungsfehler
            except Exception as e:
                logging.error(f"Loop Fehler: {e}")

            # Smart Sleep
            while time.time() - start_time < current_interval and self.running:
                time.sleep(1)

    # --- GUI HELPER ---
    def center_window(self, window, w, h):
        ws = window.winfo_screenwidth()
        hs = window.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        window.geometry('%dx%d+%d+%d' % (w, h, x, y))

    # --- POPUP ALERT ---
    def show_popup(self, msg_data):
        win = ctk.CTkToplevel(self.root)
        win.title("NetNotify")
        w, h = 500, 300
        self.center_window(win, w, h)
        win.attributes('-topmost', True)
        win.resizable(False, False)
        
        # Header
        header = ctk.CTkFrame(win, height=50, corner_radius=0, fg_color=COLOR_HEADER)
        header.pack(fill="x")
        ctk.CTkFrame(win, height=2, corner_radius=0, fg_color=COLOR_ACCENT).pack(fill="x") # Akzentlinie
        
        lbl_title = ctk.CTkLabel(header, text="NEUE NACHRICHT", font=("Roboto Medium", 15), text_color=COLOR_ACCENT)
        lbl_title.place(relx=0.5, rely=0.5, anchor="center")
        
        # Inhalt
        content = ctk.CTkFrame(win, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=25, pady=20)
        
        ctk.CTkLabel(content, text=f"Zeitstempel: {msg_data.get('time', 'Jetzt')}", 
                     text_color=COLOR_TEXT_DIM, font=("Roboto", 11)).pack(anchor="w", pady=(0, 5))
        
        txt = ctk.CTkTextbox(content, font=("Roboto", 14), height=100, 
                             fg_color=COLOR_HEADER, text_color=COLOR_TEXT_MAIN, corner_radius=6)
        txt.insert("1.0", msg_data['message'])
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, pady=(0, 20))
        
        btn = ctk.CTkButton(content, text="Verstanden", 
                            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="black",
                            font=("Roboto", 12, "bold"), command=win.destroy)
        btn.pack(fill="x")
        
        win.focus_force()
        win.bell()

    # --- SETTINGS WINDOW ---
    def open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Einstellungen")
        self.center_window(win, 400, 480) # Etwas höher für den Reset Button
        win.grab_set()
        
        ctk.CTkLabel(win, text="Konfiguration", font=("Roboto Medium", 18), text_color=COLOR_TEXT_MAIN).pack(pady=20)
        
        frm = ctk.CTkFrame(win, fg_color="transparent")
        frm.pack(padx=30, fill="x")
        
        def create_input(label, key):
            ctk.CTkLabel(frm, text=label, text_color=COLOR_TEXT_DIM, font=("Roboto", 12)).pack(anchor="w", pady=(10,0))
            entry = ctk.CTkEntry(frm, fg_color=COLOR_HEADER, border_color="#334155")
            entry.insert(0, str(self.config.get(key, "")))
            entry.pack(fill="x", pady=(2, 0))
            return entry
            
        ent_ip = create_input("Server IP", "server_ip")
        ent_port = create_input("Server Port", "server_port")
        ent_int = create_input("Intervall (Sekunden)", "check_interval")
        
        status_lbl = ctk.CTkLabel(win, text="", font=("Roboto", 11))
        status_lbl.pack(pady=10)
        
        def save():
            try:
                new_int = int(ent_int.get())
                if new_int < 1: new_int = 1
                new_conf = {
                    "server_ip": ent_ip.get().strip(),
                    "server_port": int(ent_port.get()),
                    "check_interval": new_int
                }
                if self.save_config(new_conf):
                    status_lbl.configure(text="Gespeichert!", text_color=COLOR_ACCENT)
                    win.after(1000, win.destroy)
            except ValueError:
                status_lbl.configure(text="Ungültige Eingabe!", text_color="red")

        ctk.CTkButton(win, text="Speichern", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, 
                      text_color="black", command=save).pack(pady=10)

        # --- RESET FUNCTION ---
        ctk.CTkFrame(win, height=1, fg_color="#334155").pack(fill="x", padx=30, pady=15) # Trennlinie

        def reset_client():
            self.last_seen_id = 0
            self.save_last_seen_id(0)
            status_lbl.configure(text="Client zurückgesetzt! (ID=0)", text_color="orange")
            logging.warning("Benutzer hat Client-ID manuell zurückgesetzt.")

        ctk.CTkButton(win, text="Reset Nachrichten-ID", fg_color="#ef4444", hover_color="#dc2626", 
                      text_color="white", command=reset_client).pack(pady=(0, 20))


    # --- HISTORY WINDOW ---
    def open_history(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Verlauf")
        self.center_window(win, 600, 500)
        
        scroll = ctk.CTkScrollableFrame(win, width=550, height=400, fg_color="transparent")
        scroll.pack(padx=20, pady=20, fill="both", expand=True)
        
        try:
            url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
            msgs = requests.get(url, timeout=2).json()
            msgs.sort(key=lambda x: x['id'], reverse=True) # Neueste oben
            
            if not msgs: ctk.CTkLabel(scroll, text="Keine Nachrichten.").pack()
            
            for msg in msgs:
                card = ctk.CTkFrame(scroll, fg_color=COLOR_HEADER, corner_radius=8)
                card.pack(fill="x", pady=5)
                
                top = ctk.CTkFrame(card, fg_color="transparent", height=20)
                top.pack(fill="x", padx=10, pady=(10,0))
                ctk.CTkLabel(top, text=f"ID: {msg['id']}", font=("Roboto", 10, "bold"), text_color=COLOR_ACCENT).pack(side="left")
                ctk.CTkLabel(top, text=msg.get('time',''), font=("Roboto", 10), text_color=COLOR_TEXT_DIM).pack(side="right")
                
                ctk.CTkLabel(card, text=msg['message'], font=("Roboto", 13), text_color=COLOR_TEXT_MAIN, 
                             justify="left", anchor="w", wraplength=480).pack(padx=10, pady=(5,10), fill="x")
        except:
            ctk.CTkLabel(scroll, text="Verbindungsfehler", text_color="red").pack()

    # --- INFO / LOG WINDOW ---
    def open_info(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Logs")
        self.center_window(win, 600, 450)
        
        ctk.CTkLabel(win, text=f"Host: {self.hostname}", text_color=COLOR_TEXT_DIM).pack(pady=(10,5))
        
        # Log Box
        log_box = ctk.CTkTextbox(win, font=("Consolas", 11), fg_color="#000000", text_color="#22c55e") # Matrix Green
        log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Inhalt laden
        log_content = LOG_STREAM.getvalue()
        log_box.insert("1.0", log_content)
        log_box.see("end") # Auto-Scroll
        log_box.configure(state="disabled")

    # --- TRAY ---
    def create_tray(self):
        w, h = 64, 64
        img = Image.new('RGB', (w, h), (15, 23, 42)) 
        dc = ImageDraw.Draw(img)
        dc.rectangle((0,0,w,h), fill=(15, 23, 42))
        dc.ellipse((12, 12, 52, 52), fill=COLOR_ACCENT) 
        dc.text((22, 20), "N", fill="white", font_size=40)
        
        menu = pystray.Menu(
            Item('Verlauf', self.open_history),
            Item('Einstellungen', self.open_settings),
            Item('Logs', self.open_info),
            pystray.Menu.SEPARATOR,
            Item('Beenden', self.quit_app)
        )
        self.icon = pystray.Icon("NetNotify", img, "NetNotify", menu)
        self.icon.run()

    def quit_app(self):
        self.running = False
        if self.icon: self.icon.stop()
        self.root.quit()
        sys.exit()

    def run(self):
        threading.Thread(target=self.check_for_messages, daemon=True).start()
        threading.Thread(target=self.create_tray, daemon=True).start()
        self.root.mainloop()

if __name__ == "__main__":
    app = NetNotifyClient()
    app.run()
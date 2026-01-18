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

# Farben (Angepasst an dein Feedback & Website Theme)
COLOR_BG_DARK = "#0f172a"      # Slate-950 (Hintergrund)
COLOR_HEADER = "#1e293b"       # Slate-800 (Header Balken)
COLOR_ACCENT = "#06b6d4"       # Cyan-500 (Text Akzente, Button)
COLOR_ACCENT_HOVER = "#0891b2" # Cyan-600 (Button Hover)
COLOR_TEXT_MAIN = "#f1f5f9"    # Slate-100
COLOR_TEXT_DIM = "#94a3b8"     # Slate-400

CONFIG_FILENAME = 'client_config.json'
LAST_ID_FILENAME = 'last_id.txt'

# Logging Setup
LOG_STREAM = io.StringIO()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger()

class NetNotifyClient:
    def __init__(self):
        self.app_path = self.get_app_path()
        self.config = self.load_config()
        self.running = True
        self.icon = None
        self.last_seen_id = self.get_last_seen_id()
        self.hostname = socket.gethostname()
        
        # Ein unsichtbares Hauptfenster, damit Popups (Toplevels) funktionieren
        self.root = ctk.CTk()
        self.root.withdraw()
        # Verhindert, dass CMD+Q oder Schließen das Skript killt (wir nutzen Tray)
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
                    # Sicherstellen, dass alle Keys existieren (Merge defaults)
                    for k, v in default_config.items():
                        if k not in loaded: loaded[k] = v
                    return loaded
            except: pass
        return default_config

    def save_config(self, new_conf):
        try:
            with open(self.get_file_path(CONFIG_FILENAME), 'w') as f:
                json.dump(new_conf, f, indent=4)
            
            # WICHTIG: Config im laufenden Programm update
            self.config = new_conf
            logging.info(f"Config aktualisiert. Neues Intervall: {new_conf['check_interval']}s")
            return True
        except Exception as e:
            logging.error(f"Fehler beim Speichern: {e}")
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
        logging.info(f"Dienst gestartet. Polling alle {self.config['check_interval']}s")
        
        while self.running:
            # Dynamisches Intervall-Handling
            # Wir warten in 1-Sekunden-Schritten, damit Config-Änderungen schneller greifen
            start_time = time.time()
            current_interval = int(self.config.get('check_interval', 5))
            
            try:
                url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
                resp = requests.get(url, timeout=3)
                
                if resp.status_code == 200:
                    messages = resp.json()
                    
                    if messages:
                        # IDs extrahieren
                        server_ids = [m['id'] for m in messages]
                        max_server_id = max(server_ids)
                        
                        # --- FALLBACK / RESET ERKENNUNG ---
                        # Wenn die höchste ID auf dem Server KLEINER ist als das, was wir zuletzt gesehen haben,
                        # wurde die DB vermutlich geleert/resettet. Wir setzen unseren Zähler zurück.
                        if max_server_id < self.last_seen_id:
                            logging.warning("Server-Reset erkannt (Server ID < Client ID). Setze Client zurück.")
                            self.last_seen_id = 0
                            self.save_last_seen_id(0)

                        # Sortieren (Alt -> Neu)
                        messages.sort(key=lambda x: x['id'])
                        
                        # Neue Nachrichten filtern
                        new_msgs = [m for m in messages if m['id'] > self.last_seen_id]
                        
                        for msg in new_msgs:
                            logging.info(f"Nachricht ID {msg['id']} empfangen.")
                            # Thread-Safe GUI Aufruf
                            self.root.after(0, lambda m=msg: self.show_popup(m))
                            self.save_last_seen_id(msg['id'])
                            
            except requests.exceptions.ConnectionError:
                # Kein Log-Spam bei Verbindungsabbruch
                pass
            except Exception as e:
                logging.error(f"Fehler im Loop: {e}")

            # Smart Sleep: Wartet das Intervall ab, prüft aber sekündlich ob 'running' noch True ist
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
        
        # Design Update: Dunkler Header statt knallig Blau
        header = ctk.CTkFrame(win, height=50, corner_radius=0, fg_color=COLOR_HEADER)
        header.pack(fill="x")
        
        # Kleiner Cyan-Streifen als Akzent unten am Header
        accent_strip = ctk.CTkFrame(win, height=2, corner_radius=0, fg_color=COLOR_ACCENT)
        accent_strip.pack(fill="x")
        
        # Titel im Header
        lbl_title = ctk.CTkLabel(header, text="NEUE NACHRICHT", font=("Roboto Medium", 15), text_color=COLOR_ACCENT)
        lbl_title.place(relx=0.5, rely=0.5, anchor="center")
        
        # Inhalt
        content_frame = ctk.CTkFrame(win, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=25, pady=20)
        
        # Metadaten
        ctk.CTkLabel(content_frame, text=f"Zeitstempel: {msg_data.get('time', 'Jetzt')}", 
                     text_color=COLOR_TEXT_DIM, font=("Roboto", 11)).pack(anchor="w", pady=(0, 5))
        
        # Textbox (Read-only, sieht cleaner aus)
        txt = ctk.CTkTextbox(content_frame, font=("Roboto", 14), height=100, 
                             fg_color=COLOR_HEADER, text_color=COLOR_TEXT_MAIN, corner_radius=6)
        txt.insert("1.0", msg_data['message'])
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, pady=(0, 20))
        
        # Button
        btn = ctk.CTkButton(content_frame, text="Verstanden", 
                            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, 
                            text_color="#000000", # Schwarzer Text auf Cyan Button für Kontrast
                            font=("Roboto", 12, "bold"), command=win.destroy)
        btn.pack(fill="x")
        
        # Fokus erzwingen und Warnton
        win.focus_force()
        win.bell()

    # --- HISTORY WINDOW ---
    def open_history(self):
        win = ctk.CTkToplevel(self.root)
        win.title("NetNotify Verlauf")
        self.center_window(win, 600, 500)
        win.grab_set() # Fokus auf dieses Fenster
        
        ctk.CTkLabel(win, text="Nachrichtenverlauf", font=("Roboto Medium", 20), text_color=COLOR_TEXT_MAIN).pack(pady=20)
        
        scroll_frame = ctk.CTkScrollableFrame(win, width=550, height=400, fg_color="transparent")
        scroll_frame.pack(padx=20, pady=(0, 20), fill="both", expand=True)
        
        try:
            url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
            msgs = requests.get(url, timeout=2).json()
            
            if not msgs:
                ctk.CTkLabel(scroll_frame, text="Keine Nachrichten gefunden.", text_color=COLOR_TEXT_DIM).pack(pady=20)
            
            # Neueste oben sortieren
            for msg in sorted(msgs, key=lambda x: x['id'], reverse=True):
                # Karte für jede Nachricht
                card = ctk.CTkFrame(scroll_frame, fg_color=COLOR_HEADER, corner_radius=8)
                card.pack(fill="x", pady=6, padx=5)
                
                # Header der Karte
                top = ctk.CTkFrame(card, fg_color="transparent", height=20)
                top.pack(fill="x", padx=15, pady=(12,0))
                
                ctk.CTkLabel(top, text=f"ID: {msg['id']}", font=("Roboto", 11, "bold"), text_color=COLOR_ACCENT).pack(side="left")
                ctk.CTkLabel(top, text=msg.get('time', ''), font=("Roboto", 11), text_color=COLOR_TEXT_DIM).pack(side="right")
                
                # Inhalt der Karte
                ctk.CTkLabel(card, text=msg['message'], font=("Roboto", 13), 
                             text_color=COLOR_TEXT_MAIN, justify="left", wraplength=480, anchor="w").pack(padx=15, pady=(5, 15), fill="x")
                
        except Exception as e:
            ctk.CTkLabel(scroll_frame, text=f"Keine Verbindung zum Server.\n({e})", text_color="red").pack(pady=20)

    # --- SETTINGS WINDOW ---
    def open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Einstellungen")
        self.center_window(win, 400, 420)
        win.grab_set()
        
        ctk.CTkLabel(win, text="Konfiguration", font=("Roboto Medium", 18), text_color=COLOR_TEXT_MAIN).pack(pady=20)
        
        frm = ctk.CTkFrame(win, fg_color="transparent")
        frm.pack(padx=30, fill="x")
        
        def create_input(label, key, placeholder):
            ctk.CTkLabel(frm, text=label, text_color=COLOR_TEXT_DIM, font=("Roboto", 12)).pack(anchor="w", pady=(10,0))
            entry = ctk.CTkEntry(frm, fg_color=COLOR_HEADER, border_color="#334155")
            entry.insert(0, str(self.config.get(key, placeholder)))
            entry.pack(fill="x", pady=(2, 0))
            return entry
            
        ent_ip = create_input("Server IP Adresse", "server_ip", "127.0.0.1")
        ent_port = create_input("Server Port", "server_port", "8080")
        ent_int = create_input("Check Intervall (Sekunden)", "check_interval", "5")
        
        status_lbl = ctk.CTkLabel(win, text="", font=("Roboto", 11))
        status_lbl.pack(pady=10)
        
        def save():
            try:
                # Werte validieren
                new_interval = int(ent_int.get())
                if new_interval < 1: new_interval = 1
                
                new_conf = {
                    "server_ip": ent_ip.get().strip(),
                    "server_port": int(ent_port.get()),
                    "check_interval": new_interval
                }
                
                if self.save_config(new_conf):
                    status_lbl.configure(text="Gespeichert! Wird sofort angewendet.", text_color=COLOR_ACCENT)
                    win.after(1500, win.destroy)
                else:
                    status_lbl.configure(text="Fehler beim Speichern der Datei.", text_color="red")
            except ValueError:
                status_lbl.configure(text="Bitte gültige Zahlen für Port/Intervall eingeben.", text_color="red")

        ctk.CTkButton(win, text="Speichern & Anwenden", 
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="black",
                      font=("Roboto", 12, "bold"), command=save).pack(pady=10)

    # --- INFO WINDOW ---
    def open_info(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Status & Logs")
        self.center_window(win, 500, 450)
        
        ctk.CTkLabel(win, text="NetNotify Client", font=("Roboto Medium", 20), text_color=COLOR_ACCENT).pack(pady=(20, 5))
        
        info_txt = f"Host: {self.hostname} | Server: {self.config['server_ip']}:{self.config['server_port']}"
        ctk.CTkLabel(win, text=info_txt, font=("Roboto", 11), text_color=COLOR_TEXT_DIM).pack()

        log_box = ctk.CTkTextbox(win, font=("Consolas", 11), fg_color="#000000", text_color="#00ff00")
        log_box.pack(fill="both", expand=True, padx=20, pady=20)
        log_box.insert("1.0", LOG_STREAM.getvalue())
        log_box.see("end") # Auto-Scroll nach unten
        log_box.configure(state="disabled")

    # --- TRAY ICON ---
    def create_tray_icon(self):
        w, h = 64, 64
        image = Image.new('RGB', (w, h), (15, 23, 42)) 
        dc = ImageDraw.Draw(image)
        dc.rectangle((0,0,w,h), fill=(15, 23, 42))
        dc.ellipse((12, 12, 52, 52), fill=COLOR_ACCENT) 
        dc.text((22, 20), "N", fill="white", font_size=40)
        
        menu = pystray.Menu(
            Item('Nachrichtenverlauf', self.open_history),
            Item('Einstellungen', self.open_settings),
            Item('Status & Logs', self.open_info),
            pystray.Menu.SEPARATOR,
            Item('Beenden', self.quit_app)
        )
        self.icon = pystray.Icon("NetNotify", image, "NetNotify Client", menu)
        self.icon.run()

    def quit_app(self):
        self.running = False
        if self.icon: self.icon.stop()
        self.root.quit()
        sys.exit()

    def run(self):
        # Hintergrund-Thread starten
        t = threading.Thread(target=self.check_for_messages, daemon=True)
        t.start()
        
        # Tray Icon Thread
        t_tray = threading.Thread(target=self.create_tray_icon, daemon=True)
        t_tray.start()
        
        # GUI Loop
        self.root.mainloop()

if __name__ == "__main__":
    app = NetNotifyClient()
    app.run()
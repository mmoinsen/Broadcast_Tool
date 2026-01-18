import sys
import os
import json
import time
import threading
import logging
import io
import socket
import requests
import webbrowser
from PIL import Image, ImageDraw

# GUI Imports
import customtkinter as ctk
import pystray
from pystray import MenuItem as Item

# --- KONFIGURATION & THEME ---
# Wir nutzen das Farbschema deiner Website (Slate-950/Cyan)
ctk.set_appearance_mode("Dark")  # Dark Mode wie auf der Website
ctk.set_default_color_theme("blue")  # Cyan/Blue Akzente

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
        
        # --- GUI HAUPTFENSTER (Versteckt) ---
        # Wir brauchen EINE Hauptinstanz, die immer läuft, damit Toplevels funktionieren
        self.root = ctk.CTk()
        self.root.title("NetNotify Core")
        self.root.geometry("0x0")
        self.root.withdraw() # Hauptfenster unsichtbar machen
        
        # Sicherstellen, dass beim Schließen von Fenstern nicht die App beendet wird
        self.root.protocol("WM_DELETE_WINDOW", lambda: None) 

    # --- DATEI PFADE ---
    def get_app_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))

    def get_file_path(self, filename):
        return os.path.join(self.app_path, filename)

    # --- CONFIG ---
    def load_config(self):
        config_path = self.get_file_path(CONFIG_FILENAME)
        default_config = {"server_ip": "127.0.0.1", "server_port": 8080, "check_interval": 5}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f: return json.load(f)
            except: pass
        return default_config

    def save_config(self, new_conf):
        try:
            with open(self.get_file_path(CONFIG_FILENAME), 'w') as f:
                json.dump(new_conf, f, indent=4)
            self.config = new_conf
            logging.info("Konfiguration gespeichert.")
        except Exception as e:
            logging.error(f"Config Save Error: {e}")

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

    # --- NETZWERK LOOP ---
    def check_for_messages(self):
        logging.info(f"NetNotify gestartet auf {self.hostname}")
        
        while self.running:
            try:
                url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
                resp = requests.get(url, timeout=3)
                
                if resp.status_code == 200:
                    messages = resp.json()
                    messages.sort(key=lambda x: x['id'])
                    
                    new_msgs = [m for m in messages if m['id'] > self.last_seen_id]
                    
                    for msg in new_msgs:
                        logging.info(f"Neue Nachricht ID {msg['id']} empfangen.")
                        # WICHTIG: GUI Updates müssen im Main-Thread passieren via .after()
                        self.root.after(0, lambda m=msg: self.show_popup(m))
                        self.save_last_seen_id(msg['id'])
            except Exception as e:
                # Silent fail bei Verbindungsproblemen, um Logs nicht zu fluten
                pass
            
            for _ in range(self.config['check_interval']):
                if not self.running: return
                time.sleep(1)

    # --- GUI FENSTER ---
    
    def center_window(self, window, w, h):
        ws = window.winfo_screenwidth()
        hs = window.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        window.geometry('%dx%d+%d+%d' % (w, h, x, y))

    def show_popup(self, msg_data):
        # Modernes Popup Fenster
        win = ctk.CTkToplevel(self.root)
        win.title("NetNotify Alert")
        w, h = 450, 280
        self.center_window(win, w, h)
        win.attributes('-topmost', True)
        win.resizable(False, False)
        
        # Header (Cyan Akzent wie Website)
        header = ctk.CTkFrame(win, height=50, corner_radius=0, fg_color="#06b6d4") # Cyan-500
        header.pack(fill="x")
        
        lbl_title = ctk.CTkLabel(header, text="NEUE NACHRICHT", font=("Roboto Medium", 16), text_color="white")
        lbl_title.place(relx=0.5, rely=0.5, anchor="center")
        
        # Content
        content_frame = ctk.CTkFrame(win, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=20, pady=15)
        
        ctk.CTkLabel(content_frame, text=f"Empfangen: {msg_data.get('time', 'Jetzt')}", 
                     text_color="gray", font=("Roboto", 11)).pack(anchor="w")
        
        # Textbox (Read-only)
        txt = ctk.CTkTextbox(content_frame, font=("Roboto", 14), height=100, fg_color="#1e293b", text_color="#e2e8f0")
        txt.insert("1.0", msg_data['message'])
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, pady=(5, 15))
        
        # Button
        btn = ctk.CTkButton(content_frame, text="Verstanden", fg_color="#06b6d4", hover_color="#0891b2", 
                            font=("Roboto", 12, "bold"), command=win.destroy)
        btn.pack(fill="x")
        
        win.focus_force()

    def open_history(self):
        win = ctk.CTkToplevel(self.root)
        win.title("NetNotify Verlauf")
        self.center_window(win, 600, 500)
        
        ctk.CTkLabel(win, text="Nachrichtenverlauf", font=("Roboto Medium", 20)).pack(pady=20)
        
        scroll_frame = ctk.CTkScrollableFrame(win, width=550, height=400)
        scroll_frame.pack(padx=20, pady=(0, 20), fill="both", expand=True)
        
        try:
            url = f"http://{self.config['server_ip']}:{self.config['server_port']}/get_history"
            msgs = requests.get(url, timeout=2).json()
            if not msgs:
                ctk.CTkLabel(scroll_frame, text="Keine Nachrichten gefunden.").pack(pady=20)
            
            # Neueste oben
            for msg in sorted(msgs, key=lambda x: x['id'], reverse=True):
                card = ctk.CTkFrame(scroll_frame, fg_color="#1e293b", corner_radius=8) # Slate-800 Look
                card.pack(fill="x", pady=5, padx=5)
                
                top = ctk.CTkFrame(card, fg_color="transparent", height=20)
                top.pack(fill="x", padx=10, pady=(10,0))
                
                ctk.CTkLabel(top, text=f"ID: {msg['id']}", font=("Roboto", 10, "bold"), text_color="#06b6d4").pack(side="left")
                ctk.CTkLabel(top, text=msg.get('time', ''), font=("Roboto", 10), text_color="gray").pack(side="right")
                
                ctk.CTkLabel(card, text=msg['message'], font=("Roboto", 13), justify="left", wraplength=480).pack(padx=10, pady=(5, 10), anchor="w")
                
        except Exception as e:
            ctk.CTkLabel(scroll_frame, text=f"Verbindungsfehler: {e}", text_color="red").pack(pady=20)

    def open_settings(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Einstellungen")
        self.center_window(win, 400, 350)
        
        ctk.CTkLabel(win, text="Konfiguration", font=("Roboto Medium", 18)).pack(pady=20)
        
        frm = ctk.CTkFrame(win, fg_color="transparent")
        frm.pack(padx=30, fill="x")
        
        ctk.CTkLabel(frm, text="Server IP").pack(anchor="w")
        ent_ip = ctk.CTkEntry(frm, placeholder_text="127.0.0.1")
        ent_ip.insert(0, self.config['server_ip'])
        ent_ip.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(frm, text="Port").pack(anchor="w")
        ent_port = ctk.CTkEntry(frm, placeholder_text="8080")
        ent_port.insert(0, str(self.config['server_port']))
        ent_port.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(frm, text="Check Intervall (sek)").pack(anchor="w")
        ent_int = ctk.CTkEntry(frm)
        ent_int.insert(0, str(self.config['check_interval']))
        ent_int.pack(fill="x", pady=(0, 20))
        
        def save():
            try:
                new_conf = {
                    "server_ip": ent_ip.get(),
                    "server_port": int(ent_port.get()),
                    "check_interval": int(ent_int.get())
                }
                self.save_config(new_conf)
                win.destroy()
                # Hinweis: Neustart eigentlich nötig für Netzwerk-Thread-Änderungen
            except ValueError:
                pass # Simple error handling

        ctk.CTkButton(win, text="Speichern", fg_color="#06b6d4", hover_color="#0891b2", command=save).pack(pady=10)

    def open_info(self):
        win = ctk.CTkToplevel(self.root)
        win.title("NetNotify Status")
        self.center_window(win, 500, 400)
        
        ctk.CTkLabel(win, text="NetNotify Client v1.0", font=("Roboto Medium", 20), text_color="#06b6d4").pack(pady=(20, 5))
        ctk.CTkLabel(win, text=f"Host: {self.hostname} | App Path: {self.app_path}", font=("Roboto", 10), text_color="gray").pack()

        log_box = ctk.CTkTextbox(win, font=("Consolas", 10), fg_color="#0f172a")
        log_box.pack(fill="both", expand=True, padx=20, pady=20)
        log_box.insert("1.0", LOG_STREAM.getvalue())
        log_box.configure(state="disabled")

    # --- TRAY ICON ---
    def create_tray_icon(self):
        # Erstelle ein einfaches Icon programmatisch
        w, h = 64, 64
        image = Image.new('RGB', (w, h), (15, 23, 42)) # Slate-950 Background
        dc = ImageDraw.Draw(image)
        dc.rectangle((0,0,w,h), fill=(15, 23, 42))
        dc.ellipse((10, 10, 54, 54), fill="#06b6d4") # Cyan Circle
        dc.text((22, 20), "N", fill="white", font_size=40) # Simple 'N'
        
        menu = pystray.Menu(
            Item('Verlauf anzeigen', self.open_history),
            Item('Einstellungen', self.open_settings),
            Item('Status & Logs', self.open_info),
            pystray.Menu.SEPARATOR,
            Item('Beenden', self.quit_app)
        )
        self.icon = pystray.Icon("NetNotify", image, "NetNotify Client", menu)
        self.icon.run() # Dies blockiert den Thread, in dem es läuft

    def quit_app(self):
        self.running = False
        if self.icon: self.icon.stop()
        self.root.quit()
        sys.exit()

    def run(self):
        # 1. Netzwerk-Polling im Hintergrund starten
        t = threading.Thread(target=self.check_for_messages, daemon=True)
        t.start()
        
        # 2. Tray Icon in separatem Thread starten, damit Mainloop für GUI frei bleibt?
        # Leider braucht pystray oft den Main-Thread auf macOS. 
        # Trick: Wir nutzen CustomTkinter als Mainloop und starten Tray im Thread.
        
        t_tray = threading.Thread(target=self.create_tray_icon, daemon=True)
        t_tray.start()
        
        # 3. GUI Mainloop starten (hält das Programm am Leben und verarbeitet GUI Events)
        self.root.mainloop()

if __name__ == "__main__":
    app = NetNotifyClient()
    app.run()
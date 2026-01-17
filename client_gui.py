import sys
import os
import json
import time
import threading
import logging
import io
import socket
import requests
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as Item

# --- KONFIGURATION & GLOBALS ---
CONFIG_FILE = 'client_config.json'
LAST_ID_FILE = 'last_id.txt'
LOG_STREAM = io.StringIO() # Hier speichern wir Logs im Speicher für das Info-Fenster

# Logging konfigurieren (Konsole + Stream für GUI)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
stream_handler = logging.StreamHandler(LOG_STREAM)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(stream_handler)

class BroadcastClientApp:
    def __init__(self):
        self.config = self.load_config()
        self.running = True
        self.icon = None
        self.last_seen_id = self.get_last_seen_id()
        self.hostname = socket.gethostname()

    # --- HELPER: CONFIG & DATA ---
    def load_config(self):
        default_config = {
            "server_ip": "127.0.0.1",
            "server_port": 8000,
            "check_interval_seconds": 5
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Config Fehler: {e}")
        return default_config

    def save_config(self, new_conf):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(new_conf, f, indent=4)
            self.config = new_conf
            logging.info("Konfiguration gespeichert.")
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Config: {e}")

    def get_last_seen_id(self):
        if os.path.exists(LAST_ID_FILE):
            with open(LAST_ID_FILE, 'r') as f:
                try:
                    return int(f.read().strip())
                except:
                    return 0
        return 0

    def save_last_seen_id(self, msg_id):
        with open(LAST_ID_FILE, 'w') as f:
            f.write(str(msg_id))
        self.last_seen_id = msg_id

    # --- NETZWERK & LOGIK ---
    def get_server_url(self, endpoint="get_history"):
        return f"http://{self.config['server_ip']}:{self.config['server_port']}/{endpoint}"

    def check_for_messages(self):
        """Hintergrund-Loop zum Prüfen auf Nachrichten"""
        logging.info(f"Monitor gestartet. Intervall: {self.config['check_interval_seconds']}s")
        
        # Initialer Check (ohne Popup, nur um Startpunkt zu setzen, wenn gewünscht)
        # Hier könnte man Logik einbauen, um beim allerersten Start nicht zu spammen.
        
        while self.running:
            try:
                url = self.get_server_url()
                resp = requests.get(url, timeout=5)
                
                if resp.status_code == 200:
                    messages = resp.json()
                    messages.sort(key=lambda x: x['id']) # Älteste zuerst
                    
                    new_msgs = [m for m in messages if m['id'] > self.last_seen_id]
                    
                    for msg in new_msgs:
                        logging.info(f"Neue Nachricht empfangen (ID: {msg['id']})")
                        # GUI Popup aufrufen (im Main Thread Kontext sicherstellen via Helper)
                        self.show_popup_window(msg)
                        self.save_last_seen_id(msg['id'])
                        
                else:
                    logging.warning(f"Server Status: {resp.status_code}")
                    
            except requests.exceptions.ConnectionError:
                logging.error("Verbindung fehlgeschlagen (Server down?)")
            except Exception as e:
                logging.error(f"Fehler im Loop: {e}")
            
            # Warten
            for _ in range(self.config['check_interval_seconds']):
                if not self.running: break
                time.sleep(1)

    # --- GUI FENSTER ---
    
    def create_base_window(self, title, geometry="400x300"):
        """Erstellt ein sauberes Tkinter Fenster"""
        root = tk.Tk()
        root.title(title)
        # Fenster zentrieren
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = map(int, geometry.split('x'))
        x = (sw - w) // 2
        y = (sh - h) // 2
        root.geometry(f'{w}x{h}+{x}+{y}')
        
        # Styling
        style = ttk.Style()
        style.theme_use('clam') # Etwas moderner als Default
        root.configure(bg="#f4f7f6")
        return root

    def show_popup_window(self, msg_data):
        """Das cleane Popup bei neuer Nachricht"""
        # Da wir aus einem Thread kommen, nutzen wir eine separate Funktion
        # In komplexen Apps bräuchte man Queues, hier reicht ein eigener Tk-Loop für das Popup
        
        def run_popup():
            root = self.create_base_window("Neue Broadcast Nachricht", "500x350")
            root.attributes('-topmost', True) # Immer im Vordergrund
            root.overrideredirect(True) # Keine Titelleiste (Clean Look)
            
            # Rahmen für Design
            frame = tk.Frame(root, bg="white", bd=2, relief="raised")
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            
            # Header
            lbl_header = tk.Label(frame, text="NEUE NACHRICHT", font=("Segoe UI", 12, "bold"), bg="#3498db", fg="white", pady=10)
            lbl_header.pack(fill="x")
            
            # Zeit
            lbl_time = tk.Label(frame, text=f"Gesendet: {msg_data['time']}", font=("Segoe UI", 9), bg="white", fg="#888")
            lbl_time.pack(pady=(10, 0))
            
            # Nachricht (Scrollbar falls lang)
            txt_msg = tk.Text(frame, height=8, font=("Segoe UI", 11), bg="#f9f9f9", bd=0, wrap="word", padx=10, pady=10)
            txt_msg.insert("1.0", msg_data['message'])
            txt_msg.config(state="disabled") # Read-only
            txt_msg.pack(fill="both", expand=True, padx=20, pady=10)
            
            # OK Button
            btn_ok = tk.Button(frame, text="VERSTANDEN", bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"), 
                               relief="flat", padx=20, pady=8, command=root.destroy, cursor="hand2")
            btn_ok.pack(pady=15)
            
            # Hover Effekt für Button
            def on_enter(e): btn_ok['background'] = '#27ae60'
            def on_leave(e): btn_ok['background'] = '#2ecc71'
            btn_ok.bind("<Enter>", on_enter)
            btn_ok.bind("<Leave>", on_leave)

            root.mainloop()

        # Popup in eigenem Thread starten, damit der Check-Loop nicht blockiert
        t = threading.Thread(target=run_popup)
        t.start()

    def open_config_editor(self):
        def save():
            new_conf = {
                "server_ip": entry_ip.get(),
                "server_port": int(entry_port.get()),
                "check_interval_seconds": int(entry_interval.get())
            }
            self.save_config(new_conf)
            messagebox.showinfo("Erfolg", "Konfiguration gespeichert! Bitte starte das Programm neu, damit alles wirksam wird.")
            root.destroy()

        root = self.create_base_window("Einstellungen", "400x350")
        
        pad_opts = {'padx': 20, 'pady': 10}
        
        tk.Label(root, text="Server IP:", bg="#f4f7f6").pack(anchor="w", padx=20, pady=(20,0))
        entry_ip = ttk.Entry(root)
        entry_ip.insert(0, self.config['server_ip'])
        entry_ip.pack(fill="x", **pad_opts)
        
        tk.Label(root, text="Server Port:", bg="#f4f7f6").pack(anchor="w", padx=20)
        entry_port = ttk.Entry(root)
        entry_port.insert(0, str(self.config['server_port']))
        entry_port.pack(fill="x", **pad_opts)
        
        tk.Label(root, text="Intervall (Sekunden):", bg="#f4f7f6").pack(anchor="w", padx=20)
        entry_interval = ttk.Entry(root)
        entry_interval.insert(0, str(self.config['check_interval_seconds']))
        entry_interval.pack(fill="x", **pad_opts)
        
        ttk.Button(root, text="Speichern", command=save).pack(pady=20)
        root.mainloop()

    def open_history_window(self):
        root = self.create_base_window("Nachrichten Verlauf", "600x500")
        
        txt_area = scrolledtext.ScrolledText(root, font=("Segoe UI", 10))
        txt_area.pack(fill="both", expand=True, padx=10, pady=10)
        
        txt_area.insert(tk.END, "Lade Verlauf...\n")
        root.update()
        
        try:
            url = self.get_server_url()
            resp = requests.get(url, timeout=3)
            data = resp.json() # Kommt sortiert (neu -> alt) vom Server
            
            txt_area.delete('1.0', tk.END)
            if not data:
                txt_area.insert(tk.END, "Keine Nachrichten vorhanden.")
            
            for msg in data:
                entry = f"[{msg['time']}] (ID: {msg['id']})\n{msg['message']}\n{'-'*40}\n\n"
                txt_area.insert(tk.END, entry)
                
        except Exception as e:
            txt_area.insert(tk.END, f"\nFehler beim Laden: {e}")
            
        txt_area.config(state="disabled")
        root.mainloop()

    def open_info_window(self):
        root = self.create_base_window("Info & Logs", "500x400")
        
        # Info Bereich
        info_text = (f"Client Hostname: {self.hostname}\n"
                     f"Ziel Server: {self.config['server_ip']}:{self.config['server_port']}\n"
                     f"Status: {'Running' if self.running else 'Stopped'}")
        
        lbl_info = tk.Label(root, text=info_text, bg="#e8f6fe", justify="left", padx=10, pady=10, borderwidth=1, relief="solid")
        lbl_info.pack(fill="x", padx=10, pady=10)
        
        # Log Bereich
        tk.Label(root, text="System Logs:", bg="#f4f7f6").pack(anchor="w", padx=10)
        log_area = scrolledtext.ScrolledText(root, height=10, font=("Consolas", 9))
        log_area.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        # Logs aus dem StringStream holen
        log_content = LOG_STREAM.getvalue()
        log_area.insert(tk.END, log_content)
        log_area.see(tk.END) # Auto scroll to bottom
        log_area.config(state="disabled")
        
        root.mainloop()

    def exit_app(self):
        self.running = False
        if self.icon:
            self.icon.stop()
        sys.exit()

    # --- TRAY ICON SETUP ---
    def create_tray_image(self):
        # Erstellt ein einfaches Icon (Blauer Kreis mit weißem Punkt)
        w, h = 64, 64
        image = Image.new('RGB', (w, h), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0,0,w,h), fill=(255,255,255))
        dc.ellipse((8, 8, 56, 56), fill="#3498db")
        dc.ellipse((24, 24, 40, 40), fill="white")
        return image

    def run(self):
        # 1. Start Background Thread für Nachrichten
        t_poller = threading.Thread(target=self.check_for_messages, daemon=True)
        t_poller.start()
        
        # 2. Tray Icon erstellen und starten
        image = self.create_tray_image()
        menu = pystray.Menu(
            Item('Info & Logs', self.open_info_window),
            Item('Verlauf ansehen', self.open_history_window),
            Item('Einstellungen', self.open_config_editor),
            pystray.Menu.SEPARATOR,
            Item('Beenden', self.exit_app)
        )
        
        self.icon = pystray.Icon("BroadcastClient", image, "Broadcast Client", menu)
        logging.info("Client im System Tray gestartet.")
        self.icon.run()

if __name__ == "__main__":
    app = BroadcastClientApp()
    app.run()
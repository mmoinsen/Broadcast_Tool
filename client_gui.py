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

# --- GLOBALS ---
CONFIG_FILENAME = 'client_config.json'
LAST_ID_FILENAME = 'last_id.txt'

# Logging Setup (Speicher-Stream für GUI-Anzeige)
LOG_STREAM = io.StringIO()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()
stream_handler = logging.StreamHandler(LOG_STREAM)
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(stream_handler)

class BroadcastClientApp:
    def __init__(self):
        # WICHTIG: Pfad bestimmen (für exe oder script)
        self.app_path = self.get_app_path()
        
        self.config = self.load_config()
        self.running = True
        self.icon = None
        self.last_seen_id = self.get_last_seen_id()
        self.hostname = socket.gethostname()

    # --- PFAD LOGIK FÜR EXE ---
    def get_app_path(self):
        """Ermittelt den Pfad zur Datei, egal ob Script oder Exe"""
        if getattr(sys, 'frozen', False):
            # Wenn als exe gepackt (PyInstaller)
            return os.path.dirname(sys.executable)
        else:
            # Wenn als normales Python Script
            return os.path.dirname(os.path.abspath(__file__))

    def get_file_path(self, filename):
        """Hilfsfunktion um vollen Pfad zu einer Datei zu bekommen"""
        return os.path.join(self.app_path, filename)

    # --- CONFIG & DATA ---
    def load_config(self):
        config_path = self.get_file_path(CONFIG_FILENAME)
        default_config = {
            "server_ip": "127.0.0.1",
            "server_port": 8000,
            "check_interval_seconds": 5
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Config konnte nicht geladen werden: {e}")
        else:
            # Erstelle Default Config, falls nicht vorhanden
            try:
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
            except:
                pass 
                
        return default_config

    def save_config(self, new_conf):
        config_path = self.get_file_path(CONFIG_FILENAME)
        try:
            with open(config_path, 'w') as f:
                json.dump(new_conf, f, indent=4)
            self.config = new_conf
            logging.info(f"Konfiguration gespeichert in: {config_path}")
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Config: {e}")
            messagebox.showerror("Fehler", f"Konnte Config nicht speichern:\n{e}")

    def get_last_seen_id(self):
        path = self.get_file_path(LAST_ID_FILENAME)
        if os.path.exists(path):
            with open(path, 'r') as f:
                try:
                    return int(f.read().strip())
                except:
                    return 0
        return 0

    def save_last_seen_id(self, msg_id):
        path = self.get_file_path(LAST_ID_FILENAME)
        try:
            with open(path, 'w') as f:
                f.write(str(msg_id))
            self.last_seen_id = msg_id
        except Exception as e:
            logging.error(f"Konnte ID nicht speichern: {e}")

    # --- NETZWERK & LOGIK ---
    def get_server_url(self, endpoint="get_history"):
        return f"http://{self.config['server_ip']}:{self.config['server_port']}/{endpoint}"

    def check_for_messages(self):
        logging.info(f"Client gestartet. Host: {self.hostname}")
        logging.info(f"Prüfe Server {self.config['server_ip']} alle {self.config['check_interval_seconds']}s")
        
        while self.running:
            try:
                url = self.get_server_url()
                resp = requests.get(url, timeout=5)
                
                if resp.status_code == 200:
                    messages = resp.json()
                    # Server liefert Neueste zuerst -> Wir sortieren um (Alt -> Neu)
                    messages.sort(key=lambda x: x['id']) 
                    
                    new_msgs = [m for m in messages if m['id'] > self.last_seen_id]
                    
                    for msg in new_msgs:
                        logging.info(f"Neue Nachricht (ID: {msg['id']})")
                        self.show_popup_window(msg)
                        self.save_last_seen_id(msg['id'])
                        
                else:
                    logging.warning(f"Server Fehler: {resp.status_code}")
                    
            except requests.exceptions.ConnectionError:
                # Wir loggen das nicht jedes Mal als ERROR, sonst spammt das Log voll wenn Server aus ist
                # Nur Info, dass Verbindung weg ist
                pass
            except Exception as e:
                logging.error(f"Unbekannter Fehler im Loop: {e}")
            
            # Warten
            for _ in range(self.config['check_interval_seconds']):
                if not self.running: break
                time.sleep(1)

    # --- GUI HELPER ---
    def create_base_window(self, title, geometry="400x300"):
        root = tk.Tk()
        root.title(title)
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = map(int, geometry.split('x'))
        x = (sw - w) // 2
        y = (sh - h) // 2
        root.geometry(f'{w}x{h}+{x}+{y}')
        
        style = ttk.Style()
        style.theme_use('clam')
        root.configure(bg="#f4f7f6")
        
        # Icon für Fenster setzen (optional, falls Datei existiert)
        # try: root.iconbitmap(self.get_file_path("icon.ico"))
        # except: pass
        
        return root

    # --- POPUP ---
    def show_popup_window(self, msg_data):
        def run_popup():
            root = self.create_base_window("Broadcast", "500x350")
            root.attributes('-topmost', True)
            root.overrideredirect(True) 
            
            frame = tk.Frame(root, bg="white", bd=2, relief="raised")
            frame.pack(fill="both", expand=True, padx=2, pady=2)
            
            lbl_header = tk.Label(frame, text="NEUE NACHRICHT", font=("Segoe UI", 12, "bold"), bg="#3498db", fg="white", pady=10)
            lbl_header.pack(fill="x")
            
            lbl_time = tk.Label(frame, text=f"Gesendet: {msg_data['time']}", font=("Segoe UI", 9), bg="white", fg="#888")
            lbl_time.pack(pady=(10, 0))
            
            txt_msg = tk.Text(frame, height=8, font=("Segoe UI", 11), bg="#f9f9f9", bd=0, wrap="word", padx=10, pady=10)
            txt_msg.insert("1.0", msg_data['message'])
            txt_msg.config(state="disabled")
            txt_msg.pack(fill="both", expand=True, padx=20, pady=10)
            
            btn_ok = tk.Button(frame, text="VERSTANDEN", bg="#2ecc71", fg="white", font=("Segoe UI", 10, "bold"), 
                               relief="flat", padx=20, pady=8, command=root.destroy, cursor="hand2")
            btn_ok.pack(pady=15)
            
            # Button Hover
            btn_ok.bind("<Enter>", lambda e: btn_ok.config(bg='#27ae60'))
            btn_ok.bind("<Leave>", lambda e: btn_ok.config(bg='#2ecc71'))

            root.mainloop()

        t = threading.Thread(target=run_popup)
        t.start()

    # --- CONFIG EDITOR ---
    def open_config_editor(self):
        def save():
            new_conf = {
                "server_ip": entry_ip.get(),
                "server_port": int(entry_port.get()),
                "check_interval_seconds": int(entry_interval.get())
            }
            self.save_config(new_conf)
            messagebox.showinfo("Erfolg", "Gespeichert! Bitte App neu starten.")
            root.destroy()
            self.exit_app() # App beenden erzwingen, damit Neustart sauber ist

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
        
        tk.Label(root, text="Intervall (Sek):", bg="#f4f7f6").pack(anchor="w", padx=20)
        entry_interval = ttk.Entry(root)
        entry_interval.insert(0, str(self.config['check_interval_seconds']))
        entry_interval.pack(fill="x", **pad_opts)
        
        ttk.Button(root, text="Speichern & Beenden", command=save).pack(pady=20)
        root.mainloop()

    # --- HISTORY ---
    def open_history_window(self):
        root = self.create_base_window("Verlauf", "600x500")
        txt_area = scrolledtext.ScrolledText(root, font=("Segoe UI", 10))
        txt_area.pack(fill="both", expand=True, padx=10, pady=10)
        
        txt_area.insert(tk.END, "Lade Verlauf...\n")
        root.update()
        
        try:
            url = self.get_server_url()
            resp = requests.get(url, timeout=3)
            data = resp.json()
            
            txt_area.delete('1.0', tk.END)
            if not data:
                txt_area.insert(tk.END, "Keine Nachrichten.")
            
            for msg in data:
                entry = f"[{msg['time']}]\n{msg['message']}\n{'-'*40}\n\n"
                txt_area.insert(tk.END, entry)
        except Exception as e:
            txt_area.delete('1.0', tk.END)
            txt_area.insert(tk.END, f"Fehler: {e}")
            
        txt_area.config(state="disabled")
        root.mainloop()

    # --- INFO ---
    def open_info_window(self):
        root = self.create_base_window("Info & Logs", "500x400")
        
        info_text = (f"Hostname: {self.hostname}\n"
                     f"Ziel: {self.config['server_ip']}:{self.config['server_port']}\n"
                     f"App Pfad: {self.app_path}")
        
        lbl_info = tk.Label(root, text=info_text, bg="#e8f6fe", justify="left", padx=10, pady=10, relief="solid", bd=1)
        lbl_info.pack(fill="x", padx=10, pady=10)
        
        tk.Label(root, text="Logs:", bg="#f4f7f6").pack(anchor="w", padx=10)
        log_area = scrolledtext.ScrolledText(root, height=10, font=("Consolas", 8))
        log_area.pack(fill="both", expand=True, padx=10, pady=(0,10))
        
        log_content = LOG_STREAM.getvalue()
        log_area.insert(tk.END, log_content)
        log_area.see(tk.END)
        log_area.config(state="disabled")
        root.mainloop()

    def exit_app(self):
        self.running = False
        if self.icon: self.icon.stop()
        sys.exit()

    def create_tray_image(self):
        w, h = 64, 64
        image = Image.new('RGB', (w, h), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((0,0,w,h), fill=(255,255,255))
        dc.ellipse((8, 8, 56, 56), fill="#3498db")
        dc.ellipse((24, 24, 40, 40), fill="white")
        return image

    def run(self):
        t_poller = threading.Thread(target=self.check_for_messages, daemon=True)
        t_poller.start()
        
        image = self.create_tray_image()
        menu = pystray.Menu(
            Item('Info & Logs', self.open_info_window),
            Item('Verlauf', self.open_history_window),
            Item('Einstellungen', self.open_config_editor),
            pystray.Menu.SEPARATOR,
            Item('Beenden', self.exit_app)
        )
        
        self.icon = pystray.Icon("BroadcastClient", image, "Broadcast Client", menu)
        self.icon.run()

if __name__ == "__main__":
    app = BroadcastClientApp()
    app.run()
import time
import socket
import json
import requests
import os


def load_config():
    try:
        with open('client_config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Fehler: client_config.json nicht gefunden.")
        return None

def get_last_seen_id():
    if os.path.exists('last_id.txt'):
        with open('last_id.txt', 'r') as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 0
    return 0

def save_last_seen_id(msg_id):
    with open('last_id.txt', 'w') as f:
        f.write(str(msg_id))

# --- HAUPTPROGRAMM ---
def start_client():
    config = load_config()
    if not config:
        return

    hostname = socket.gethostname()
    
    server_url = f"{config['server_ip']}:{config['server_port']}/get_history"
    interval = config['check_interval_seconds']
    
    print(f"--- BROADCAST CLIENT ---")
    print(f"Client Name: {hostname}")
    print(f"Verbinde zu: {server_url}")
    print(f"Intervall: alle {interval} Sekunden")
    print("------------------------\n")

    
    last_seen_id = get_last_seen_id()
    
    
    if last_seen_id == 0 and not config.get('show_history_on_startup', True):
        try:
            print("Initialisierung... überspringe alte Nachrichten.")
            
            # WICHTIG: Hier timeout=5 ergänzen!
            resp = requests.get(server_url, timeout=5) 
            
            if resp.status_code == 200:
                data = resp.json()
                # Prüfen, ob überhaupt Daten da sind, sonst crasht max()
                if data and len(data) > 0:
                    max_id = max(msg['id'] for msg in data)
                    last_seen_id = max_id
                    save_last_seen_id(last_seen_id)
                    print(f"Initialisierung fertig. Start-ID gesetzt auf: {last_seen_id}")
                else:
                    print("Keine alten Nachrichten gefunden. Starte bei 0.")
            else:
                print(f"Warnung: Server antwortete mit Status {resp.status_code}")

        except requests.exceptions.ConnectionError:
            print(">> FEHLER: Server nicht erreichbar. Ist main.py gestartet?")
            print(">> Das Programm macht weiter, wird aber vermutlich gleich wieder Fehler werfen.")
        except Exception as e:
            print(f"Fehler bei Initialisierung: {e}")

    while True:
        try:
            response = requests.get(server_url, timeout=5)
            
            if response.status_code == 200:
                messages = response.json()
                
                
                messages.reverse()
                
                new_messages_found = False
                
                for msg in messages:
                    current_id = msg['id']
                    
                    
                    if current_id > last_seen_id:
                        print(f"\n[NEUE NACHRICHT] {msg['time']}")
                        print(f"Inhalt: {msg['message']}")
                        print("-" * 30)
                        
                        last_seen_id = current_id
                        new_messages_found = True
                
                
                if new_messages_found:
                    save_last_seen_id(last_seen_id)
            
            else:
                print(f"Server Fehler: Status {response.status_code}")

        except requests.exceptions.ConnectionError:
            print("Verbindung zum Server fehlgeschlagen... versuche es erneut.")
        except Exception as e:
            print(f"Ein Fehler ist aufgetreten: {e}")

        
        time.sleep(interval)

if __name__ == "__main__":
    start_client()
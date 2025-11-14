"""
Server web per il frontend dell'applicazione Medical Facial Analysis
Serve i file statici HTML/CSS/JS della webapp
"""

import http.server
import socketserver
import os
import webbrowser
import threading
import time

class WebHandler(http.server.SimpleHTTPRequestHandler):
    """Handler personalizzato per servire file statici"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="webapp", **kwargs)
    
    def end_headers(self):
        # Aggiungi headers per CORS se necessario
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

def find_free_port(start_port=3000, max_attempts=10):
    """Trova una porta libera per il server web"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
            return port
        except OSError:
            continue
    return None

def start_web_server():
    """Avvia il server web per il frontend"""
    try:
        # Cambia directory alla root del progetto
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Trova una porta libera
        port = find_free_port()
        if not port:
            print("❌ Nessuna porta disponibile nel range 3000-3009")
            return
        
        # Crea server HTTP
        with socketserver.TCPServer(("127.0.0.1", port), WebHandler) as httpd:
            url = f"http://127.0.0.1:{port}"
            
            print("🌐 Frontend Web Server Medical Facial Analysis")
            print("=" * 50)
            print(f"🚀 Server frontend avviato sulla porta {port}")
            print(f"🌍 Interfaccia web: {url}")
            print(f"📱 Applicazione: {url}/index.html")
            print("🛑 Premi Ctrl+C per fermare il server")
            print()
            
            # Funzione per aprire il browser dopo 2 secondi
            def open_browser():
                time.sleep(2)
                print(f"🔗 Apertura automatica browser: {url}")
                webbrowser.open(url)
            
            # Avvia thread per aprire browser
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
            
            # Avvia server
            print("📡 Server in ascolto...")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n🛑 Server web fermato dall'utente")
    except Exception as e:
        print(f"❌ Errore avvio server web: {e}")

if __name__ == "__main__":
    start_web_server()
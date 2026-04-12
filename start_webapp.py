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
import json
import base64
from urllib.parse import urlparse, parse_qs
import sys

# Aggiungi il percorso src per importare green_dots_processor
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from green_dots_processor import GreenDotsProcessor
    GREEN_DOTS_AVAILABLE = True
    print("✅ GreenDotsProcessor importato con successo")
except ImportError as e:
    print(f"❌ Warning: GreenDotsProcessor not available: {e}")
    GREEN_DOTS_AVAILABLE = False

class WebHandler(http.server.SimpleHTTPRequestHandler):
    """Handler personalizzato per servire file statici e gestire API eyebrow"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="webapp", **kwargs)
    
    def end_headers(self):
        # Aggiungi headers per CORS
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        # Disabilita cache per JS/CSS (forza reload modifiche)
        if self.path.endswith('.js') or self.path.endswith('.css'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Gestisce richieste OPTIONS per CORS"""
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        """Gestisce richieste POST per API eyebrow"""
        try:
            # Parse URL
            url_path = urlparse(self.path).path
            
            # Gestisci endpoint API eyebrow
            if url_path == '/api/eyebrow/left':
                self.handle_eyebrow_analysis('left')
            elif url_path == '/api/eyebrow/right':
                self.handle_eyebrow_analysis('right')
            else:
                # Endpoint non supportato
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': 'Endpoint non trovato'}
                self.wfile.write(json.dumps(response).encode())
                
        except Exception as e:
            print(f"❌ Errore POST: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'success': False, 'error': str(e)}
            self.wfile.write(json.dumps(response).encode())
    
    def handle_eyebrow_analysis(self, side):
        """Gestisce l'analisi del sopracciglio"""
        try:
            print(f"🔍 Iniziando analisi sopracciglio {side}")
            
            if not GREEN_DOTS_AVAILABLE:
                print("❌ GreenDotsProcessor non disponibile")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'success': False,
                    'side': side,
                    'error': 'Modulo GreenDotsProcessor non disponibile'
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Leggi dati POST
            content_length = int(self.headers['Content-Length'])
            print(f"📦 Content length: {content_length}")
            post_data = self.rfile.read(content_length)
            print(f"📝 Post data ricevuti: {len(post_data)} bytes")
            
            try:
                request_data = json.loads(post_data.decode())
                print(f"✅ JSON parsing completato")
            except json.JSONDecodeError as je:
                print(f"❌ Errore parsing JSON: {je}")
                raise ValueError(f"Dati JSON non validi: {je}")
            
            # Estrai immagine base64
            image_base64 = request_data.get('image', '')
            print(f"🖼️ Immagine base64 ricevuta: {len(image_base64)} caratteri")
            
            if not image_base64:
                print("❌ Nessuna immagine fornita")
                raise ValueError("Immagine non fornita")
            
            # Processa con GreenDotsProcessor
            print("🔧 Inizializzando GreenDotsProcessor...")
            processor = GreenDotsProcessor()
            print("✅ GreenDotsProcessor inizializzato")
            
            # Decodifica immagine
            from PIL import Image
            import io
            
            print("🔄 Decodificando immagine base64...")
            
            # Rimuovi prefisso data URL se presente
            if ',' in image_base64:
                image_base64 = image_base64.split(',')[1]
                print("🔗 Rimosso prefisso data URL")
            
            try:
                # Decodifica base64
                image_data = base64.b64decode(image_base64)
                print(f"📦 Immagine decodificata: {len(image_data)} bytes")
                
                pil_image = Image.open(io.BytesIO(image_data))
                print(f"🖼️ PIL Image caricata: {pil_image.size}, mode: {pil_image.mode}")
                
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                    print("🎨 Convertita in RGB")
            except Exception as img_error:
                print(f"❌ Errore decodifica immagine: {img_error}")
                raise ValueError(f"Errore decodifica immagine: {img_error}")
            
            # Processa immagine
            results = processor.process_pil_image(pil_image)
            
            if not results['success']:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'success': False,
                    'side': side,
                    'error': results.get('error', 'Errore processing')
                }
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Estrai dati del lato richiesto
            if side == 'left':
                eyebrow_dots = results['groups']['Sx']
                eyebrow_coordinates = results['coordinates']['Sx']
                eyebrow_statistics = results['statistics']['left']
                bbox = processor.get_left_eyebrow_bbox(0.5)
            else:  # right
                eyebrow_dots = results['groups']['Dx']
                eyebrow_coordinates = results['coordinates']['Dx']
                eyebrow_statistics = results['statistics']['right']
                bbox = processor.get_right_eyebrow_bbox(0.5)
            
            # Prepara risposta
            response_data = {
                'success': True,
                'side': side,
                'data': {
                    'dots': eyebrow_dots,
                    'coordinates': eyebrow_coordinates,
                    'statistics': eyebrow_statistics,
                    'bbox': {
                        'x_min': bbox[0],
                        'y_min': bbox[1],
                        'x_max': bbox[2],
                        'y_max': bbox[3]
                    }
                },
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S')
            }
            
            # Invia risposta
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Converti numpy types per JSON serialization
            def convert_numpy_types(obj):
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, dict):
                    return {key: convert_numpy_types(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(item) for item in obj]
                else:
                    return obj
            
            clean_response = convert_numpy_types(response_data)
            self.wfile.write(json.dumps(clean_response).encode())
            
            print(f"✅ Analisi sopracciglio {side} completata")
            
        except Exception as e:
            print(f"❌ Errore analisi sopracciglio {side}: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'success': False,
                'side': side,
                'error': str(e)
            }
            self.wfile.write(json.dumps(response).encode())

def find_free_port(start_port=3000, max_attempts=10):
    """Trova una porta libera per il server web"""
    import socket
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
            return port
        except OSError:
            continue
    return None

def start_web_server():
    """Avvia il server web per il frontend"""
    try:
        # Cambia directory alla root del progetto
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        # IMPORTANTE: usa sempre la porta 3000 come default
        # Non cercare altre porte (5000 è riservata per auth_server)
        # Se 3000 è occupata, c'è un vero conflitto da risolvere
        port = 3000

        # Verifica se la porta è disponibile
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
        except OSError:
            print(f"❌ ERRORE: La porta {port} è già in uso!")
            print(f"   auth_server.py usa la porta 5000")
            print(f"   webapp deve usare la porta 3000")
            print(f"   Per risolvere:")
            print(f"   1. Verifica processi: ps aux | grep -E '(python|node|java)'")
            print(f"   2. Cleanup server: python3 cleanup_servers.py force")
            print(f"   3. Riavvia: ./restart_all.sh")
            return
        
        # Crea server HTTP
        with socketserver.TCPServer(("0.0.0.0", port), WebHandler) as httpd:
            url = f"http://localhost:{port}"
            
            print("🌐 Frontend Web Server Medical Facial Analysis")
            print("=" * 50)
            print(f"🚀 Server frontend avviato sulla porta {port}")
            print(f"🌍 Interfaccia web: {url}")
            print(f"📱 Applicazione: {url}/index.html")
            print("🛑 Premi Ctrl+C per fermare il server")
            print()
            
            # ❌ DISABILITATO: Non aprire browser automaticamente quando avviato con nohup
            # Funzione per aprire il browser dopo 2 secondi
            # def open_browser():
            #     time.sleep(2)
            #     print(f"🔗 Apertura automatica browser: {url}")
            #     webbrowser.open(url)
            
            # Avvia thread per aprire browser
            # browser_thread = threading.Thread(target=open_browser, daemon=True)
            # browser_thread.start()
            
            # Avvia server
            print("📡 Server in ascolto...")
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n🛑 Server web fermato dall'utente")
    except Exception as e:
        print(f"❌ Errore avvio server web: {e}")

if __name__ == "__main__":
    start_web_server()
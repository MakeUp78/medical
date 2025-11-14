"""
Modulo di integrazione tra Canvas App e Webapp API
Gestisce l'invio dell'immagine corrente del canvas all'API per l'analisi
"""

import base64
import cv2
import numpy as np
import requests
import json
from typing import Dict, List, Optional, Any, Tuple
from io import BytesIO
from PIL import Image


class WebAppCanvasIntegration:
    """Classe per l'integrazione tra Canvas e Webapp API."""
    
    def __init__(self, api_base_url: str = "http://127.0.0.1:8001"):
        self.api_base_url = api_base_url
        self.session = requests.Session()
        
    def encode_image_to_base64(self, image: np.ndarray) -> str:
        """Converte un'immagine OpenCV in base64."""
        try:
            # Converti da BGR a RGB se necessario
            if len(image.shape) == 3 and image.shape[2] == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = image
            
            # Converti in PIL Image
            pil_image = Image.fromarray(image_rgb)
            
            # Salva in buffer come JPEG
            buffer = BytesIO()
            pil_image.save(buffer, format='JPEG', quality=95)
            
            # Converti in base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            return image_base64
            
        except Exception as e:
            print(f"Errore conversione immagine a base64: {e}")
            return ""
    
    def send_canvas_for_analysis(self, 
                               canvas_image: np.ndarray,
                               analysis_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Invia l'immagine del canvas all'API per l'analisi completa.
        
        Args:
            canvas_image: Immagine corrente del canvas (formato OpenCV)
            analysis_types: Lista dei tipi di analisi da eseguire
            
        Returns:
            Risultato dell'analisi dall'API
        """
        try:
            if canvas_image is None:
                return {"success": False, "error": "Nessuna immagine nel canvas"}
            
            # Codifica immagine in base64
            image_b64 = self.encode_image_to_base64(canvas_image)
            if not image_b64:
                return {"success": False, "error": "Errore codifica immagine"}
            
            # Prepara richiesta
            if analysis_types is None:
                analysis_types = [
                    "face_width", "face_height", "eye_distance", "nose_width", 
                    "mouth_width", "eyebrow_areas", "eye_areas", "facial_symmetry",
                    "cheek_width", "forehead_width", "chin_width", "face_profile",
                    "nose_angle", "mouth_angle", "face_proportions", "key_distances"
                ]
            
            payload = {
                "image": image_b64,
                "analysis_types": analysis_types
            }
            
            # Invia richiesta all'API
            url = f"{self.api_base_url}/api/canvas-analysis"
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {"success": True, "data": result}
            else:
                error_msg = f"Errore API: {response.status_code}"
                try:
                    error_detail = response.json().get("detail", "Errore sconosciuto")
                    error_msg += f" - {error_detail}"
                except:
                    pass
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            return {"success": False, "error": f"Errore connessione API: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Errore generico: {e}"}
    
    def apply_single_measurement(self, 
                               canvas_image: np.ndarray, 
                               measurement_type: str) -> Dict[str, Any]:
        """
        Applica una singola misurazione all'immagine del canvas.
        
        Args:
            canvas_image: Immagine corrente del canvas
            measurement_type: Tipo di misurazione da applicare
            
        Returns:
            Risultato della misurazione specifica
        """
        result = self.send_canvas_for_analysis(canvas_image, [measurement_type])
        
        if result["success"]:
            data = result["data"]
            # Filtra solo la misurazione richiesta
            measurements = data.get("measurements", [])
            filtered_measurements = [m for m in measurements if m["type"] == measurement_type]
            
            return {
                "success": True,
                "measurement": filtered_measurements[0] if filtered_measurements else None,
                "landmarks": data.get("landmarks", []),
                "session_id": data.get("session_id")
            }
        
        return result
    
    def get_facial_symmetry_analysis(self, canvas_image: np.ndarray) -> Dict[str, Any]:
        """Analisi specifica della simmetria facciale."""
        result = self.send_canvas_for_analysis(canvas_image, ["facial_symmetry"])
        
        if result["success"]:
            data = result["data"]
            return {
                "success": True,
                "symmetry_analysis": data.get("symmetry_analysis", {}),
                "pose_angles": data.get("pose_angles", {}),
                "frontality_score": data.get("frontality_score", 0.0),
                "landmarks": data.get("landmarks", [])
            }
        
        return result
    
    def get_all_measurements(self, canvas_image: np.ndarray) -> Dict[str, Any]:
        """Ottiene tutte le misurazioni disponibili."""
        return self.send_canvas_for_analysis(canvas_image)


class CanvasButtonIntegration:
    """Classe per integrare i pulsanti del canvas con l'API webapp."""
    
    def __init__(self, canvas_app, api_integration: WebAppCanvasIntegration):
        self.canvas_app = canvas_app
        self.api = api_integration
        
    def get_current_canvas_image(self) -> Optional[np.ndarray]:
        """Ottiene l'immagine corrente dal canvas."""
        try:
            # Prova diverse variabili per l'immagine corrente
            if hasattr(self.canvas_app, 'current_image_on_canvas') and self.canvas_app.current_image_on_canvas is not None:
                return self.canvas_app.current_image_on_canvas.copy()
            elif hasattr(self.canvas_app, 'current_image') and self.canvas_app.current_image is not None:
                return self.canvas_app.current_image.copy()
            elif hasattr(self.canvas_app, 'original_base_image') and self.canvas_app.original_base_image is not None:
                return self.canvas_app.original_base_image.copy()
            else:
                return None
        except Exception as e:
            print(f"Errore ottenimento immagine canvas: {e}")
            return None
    
    def enhanced_toggle_face_width(self):
        """Versione enhanced di toggle_face_width che usa l'API."""
        print("🚀 ENHANCED: toggle_face_width con API")
        
        # Ottieni immagine corrente
        canvas_image = self.get_current_canvas_image()
        if canvas_image is None:
            print("❌ Nessuna immagine nel canvas")
            return
        
        # Analizza tramite API
        result = self.api.apply_single_measurement(canvas_image, "face_width")
        
        if result["success"] and result["measurement"]:
            measurement = result["measurement"]
            print(f"✅ Larghezza volto: {measurement['value']:.2f} {measurement['unit']}")
            
            # Applica visualizzazione usando i metodi originali del canvas
            self.canvas_app.measure_face_width()
            
            # Aggiorna testo pulsante
            if self.canvas_app.preset_buttons.get("face_width"):
                self.canvas_app.preset_buttons["face_width"].config(text="Nascondi Larghezza Volto")
        else:
            print(f"❌ Errore analisi: {result.get('error', 'Sconosciuto')}")
            # Fallback al metodo originale
            self.canvas_app.toggle_face_width()
    
    def enhanced_toggle_facial_symmetry(self):
        """Versione enhanced di toggle_facial_symmetry che usa l'API."""
        print("🚀 ENHANCED: toggle_facial_symmetry con API")
        
        canvas_image = self.get_current_canvas_image()
        if canvas_image is None:
            print("❌ Nessuna immagine nel canvas")
            return
        
        # Analisi simmetria tramite API
        result = self.api.get_facial_symmetry_analysis(canvas_image)
        
        if result["success"]:
            symmetry_data = result["symmetry_analysis"]
            overall_score = symmetry_data.get("overall_score", 0.0)
            components = symmetry_data.get("symmetry_components", {})
            
            print(f"✅ Simmetria facciale: {overall_score:.3f}")
            print(f"   - Occhi: {components.get('eyes', 0):.3f}")
            print(f"   - Bocca: {components.get('mouth', 0):.3f}")
            print(f"   - Contorno: {components.get('face_outline', 0):.3f}")
            
            # Applica visualizzazione originale
            self.canvas_app.measure_facial_symmetry()
            
            # Aggiorna testo pulsante
            if self.canvas_app.preset_buttons.get("facial_symmetry"):
                self.canvas_app.preset_buttons["facial_symmetry"].config(text="Nascondi Simmetria")
        else:
            print(f"❌ Errore analisi simmetria: {result.get('error', 'Sconosciuto')}")
            # Fallback al metodo originale
            self.canvas_app.toggle_facial_symmetry()
    
    def enhanced_toggle_all_measurements(self):
        """Applica tutte le misurazioni contemporaneamente usando l'API."""
        print("🚀 ENHANCED: Analisi completa con API")
        
        canvas_image = self.get_current_canvas_image()
        if canvas_image is None:
            print("❌ Nessuna immagine nel canvas")
            return
        
        # Analisi completa tramite API
        result = self.api.get_all_measurements(canvas_image)
        
        if result["success"]:
            data = result["data"]
            measurements = data.get("measurements", [])
            
            print(f"✅ Analisi completa completata: {len(measurements)} misurazioni")
            
            # Applica tutte le visualizzazioni
            measurement_methods = {
                "face_width": self.canvas_app.measure_face_width,
                "face_height": self.canvas_app.measure_face_height,
                "eye_distance": self.canvas_app.measure_eye_distance,
                "nose_width": self.canvas_app.measure_nose_width,
                "mouth_width": self.canvas_app.measure_mouth_width,
                "facial_symmetry": self.canvas_app.measure_facial_symmetry,
            }
            
            # Applica le misurazioni disponibili
            for measurement in measurements:
                m_type = measurement["type"]
                if m_type in measurement_methods:
                    try:
                        measurement_methods[m_type]()
                        print(f"   ✓ {m_type}: {measurement['value']:.2f} {measurement['unit']}")
                    except Exception as e:
                        print(f"   ❌ Errore {m_type}: {e}")
            
            return {"success": True, "measurements": measurements}
        else:
            print(f"❌ Errore analisi completa: {result.get('error', 'Sconosciuto')}")
            return {"success": False, "error": result.get('error')}


def integrate_canvas_with_webapp(canvas_app, api_base_url: str = "http://127.0.0.1:8001"):
    """
    Integra il canvas app con la webapp API.
    
    Args:
        canvas_app: Istanza di CanvasApp
        api_base_url: URL base della webapp API
        
    Returns:
        Istanza di CanvasButtonIntegration per i pulsanti enhanced
    """
    api_integration = WebAppCanvasIntegration(api_base_url)
    button_integration = CanvasButtonIntegration(canvas_app, api_integration)
    
    # Salva riferimenti nell'app canvas per uso futuro
    canvas_app.webapp_integration = api_integration
    canvas_app.button_integration = button_integration
    
    return button_integration
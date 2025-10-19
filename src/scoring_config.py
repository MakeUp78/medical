"""
Configuration manager for scoring weights and parameters
"""
import json
import os


class ScoringConfig:
    """Configurazione dei pesi per l'algoritmo di scoring"""

    def __init__(self):
        # Pesi dei componenti (devono sommare a 1.0) - VALORI DEFAULT
        self.nose_weight = 0.30  # Peso naso centrato
        self.mouth_weight = 0.25  # Peso bocca centrata
        self.symmetry_weight = 0.25  # Peso simmetria generale
        self.eye_weight = 0.20  # Peso allineamento occhi

        # Parametri di tolleranza - VALORI DEFAULT
        self.nose_tolerance = 0.3  # Tolleranza deviazione naso (frazione di eye_distance)
        self.mouth_tolerance = 0.4  # Tolleranza deviazione bocca
        self.symmetry_tolerance = 0.7  # Tolleranza minima simmetria

        # Bonus roll - VALORI DEFAULT
        self.roll_bonus_high = 1.03  # Bonus per roll quasi perfetto (eye_score > 0.95)
        self.roll_bonus_med = 1.015  # Bonus per roll molto buono (eye_score > 0.90)

        # Penalità - VALORI DEFAULT
        self.penalty_threshold_nose = 0.4  # Soglia sotto cui penalizzare naso
        self.penalty_threshold_mouth = 0.4  # Soglia sotto cui penalizzare bocca
        self.penalty_threshold_symmetry = 0.6  # Soglia sotto cui penalizzare simmetria
        self.penalty_factor = 0.3  # Fattore di penalità

        # Callbacks per aggiornamenti in tempo reale
        self.on_weights_changed = None
        
        # Percorso file di configurazione
        self.config_file = "config.json"
        
        # CARICA AUTOMATICAMENTE I PARAMETRI SALVATI ALL'AVVIO
        self.load_from_config()

    def load_from_config(self):
        """Carica i parametri scoring dal file config.json se esiste."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Carica parametri scoring se esistono
                if 'scoring' in config_data:
                    scoring_config = config_data['scoring']
                    
                    # Carica pesi
                    self.nose_weight = scoring_config.get('nose_weight', self.nose_weight)
                    self.mouth_weight = scoring_config.get('mouth_weight', self.mouth_weight)
                    self.symmetry_weight = scoring_config.get('symmetry_weight', self.symmetry_weight)
                    self.eye_weight = scoring_config.get('eye_weight', self.eye_weight)
                    
                    # Carica tolleranze
                    self.nose_tolerance = scoring_config.get('nose_tolerance', self.nose_tolerance)
                    self.mouth_tolerance = scoring_config.get('mouth_tolerance', self.mouth_tolerance)
                    self.symmetry_tolerance = scoring_config.get('symmetry_tolerance', self.symmetry_tolerance)
                    
                    # Carica bonus
                    self.roll_bonus_high = scoring_config.get('roll_bonus_high', self.roll_bonus_high)
                    self.roll_bonus_med = scoring_config.get('roll_bonus_med', self.roll_bonus_med)
                    
                    # Carica penalità
                    self.penalty_threshold_nose = scoring_config.get('penalty_threshold_nose', self.penalty_threshold_nose)
                    self.penalty_threshold_mouth = scoring_config.get('penalty_threshold_mouth', self.penalty_threshold_mouth)
                    self.penalty_threshold_symmetry = scoring_config.get('penalty_threshold_symmetry', self.penalty_threshold_symmetry)
                    self.penalty_factor = scoring_config.get('penalty_factor', self.penalty_factor)
                    
                    print(f"📁 Parametri scoring caricati da {self.config_file}")
                    print(f"   Pesi: N={self.nose_weight:.2f} B={self.mouth_weight:.2f} S={self.symmetry_weight:.2f} O={self.eye_weight:.2f}")
                else:
                    print(f"📁 Sezione 'scoring' non trovata in {self.config_file}, uso valori default")
            else:
                print(f"📁 File {self.config_file} non trovato, uso valori default")
                
        except Exception as e:
            print(f"⚠️ Errore nel caricamento parametri scoring: {e}")
            print("📁 Uso valori default")

    def save_to_config(self):
        """Salva i parametri scoring correnti nel file config.json."""
        try:
            # Carica la configurazione esistente o crea una nuova
            config_data = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            
            # Aggiorna/crea la sezione scoring
            config_data['scoring'] = {
                'nose_weight': self.nose_weight,
                'mouth_weight': self.mouth_weight,
                'symmetry_weight': self.symmetry_weight,
                'eye_weight': self.eye_weight,
                'nose_tolerance': self.nose_tolerance,
                'mouth_tolerance': self.mouth_tolerance,
                'symmetry_tolerance': self.symmetry_tolerance,
                'roll_bonus_high': self.roll_bonus_high,
                'roll_bonus_med': self.roll_bonus_med,
                'penalty_threshold_nose': self.penalty_threshold_nose,
                'penalty_threshold_mouth': self.penalty_threshold_mouth,
                'penalty_threshold_symmetry': self.penalty_threshold_symmetry,
                'penalty_factor': self.penalty_factor
            }
            
            # Salva il file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Parametri scoring salvati in {self.config_file}")
            print(f"   Pesi: N={self.nose_weight:.2f} B={self.mouth_weight:.2f} S={self.symmetry_weight:.2f} O={self.eye_weight:.2f}")
            
        except Exception as e:
            print(f"⚠️ Errore nel salvataggio parametri scoring: {e}")

    def set_callback(self, callback):
        """Imposta la callback per i cambiamenti"""
        self.on_weights_changed = callback

    def set_weights(self, nose=None, mouth=None, symmetry=None, eye=None):
        """Imposta i pesi normalizzando automaticamente"""
        if nose is not None:
            self.nose_weight = nose
        if mouth is not None:
            self.mouth_weight = mouth
        if symmetry is not None:
            self.symmetry_weight = symmetry
        if eye is not None:
            self.eye_weight = eye

        # Normalizza i pesi per sommare a 1.0
        total = (
            self.nose_weight
            + self.mouth_weight
            + self.symmetry_weight
            + self.eye_weight
        )
        if total > 0:
            self.nose_weight /= total
            self.mouth_weight /= total
            self.symmetry_weight /= total
            self.eye_weight /= total

        # SALVA AUTOMATICAMENTE quando cambiano i pesi
        self.save_to_config()

        # Notifica cambio
        if self.on_weights_changed:
            self.on_weights_changed()

    def get_weights_dict(self):
        """Ritorna i pesi come dizionario"""
        return {
            "nose": self.nose_weight,
            "mouth": self.mouth_weight,
            "symmetry": self.symmetry_weight,
            "eye": self.eye_weight,
        }

    def set_tolerances(self, nose_tol=None, mouth_tol=None, symmetry_tol=None):
        """Imposta le tolleranze"""
        if nose_tol is not None:
            self.nose_tolerance = nose_tol
        if mouth_tol is not None:
            self.mouth_tolerance = mouth_tol
        if symmetry_tol is not None:
            self.symmetry_tolerance = symmetry_tol

        # SALVA AUTOMATICAMENTE quando cambiano le tolleranze
        self.save_to_config()

        if self.on_weights_changed:
            self.on_weights_changed()

    def set_nose_weight(self, weight):
        """Imposta il peso del naso"""
        self.set_weights(nose=weight)

    def set_mouth_weight(self, weight):
        """Imposta il peso della bocca"""
        self.set_weights(mouth=weight)

    def set_symmetry_weight(self, weight):
        """Imposta il peso della simmetria"""
        self.set_weights(symmetry=weight)

    def set_eye_weight(self, weight):
        """Imposta il peso degli occhi"""
        self.set_weights(eye=weight)

    def set_penalty_thresholds(self, nose_threshold=None, mouth_threshold=None, symmetry_threshold=None):
        """Imposta le soglie di penalità"""
        if nose_threshold is not None:
            self.penalty_threshold_nose = nose_threshold
        if mouth_threshold is not None:
            self.penalty_threshold_mouth = mouth_threshold
        if symmetry_threshold is not None:
            self.penalty_threshold_symmetry = symmetry_threshold

        # SALVA AUTOMATICAMENTE quando cambiano le soglie
        self.save_to_config()

        if self.on_weights_changed:
            self.on_weights_changed()

    def set_nose_threshold(self, threshold):
        """Imposta la soglia di penalità del naso"""
        self.set_penalty_thresholds(nose_threshold=threshold)

    def set_mouth_threshold(self, threshold):
        """Imposta la soglia di penalità della bocca"""
        self.set_penalty_thresholds(mouth_threshold=threshold)

    def set_symmetry_threshold(self, threshold):
        """Imposta la soglia di penalità della simmetria"""
        self.set_penalty_thresholds(symmetry_threshold=threshold)

    def __str__(self):
        """Rappresentazione stringa per debug"""
        return (
            f"ScoringConfig: Naso={self.nose_weight:.2f}, "
            f"Bocca={self.mouth_weight:.2f}, "
            f"Simmetria={self.symmetry_weight:.2f}, "
            f"Occhi={self.eye_weight:.2f}"
        )


# Istanza globale per la configurazione
scoring_config = ScoringConfig()

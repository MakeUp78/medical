"""
Configuration manager for scoring weights and parameters
"""


class ScoringConfig:
    """Configurazione dei pesi per l'algoritmo di scoring"""

    def __init__(self):
        # Pesi dei componenti (devono sommare a 1.0)
        self.nose_weight = 0.30  # Peso naso centrato
        self.mouth_weight = 0.25  # Peso bocca centrata
        self.symmetry_weight = 0.25  # Peso simmetria generale
        self.eye_weight = 0.20  # Peso allineamento occhi

        # Parametri di tolleranza
        self.nose_tolerance = (
            0.3  # Tolleranza deviazione naso (frazione di eye_distance)
        )
        self.mouth_tolerance = 0.4  # Tolleranza deviazione bocca
        self.symmetry_tolerance = 0.7  # Tolleranza minima simmetria

        # Bonus roll
        self.roll_bonus_high = 1.03  # Bonus per roll quasi perfetto (eye_score > 0.95)
        self.roll_bonus_med = 1.015  # Bonus per roll molto buono (eye_score > 0.90)

        # Penalità
        self.penalty_threshold_nose = 0.4  # Soglia sotto cui penalizzare naso
        self.penalty_threshold_mouth = 0.4  # Soglia sotto cui penalizzare bocca
        self.penalty_threshold_symmetry = 0.6  # Soglia sotto cui penalizzare simmetria
        self.penalty_factor = 0.3  # Fattore di penalità

        # Callbacks per aggiornamenti in tempo reale
        self.on_weights_changed = None

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

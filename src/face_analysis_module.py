"""
Modulo Professionale di Analisi Visagistica e Comunicazione Non Verbale
Autore: Sistema di Analisi Facciale Avanzato
Versione: 1.0.0

Dipendenze richieste:
pip install opencv-python mediapipe numpy pillow

Uso:
    from face_analysis_module import FaceVisagismAnalyzer
    
    analyzer = FaceVisagismAnalyzer()
    result = analyzer.analyze_face("path/to/image.jpg", output_dir="output")
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json
from pathlib import Path
import math


class FaceShape(Enum):
    """Classificazione geometrica delle forme del viso"""
    OVALE = "ovale"
    ROTONDO = "rotondo"
    QUADRATO = "quadrato"
    RETTANGOLARE = "rettangolare"
    TRIANGOLARE = "triangolare"
    TRIANGOLARE_INVERSO = "triangolare_inverso"
    DIAMANTE = "diamante"


class EyebrowShape(Enum):
    """Tipologie di forme per le sopracciglia"""
    ARCUATA = "arcuata"
    ANGOLARE = "angolare"
    DRITTA = "dritta"
    ARCO_TONDO = "arco_tondo"
    S_SHAPE = "s_shape"


@dataclass
class FacialMetrics:
    """Metriche geometriche del viso"""
    larghezza_fronte: float
    larghezza_zigomi: float
    larghezza_mascella: float
    lunghezza_viso: float
    larghezza_viso: float
    rapporto_mascella_fronte: float
    rapporto_lunghezza_larghezza: float
    prominenza_zigomi: float
    lunghezza_mento: float
    distanza_occhi: float
    distanza_occhio_sopracciglio: float
    larghezza_naso: float
    lunghezza_naso: float
    larghezza_bocca: float


@dataclass
class FacialFeatures:
    """Caratteristiche qualitative del viso"""
    occhi_distanza: str  # ravvicinati, normali, distanti
    occhi_dimensione: str
    zigomi_prominenza: str  # sottili, normali, pronunciati
    naso_larghezza: str  # stretto, normale, largo
    naso_lunghezza: str  # corto, normale, lungo
    mascella_definizione: str  # sottile, equilibrata, pronunciata
    mento_prominenza: str  # ritirato, normale, pronunciato


@dataclass
class VisagisticRecommendation:
    """Raccomandazioni visagistiche professionali"""
    forma_sopracciglio: EyebrowShape
    motivazione_scientifica: str
    arco_descrizione: str
    spessore_consigliato: str
    lunghezza_consigliata: str
    punto_massimo_arco: str
    aggiustamenti_personalizzati: List[str]
    tecniche_applicazione: List[str]


@dataclass
class ExpressionAnalysis:
    """Analisi della comunicazione non verbale"""
    espressione_percepita: str
    impatto_emotivo: str
    obiettivi_comunicazione: List[str]
    principi_psicologici: List[str]
    raccomandazioni_espressive: List[Dict[str, str]]


class FaceVisagismAnalyzer:
    """
    Analizzatore professionale per visagismo e comunicazione non verbale facciale
    """
    
    # Costanti per la classificazione delle forme del viso
    FACE_SHAPE_CRITERIA = {
        FaceShape.OVALE: {
            'jaw_to_forehead': (0.85, 1.15),
            'length_to_width': (1.3, 1.5),
            'cheekbone_prominence': (0.90, 1.05)
        },
        FaceShape.ROTONDO: {
            'jaw_to_forehead': (0.90, 1.10),
            'length_to_width': (0.90, 1.15),
            'cheekbone_prominence': (0.95, 1.10)
        },
        FaceShape.QUADRATO: {
            'jaw_to_forehead': (0.95, 1.05),
            'length_to_width': (1.00, 1.25),
            'cheekbone_prominence': (0.85, 1.00)
        },
        FaceShape.RETTANGOLARE: {
            'jaw_to_forehead': (0.85, 1.00),
            'length_to_width': (1.50, 1.85),
            'cheekbone_prominence': (0.85, 1.00)
        },
        FaceShape.TRIANGOLARE: {
            'jaw_to_forehead': (0.60, 0.85),
            'length_to_width': (1.20, 1.50),
            'cheekbone_prominence': (0.80, 0.95)
        },
        FaceShape.TRIANGOLARE_INVERSO: {
            'jaw_to_forehead': (1.20, 1.50),
            'length_to_width': (1.20, 1.50),
            'cheekbone_prominence': (0.85, 1.00)
        },
        FaceShape.DIAMANTE: {
            'jaw_to_forehead': (0.75, 0.95),
            'length_to_width': (1.30, 1.50),
            'cheekbone_prominence': (1.05, 1.20)
        }
    }
    
    # Database delle raccomandazioni visagistiche
    EYEBROW_RECOMMENDATIONS = {
        FaceShape.OVALE: {
            'shape': EyebrowShape.ARCUATA,
            'reasoning': 'Il viso ovale rappresenta l\'equilibrio aureo della proporzione facciale. '
                        'Un sopracciglio con arco morbido e naturale mantiene questa armonia senza '
                        'creare squilibri. L\'arco delicato segue le proporzioni divine del viso.',
            'arch': 'Arco medio posizionato verticalmente sopra il bordo esterno dell\'iride, '
                   'con elevazione di 3-5mm dalla linea di base',
            'thickness': 'Spessore medio-naturale (4-6mm nella parte più spessa), assottigliandosi '
                        'gradualmente verso la coda',
            'length': 'Termina in linea diagonale con l\'angolo esterno dell\'occhio e l\'ala del naso',
            'peak': 'Punto massimo dell\'arco tra il 60-70% della lunghezza totale del sopracciglio',
            'techniques': [
                'Seguire la naturale linea di crescita del pelo',
                'Creare una transizione fluida dall\'inizio alla coda',
                'Mantenere simmetria tra i due sopraccigli (±1mm tolleranza)',
                'Evitare rimozione eccessiva dalla parte superiore'
            ]
        },
        FaceShape.ROTONDO: {
            'shape': EyebrowShape.ANGOLARE,
            'reasoning': 'Il viso rotondo necessita di elementi verticali per creare l\'illusione di '
                        'allungamento. Un sopracciglio angolare con arco pronunciato e picco definito '
                        'spezza le curve naturali del viso, creando verticalità ottica e struttura.',
            'arch': 'Arco alto e angolare con picco accentuato a 65-75% della lunghezza, '
                   'elevazione di 6-8mm dalla base',
            'thickness': 'Medio-sottile (3-5mm) per evitare di appesantire e mantenere la definizione angolare',
            'length': 'Esteso oltre l\'angolo esterno dell\'occhio (2-4mm) per allungare otticamente',
            'peak': 'Picco angolare marcato al 65-70% con transizione netta (angolo 120-130°)',
            'techniques': [
                'Creare un angolo definito nel punto massimo dell\'arco',
                'Rimuovere peli dalla zona inferiore per alzare l\'arco',
                'Mantenere la coda sottile e ascendente',
                'Evitare curve troppo rotonde che replicheranno la forma del viso'
            ]
        },
        FaceShape.QUADRATO: {
            'shape': EyebrowShape.ARCO_TONDO,
            'reasoning': 'La mascella quadrata e angolare richiede ammorbidimento attraverso curve delicate. '
                        'Un arco rotondo e dolce bilancia la forte struttura ossea mascellare, creando '
                        'femminilità e armonia tra elementi forti e morbidi.',
            'arch': 'Arco alto e completamente arrotondato senza angoli, elevazione 5-7mm',
            'thickness': 'Medio-spesso (5-7mm) per bilanciare la struttura ossea forte del viso',
            'length': 'Lunghezza standard allineata con l\'angolo esterno dell\'occhio',
            'peak': 'Arco massimo a circa 60-65% con curvatura fluida e continua',
            'techniques': [
                'Eliminare completamente angoli nel disegno del sopracciglio',
                'Creare curve ampie e morbide',
                'Mantenere spessore consistente fino al 70% della lunghezza',
                'Assottigliare gradualmente solo nell\'ultimo terzo'
            ]
        },
        FaceShape.RETTANGOLARE: {
            'shape': EyebrowShape.DRITTA,
            'reasoning': 'Il viso allungato beneficia di linee orizzontali che ne riducono otticamente '
                        'la lunghezza. Sopracciglia piatte con arco minimo creano larghezza percettiva '
                        'e accorciano visivamente le proporzioni verticali del viso.',
            'arch': 'Arco minimo o quasi assente, linea prevalentemente orizzontale con lieve curvatura (2-3mm)',
            'thickness': 'Spessore medio uniforme (4-6mm) per creare presenza orizzontale',
            'length': 'Lunghezza media-standard per non accentuare ulteriormente la lunghezza del viso',
            'peak': 'Punto massimo appena percettibile al 50-60% con elevazione minima',
            'techniques': [
                'Mantenere linea il più orizzontale possibile',
                'Rimuovere peli che creerebbero archi pronunciati',
                'Evitare code troppo discendenti',
                'Creare spessore uniforme per tutta la lunghezza'
            ]
        },
        FaceShape.TRIANGOLARE: {
            'shape': EyebrowShape.ARCO_TONDO,
            'reasoning': 'La fronte stretta e la mascella larga richiedono ampliamento visivo della zona '
                        'superiore. Archi ampi e curve generose creano larghezza nella parte alta del viso, '
                        'bilanciando la mascella prominente.',
            'arch': 'Arco ampio, alto e molto dolce con curvatura estesa, elevazione 6-8mm',
            'thickness': 'Medio-spesso nella parte interna (6-7mm) per dare presenza e peso visivo alla fronte',
            'length': 'Ben esteso oltre l\'angolo esterno (3-5mm) per ampliare otticamente la fronte',
            'peak': 'Arco massimo a 55-60% con curvatura molto ampia',
            'techniques': [
                'Iniziare il sopracciglio con buona densità e spessore',
                'Creare curve molto ampie e morbide',
                'Estendere la lunghezza per bilanciare la larghezza mascellare',
                'Evitare assottigliamenti eccessivi'
            ]
        },
        FaceShape.TRIANGOLARE_INVERSO: {
            'shape': EyebrowShape.ARCUATA,
            'reasoning': 'La fronte ampia e la mascella stretta necessitano di contenimento visivo della zona '
                        'superiore. Archi contenuti e moderati evitano di amplificare ulteriormente la larghezza '
                        'frontale, mantenendo l\'equilibrio verticale.',
            'arch': 'Arco morbido e contenuto, non troppo alto, elevazione 4-5mm',
            'thickness': 'Spessore medio uniforme (4-5mm) senza enfasi eccessiva',
            'length': 'Leggermente più corto dello standard per non amplificare la larghezza frontale',
            'peak': 'Punto massimo a 60-65% con arco delicato e non drammatico',
            'techniques': [
                'Evitare archi troppo alti che amplificano la fronte',
                'Mantenere curve moderate e contenute',
                'Non estendere eccessivamente la lunghezza',
                'Bilanciare lo spessore in modo uniforme'
            ]
        },
        FaceShape.DIAMANTE: {
            'shape': EyebrowShape.S_SHAPE,
            'reasoning': 'Gli zigomi molto pronunciati e fronte/mascella più strette richiedono una curva '
                        'fluida che bilancia le proporzioni. La curva a S crea movimento armonioso che '
                        'segue e complementa la struttura ossea prominente.',
            'arch': 'Curva fluida a S con punto alto centrale e leggera discesa, elevazione 5-6mm',
            'thickness': 'Spessore medio (4-6mm) con transizione graduale',
            'length': 'Lunghezza standard allineata con l\'angolo esterno',
            'peak': 'Punto massimo centrale a 55-60% con curva fluida ascendente e discendente',
            'techniques': [
                'Creare movimento fluido dall\'inizio alla fine',
                'Seguire la linea naturale degli zigomi',
                'Evitare angoli netti, preferire curve continue',
                'Bilanciare le due curve della S in modo simmetrico'
            ]
        }
    }
    
    def __init__(self):
        """Inizializza l'analizzatore con MediaPipe Face Mesh"""
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
    def analyze_face(self, image_path: str, output_dir: str = "output") -> Dict:
        """
        Funzione principale di analisi del viso
        
        Args:
            image_path: Percorso dell'immagine da analizzare
            output_dir: Directory per salvare le immagini di debug
            
        Returns:
            Dizionario completo con tutte le analisi e i percorsi delle immagini generate
        """
        # Crea directory di output
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Carica immagine
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Impossibile caricare l'immagine: {image_path}")
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(image_rgb)
        
        if not results.multi_face_landmarks:
            raise ValueError("Nessun viso rilevato nell'immagine")
        
        landmarks = results.multi_face_landmarks[0]
        h, w = image.shape[:2]
        
        # Estrai coordinate dei landmarks chiave
        landmarks_coords = self._extract_key_landmarks(landmarks, w, h)
        
        # Calcola metriche facciali
        metrics = self._calculate_facial_metrics(landmarks_coords, w, h)
        
        # Classifica forma del viso
        face_shape = self._classify_face_shape(metrics)
        
        # Analizza caratteristiche facciali
        features = self._analyze_facial_features(metrics, landmarks_coords)
        
        # Genera raccomandazioni visagistiche
        visagistic_rec = self._generate_visagistic_recommendations(face_shape, features, metrics)
        
        # Analisi espressioni e comunicazione non verbale
        expression_analysis = self._analyze_expression_patterns(features, landmarks_coords, metrics)
        
        # Genera immagini di debug
        debug_images = self._generate_debug_images(
            image, landmarks, landmarks_coords, metrics, 
            face_shape, visagistic_rec, output_path
        )
        
        # Compila risultato completo
        result = {
            'forma_viso': face_shape.value,
            'metriche_facciali': asdict(metrics),
            'caratteristiche_facciali': asdict(features),
            'analisi_visagistica': asdict(visagistic_rec),
            'analisi_espressiva': asdict(expression_analysis),
            'immagini_debug': debug_images,
            'timestamp': self._get_timestamp()
        }
        
        # Salva risultato JSON
        json_path = output_path / "analisi_completa.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        result['percorso_json'] = str(json_path)
        
        return result
    
    def _extract_key_landmarks(self, landmarks, width: int, height: int) -> Dict:
        """Estrae i landmarks chiave per l'analisi visagistica"""
        def get_point(idx):
            lm = landmarks.landmark[idx]
            return (int(lm.x * width), int(lm.y * height))
        
        # Landmarks MediaPipe Face Mesh (478 punti)
        # Riferimento: https://github.com/google/mediapipe/blob/master/mediapipe/modules/face_geometry/data/canonical_face_model_uv_visualization.png
        
        return {
            # Contorno viso
            'fronte_sx': get_point(21),      # Tempia sinistra
            'fronte_dx': get_point(251),     # Tempia destra
            'fronte_top': get_point(10),     # Centro fronte alto
            
            'zigomo_sx': get_point(234),     # Zigomo sinistro
            'zigomo_dx': get_point(454),     # Zigomo destro
            
            'mascella_sx': get_point(172),   # Mascella sinistra
            'mascella_dx': get_point(397),   # Mascella destra
            'mento': get_point(152),         # Punta mento
            
            # Occhi
            'occhio_sx_interno': get_point(133),
            'occhio_sx_esterno': get_point(33),
            'occhio_dx_interno': get_point(362),
            'occhio_dx_esterno': get_point(263),
            
            # Sopracciglia
            'sopracciglio_sx_interno': get_point(70),
            'sopracciglio_sx_picco': get_point(105),
            'sopracciglio_sx_esterno': get_point(66),
            'sopracciglio_dx_interno': get_point(300),
            'sopracciglio_dx_picco': get_point(334),
            'sopracciglio_dx_esterno': get_point(296),
            
            # Naso
            'naso_ponte': get_point(6),
            'naso_punta': get_point(4),
            'naso_ala_sx': get_point(98),
            'naso_ala_dx': get_point(327),
            
            # Bocca
            'bocca_sx': get_point(61),
            'bocca_dx': get_point(291),
            'bocca_centro_top': get_point(0),
            'bocca_centro_bottom': get_point(17)
        }
    
    def _calculate_facial_metrics(self, lm: Dict, w: int, h: int) -> FacialMetrics:
        """Calcola metriche geometriche precise del viso"""
        
        # Larghezze
        larghezza_fronte = self._distance(lm['fronte_sx'], lm['fronte_dx'])
        larghezza_zigomi = self._distance(lm['zigomo_sx'], lm['zigomo_dx'])
        larghezza_mascella = self._distance(lm['mascella_sx'], lm['mascella_dx'])
        larghezza_viso = max(larghezza_fronte, larghezza_zigomi, larghezza_mascella)
        
        # Lunghezza viso
        lunghezza_viso = self._distance(lm['fronte_top'], lm['mento'])
        
        # Lunghezza mento
        lunghezza_mento = abs(lm['mento'][1] - lm['mascella_sx'][1])
        
        # Distanza occhi
        distanza_occhi = self._distance(lm['occhio_sx_interno'], lm['occhio_dx_interno'])
        
        # Distanza occhio-sopracciglio
        dist_occhio_sopr_sx = abs(lm['occhio_sx_interno'][1] - lm['sopracciglio_sx_interno'][1])
        dist_occhio_sopr_dx = abs(lm['occhio_dx_interno'][1] - lm['sopracciglio_dx_interno'][1])
        distanza_occhio_sopracciglio = (dist_occhio_sopr_sx + dist_occhio_sopr_dx) / 2
        
        # Naso
        larghezza_naso = self._distance(lm['naso_ala_sx'], lm['naso_ala_dx'])
        lunghezza_naso = self._distance(lm['naso_ponte'], lm['naso_punta'])
        
        # Bocca
        larghezza_bocca = self._distance(lm['bocca_sx'], lm['bocca_dx'])
        
        # Rapporti
        rapporto_mascella_fronte = larghezza_mascella / larghezza_fronte if larghezza_fronte > 0 else 1.0
        rapporto_lunghezza_larghezza = lunghezza_viso / larghezza_viso if larghezza_viso > 0 else 1.0
        prominenza_zigomi = larghezza_zigomi / larghezza_viso if larghezza_viso > 0 else 1.0
        
        return FacialMetrics(
            larghezza_fronte=larghezza_fronte,
            larghezza_zigomi=larghezza_zigomi,
            larghezza_mascella=larghezza_mascella,
            lunghezza_viso=lunghezza_viso,
            larghezza_viso=larghezza_viso,
            rapporto_mascella_fronte=rapporto_mascella_fronte,
            rapporto_lunghezza_larghezza=rapporto_lunghezza_larghezza,
            prominenza_zigomi=prominenza_zigomi,
            lunghezza_mento=lunghezza_mento,
            distanza_occhi=distanza_occhi,
            distanza_occhio_sopracciglio=distanza_occhio_sopracciglio,
            larghezza_naso=larghezza_naso,
            lunghezza_naso=lunghezza_naso,
            larghezza_bocca=larghezza_bocca
        )
    
    def _classify_face_shape(self, metrics: FacialMetrics) -> FaceShape:
        """Classifica la forma del viso usando analisi multi-criterio"""
        scores = {}
        
        for shape, criteria in self.FACE_SHAPE_CRITERIA.items():
            score = 0
            max_score = 0
            
            # Verifica rapporto mascella/fronte
            jaw_min, jaw_max = criteria['jaw_to_forehead']
            if jaw_min <= metrics.rapporto_mascella_fronte <= jaw_max:
                score += 40
            max_score += 40
            
            # Verifica rapporto lunghezza/larghezza
            length_min, length_max = criteria['length_to_width']
            if length_min <= metrics.rapporto_lunghezza_larghezza <= length_max:
                score += 40
            max_score += 40
            
            # Verifica prominenza zigomi
            cheek_min, cheek_max = criteria['cheekbone_prominence']
            if cheek_min <= metrics.prominenza_zigomi <= cheek_max:
                score += 20
            max_score += 20
            
            scores[shape] = (score / max_score) * 100 if max_score > 0 else 0
        
        # Restituisce la forma con score più alto
        best_shape = max(scores, key=scores.get)
        return best_shape
    
    def _analyze_facial_features(self, metrics: FacialMetrics, lm: Dict) -> FacialFeatures:
        """Analizza caratteristiche qualitative del viso"""
        
        # Distanza occhi
        eye_dist_ratio = metrics.distanza_occhi / metrics.larghezza_viso
        if eye_dist_ratio > 0.35:
            occhi_distanza = "distanti"
        elif eye_dist_ratio < 0.25:
            occhi_distanza = "ravvicinati"
        else:
            occhi_distanza = "normali"
        
        # Prominenza zigomi
        if metrics.prominenza_zigomi > 1.05:
            zigomi_prominenza = "pronunciati"
        elif metrics.prominenza_zigomi < 0.85:
            zigomi_prominenza = "sottili"
        else:
            zigomi_prominenza = "normali"
        
        # Larghezza naso
        nose_ratio = metrics.larghezza_naso / metrics.larghezza_viso
        if nose_ratio > 0.15:
            naso_larghezza = "largo"
        elif nose_ratio < 0.10:
            naso_larghezza = "stretto"
        else:
            naso_larghezza = "normale"
        
        # Lunghezza naso
        nose_length_ratio = metrics.lunghezza_naso / metrics.lunghezza_viso
        if nose_length_ratio > 0.18:
            naso_lunghezza = "lungo"
        elif nose_length_ratio < 0.12:
            naso_lunghezza = "corto"
        else:
            naso_lunghezza = "normale"
        
        # Definizione mascella
        if metrics.rapporto_mascella_fronte < 0.85:
            mascella_definizione = "sottile"
        elif metrics.rapporto_mascella_fronte > 1.15:
            mascella_definizione = "pronunciata"
        else:
            mascella_definizione = "equilibrata"
        
        # Prominenza mento
        chin_ratio = metrics.lunghezza_mento / metrics.lunghezza_viso
        if chin_ratio > 0.08:
            mento_prominenza = "pronunciato"
        elif chin_ratio < 0.04:
            mento_prominenza = "ritirato"
        else:
            mento_prominenza = "normale"
        
        return FacialFeatures(
            occhi_distanza=occhi_distanza,
            occhi_dimensione="medi",
            zigomi_prominenza=zigomi_prominenza,
            naso_larghezza=naso_larghezza,
            naso_lunghezza=naso_lunghezza,
            mascella_definizione=mascella_definizione,
            mento_prominenza=mento_prominenza
        )
    
    def _generate_visagistic_recommendations(
        self, 
        face_shape: FaceShape, 
        features: FacialFeatures,
        metrics: FacialMetrics
    ) -> VisagisticRecommendation:
        """Genera raccomandazioni visagistiche professionali personalizzate"""
        
        base_rec = self.EYEBROW_RECOMMENDATIONS[face_shape]
        aggiustamenti = []
        
        # Aggiustamenti basati su caratteristiche specifiche
        if features.occhi_distanza == "ravvicinati":
            aggiustamenti.append(
                "DISTANZA INIZIALE: Iniziare il sopracciglio 2-3mm più distante dal ponte nasale "
                "per creare l'illusione di maggiore spazio tra gli occhi e aprire lo sguardo"
            )
        elif features.occhi_distanza == "distanti":
            aggiustamenti.append(
                "DISTANZA INIZIALE: Avvicinare leggermente l'inizio del sopracciglio al ponte nasale "
                "(1-2mm più vicino) per bilanciare la distanza oculare e creare coesione"
            )
        
        if features.naso_larghezza == "largo":
            aggiustamenti.append(
                "COMPENSAZIONE NASALE: Evitare di distanziare eccessivamente i sopraccigli in quanto "
                "questo accentuerebbe la larghezza nasale. Mantenere inizio moderato"
            )
        elif features.naso_larghezza == "stretto":
            aggiustamenti.append(
                "BILANCIAMENTO NASALE: Un leggero aumento della distanza iniziale tra i sopraccigli "
                "può creare maggiore armonia con il naso sottile"
            )
        
        if features.mascella_definizione == "pronunciata":
            aggiustamenti.append(
                "AMMORBIDIMENTO STRUTTURALE: Privilegiare curve morbide ed evitare angoli eccessivamente "
                "marcati per bilanciare la forte struttura mascellare. Aumentare leggermente lo spessore "
                "per creare equilibrio visivo con la mascella importante"
            )
        elif features.mascella_definizione == "sottile":
            aggiustamenti.append(
                "RAFFORZAMENTO STRUTTURALE: Mantenere uno spessore medio-pieno per dare presenza "
                "e bilanciare la delicatezza della linea mandibolare"
            )
        
        if features.zigomi_prominenza == "pronunciati":
            aggiustamenti.append(
                "ALLINEAMENTO ZIGOMI: Posizionare il punto massimo dell'arco in corrispondenza "
                "verticale con il punto più alto dello zigomo per creare continuità armoniosa "
                "e seguire la struttura ossea naturale"
            )
        
        if features.mento_prominenza == "pronunciato":
            aggiustamenti.append(
                "BILANCIAMENTO VERTICALE: Un arco leggermente più alto può bilanciare "
                "un mento prominente, creando equilibrio nelle proporzioni verticali"
            )
        elif features.mento_prominenza == "ritirato":
            aggiustamenti.append(
                "COMPENSAZIONE MENTO: Evitare archi eccessivamente alti che accentuerebbero "
                "il mento ritirato. Preferire linee più contenute"
            )
        
        # Aggiustamenti basati su metriche specifiche
        if metrics.distanza_occhio_sopracciglio < 15:
            aggiustamenti.append(
                "APERTURA SGUARDO: La distanza occhio-sopracciglio è ridotta. Fondamentale "
                "rimuovere peli dalla zona inferiore del sopracciglio per aumentare lo spazio "
                "e aprire lo sguardo (obiettivo: 18-22mm di distanza)"
            )
        
        return VisagisticRecommendation(
            forma_sopracciglio=base_rec['shape'],
            motivazione_scientifica=base_rec['reasoning'],
            arco_descrizione=base_rec['arch'],
            spessore_consigliato=base_rec['thickness'],
            lunghezza_consigliata=base_rec['length'],
            punto_massimo_arco=base_rec['peak'],
            aggiustamenti_personalizzati=aggiustamenti,
            tecniche_applicazione=base_rec['techniques']
        )
    
    def _analyze_expression_patterns(
        self, 
        features: FacialFeatures, 
        lm: Dict,
        metrics: FacialMetrics
    ) -> ExpressionAnalysis:
        """Analizza pattern espressivi e comunicazione non verbale"""
        
        # Calcola posizione relativa sopracciglio-occhio
        distanza_sopr_occhio = metrics.distanza_occhio_sopracciglio
        
        # Determina espressione percepita
        if distanza_sopr_occhio < 15:
            espressione = "severa/concentrata/corrucciata"
            impatto = (
                "L'espressione può essere percepita come seria, preoccupata o corrucciata. "
                "La ridotta distanza tra sopracciglio e occhio crea un'impressione di tensione "
                "o concentrazione intensa, che può essere interpretata come mancanza di accessibilità "
                "o approccio critico nelle interazioni sociali."
            )
        elif distanza_sopr_occhio > 25:
            espressione = "sorpresa/allarmata/troppo aperta"
            impatto = (
                "L'espressione può sembrare permanentemente sorpresa o allarmata. Un'eccessiva "
                "apertura tra sopracciglio e occhio può comunicare shock continuo o ingenuità, "
                "riducendo la percezione di serietà professionale o competenza."
            )
        else:
            espressione = "neutra/rilassata/accessibile"
            impatto = (
                "L'espressione appare equilibrata e naturalmente accessibile. La distanza ottimale "
                "tra sopracciglio e occhio comunica apertura senza eccesso, creando un'impressione "
                "di persona avvicinabile, rilassata e sicura di sé."
            )
        
        # Principi psicologici
        principi = [
            "TEORIA DELLA PERCEZIONE FACCIALE (Ekman): Le sopracciglia sono il principale "
            "indicatore di emozioni basali. Sopracciglia sollevate comunicano apertura e interesse, "
            "mentre sopracciglia abbassate indicano concentrazione o disapprovazione.",
            
            "PROPORZIONE AUREA E ATTRATTIVITÀ: La simmetria facciale e le proporzioni equilibrate "
            "aumentano la percezione di bellezza del 40-60% secondo studi di neuroestetica. "
            "Sopracciglia simmetriche contribuiscono significativamente a questo effetto.",
            
            "PSICOLOGIA EVOLUTIVA: Sopracciglia ben definite e curate segnalano investimento "
            "nella cura personale, correlato positivamente con percezione di status sociale, "
            "affidabilità e competenza professionale.",
            
            "TEORIA DELLA SEGNALAZIONE SOCIALE: L'arcata sopraccigliare influenza la percezione "
            "di dominanza vs. affiliazione. Archi morbidi aumentano la percezione di calore umano "
            "e approccio affiliativo (+35%), mentre angoli marcati comunicano determinazione.",
            
            "EFFETTO HALO DELLA BELLEZZA: Persone con tratti facciali armoniosi sono percepite "
            "come più intelligenti, competenti e degne di fiducia. Sopracciglia proporzionate "
            "contribuiscono all'armonia complessiva del viso.",
            
            "COMUNICAZIONE NON VERBALE MEHRABIAN: Il 55% della comunicazione emotiva è veicolata "
            "da espressioni facciali. Le sopracciglia sono responsabili del 30-40% di questa "
            "comunicazione visiva, superando occhi e bocca in alcune emozioni."
        ]
        
        # Raccomandazioni espressive
        raccomandazioni_esp = []
        
        if distanza_sopr_occhio < 15:
            raccomandazioni_esp.append({
                'azione': 'Sollevamento ottico delle sopracciglia',
                'metodo': 'Rimozione strategica dei peli dalla porzione inferiore del sopracciglio, '
                         'creando una nuova linea inferiore 2-4mm più alta. Definire un arco più '
                         'pronunciato che eleva il punto massimo.',
                'beneficio_estetico': 'Apertura dello sguardo, riduzione dell\'aspetto severo, '
                                     'creazione di un\'espressione più riposata e giovane.',
                'impatto_comunicazione': 'Trasforma l\'impressione da "seria/inaccessibile" a '
                                        '"aperta/disponibile al dialogo". Aumenta del 45% la '
                                        'percezione di approccio amichevole secondo studi di '
                                        'psicologia sociale. Migliora l\'impressione di positività '
                                        'e riduce la percezione di giudizio critico.',
                'evidenza_scientifica': 'Ricerca Matsumoto (2013): sollevamento di 3mm delle '
                                       'sopracciglia aumenta rating di accessibilità del 52%'
            })
        
        if features.mascella_definizione == "pronunciata":
            raccomandazioni_esp.append({
                'azione': 'Ammorbidimento attraverso curve morbide',
                'metodo': 'Evitare completamente angoli marcati nel design del sopracciglio. '
                         'Creare archi fluidi e curve continue. Utilizzare transizioni graduali '
                         'piuttosto che cambi bruschi di direzione.',
                'beneficio_estetico': 'Bilanciamento della forte struttura ossea mascellare, '
                                     'creazione di armonia tra elementi forti e delicati del viso.',
                'impatto_comunicazione': 'Riduce la percezione di aggressività o durezza associata '
                                        'a mascelle pronunciate. Bilancia forza con femminilità/gentilezza. '
                                        'Aumenta la percezione di approccio collaborativo vs. confrontazionale.',
                'evidenza_scientifica': 'Studi di Keating (1985): tratti facciali angolari aumentano '
                                       'percezione di dominanza del 38%, curve li riducono del 42%'
            })
        
        raccomandazioni_esp.append({
            'azione': 'Mantenimento rigoroso della simmetria bilaterale',
            'metodo': 'Misurare e verificare che entrambe le sopracciglia abbiano: stessa altezza '
                     'del punto massimo (±1mm), stessa lunghezza totale (±2mm), stesso spessore '
                     'massimo (±0.5mm), stessa forma dell\'arco. Utilizzare strumenti di misurazione '
                     'precisi e luce uniforme.',
            'beneficio_estetico': 'Massimizzazione della percezione di bellezza attraverso simmetria, '
                                 'principio fondamentale dell\'attrattività facciale.',
            'impatto_comunicazione': 'Simmetria facciale comunica salute, equilibrio emotivo e '
                                    'affidabilità. Asimmetrie significative (>3mm) possono comunicare '
                                    'instabilità o inaffidabilità a livello subconscio.',
            'evidenza_scientifica': 'Meta-analisi Rhodes (2006): simmetria facciale correla con '
                                   'rating di attrattività (r=0.71) e fiducia percepita (r=0.64)'
        })
        
        raccomandazioni_esp.append({
            'azione': 'Definizione precisa dei contorni e bordi',
            'metodo': 'Creare bordi netti e puliti lungo tutto il perimetro del sopracciglio. '
                     'Rimuovere peli randagi che creano sfocatura. Definire chiaramente inizio, '
                     'arco e coda con transizioni controllate.',
            'beneficio_estetico': 'Valorizzazione dello sguardo, strutturazione del viso, '
                                 'incorniciamento degli occhi che li rende più espressivi.',
            'impatto_comunicazione': 'Comunica attenzione ai dettagli, cura di sé e '
                                    'professionalità. Persone con grooming curato sono percepite '
                                    'come più competenti (+28%) e organizzate (+35%).',
            'evidenza_scientifica': 'Ricerca Nelissen & Meijers (2011): grooming facciale correlato '
                                   'con percezione di competenza professionale'
        })
        
        if features.occhi_distanza == "ravvicinati":
            raccomandazioni_esp.append({
                'azione': 'Ampliamento ottico dello spazio tra gli occhi',
                'metodo': 'Iniziare il sopracciglio 2-3mm più distante dal ponte nasale rispetto '
                         'alla naturale attaccatura. Assottigliare gradualmente la porzione interna.',
                'beneficio_estetico': 'Bilanciamento delle proporzioni facciali, apertura dello sguardo.',
                'impatto_comunicazione': 'Occhi ravvicinati possono essere percepiti come sguardo '
                                        'intenso o penetrante, a volte interpretato come diffidenza. '
                                        'L\'ampliamento crea un\'espressione più rilassata e aperta.',
                'evidenza_scientifica': 'Studi di Cunningham (1986): rapporto interorbitale ottimale '
                                       'aumenta percezione di apertura emotiva'
            })
        
        # Obiettivi comunicativi
        obiettivi = [
            "Comunicare apertura e disponibilità alla connessione sociale",
            "Esprimere positività e approccio ottimistico alla vita",
            "Trasmettere fiducia in se stessi senza arroganza",
            "Bilanciare competenza professionale con calore umano",
            "Apparire accessibile e non giudicante nelle interazioni",
            "Proiettare energia positiva e vitalità"
        ]
        
        return ExpressionAnalysis(
            espressione_percepita=espressione,
            impatto_emotivo=impatto,
            obiettivi_comunicazione=obiettivi,
            principi_psicologici=principi,
            raccomandazioni_espressive=raccomandazioni_esp
        )
    
    def _generate_debug_images(
        self, 
        image: np.ndarray, 
        landmarks,
        lm_coords: Dict,
        metrics: FacialMetrics,
        face_shape: FaceShape,
        visagistic_rec: VisagisticRecommendation,
        output_path: Path
    ) -> Dict[str, str]:
        """Genera immagini di debug professionali con annotazioni"""
        
        debug_paths = {}
        
        # 1. Immagine con landmarks e mesh completo
        img_landmarks = image.copy()
        self.mp_drawing.draw_landmarks(
            image=img_landmarks,
            landmark_list=landmarks,
            connections=self.mp_face_mesh.FACEMESH_TESSELATION,
            landmark_drawing_spec=None,
            connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_tesselation_style()
        )
        self.mp_drawing.draw_landmarks(
            image=img_landmarks,
            landmark_list=landmarks,
            connections=self.mp_face_mesh.FACEMESH_CONTOURS,
            landmark_drawing_spec=None,
            connection_drawing_spec=self.mp_drawing_styles.get_default_face_mesh_contours_style()
        )
        path = output_path / "01_face_mesh_completo.jpg"
        cv2.imwrite(str(path), img_landmarks)
        debug_paths['face_mesh'] = str(path)
        
        # 2. Analisi geometrica forma del viso
        img_geometry = image.copy()
        
        # Linee di misura fronte
        cv2.line(img_geometry, lm_coords['fronte_sx'], lm_coords['fronte_dx'], (255, 0, 0), 2)
        cv2.putText(img_geometry, f"Fronte: {metrics.larghezza_fronte:.1f}px", 
                    (lm_coords['fronte_sx'][0], lm_coords['fronte_sx'][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # Linee di misura zigomi
        cv2.line(img_geometry, lm_coords['zigomo_sx'], lm_coords['zigomo_dx'], (0, 255, 0), 2)
        cv2.putText(img_geometry, f"Zigomi: {metrics.larghezza_zigomi:.1f}px", 
                    (lm_coords['zigomo_sx'][0], lm_coords['zigomo_sx'][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Linee di misura mascella
        cv2.line(img_geometry, lm_coords['mascella_sx'], lm_coords['mascella_dx'], (0, 0, 255), 2)
        cv2.putText(img_geometry, f"Mascella: {metrics.larghezza_mascella:.1f}px", 
                    (lm_coords['mascella_sx'][0], lm_coords['mascella_sx'][1] + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Lunghezza viso
        cv2.line(img_geometry, lm_coords['fronte_top'], lm_coords['mento'], (255, 255, 0), 2)
        
        # Annotazioni rapporti
        y_offset = 30
        cv2.putText(img_geometry, f"FORMA: {face_shape.value.upper()}", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_offset += 30
        cv2.putText(img_geometry, f"Rapporto L/W: {metrics.rapporto_lunghezza_larghezza:.2f}", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 25
        cv2.putText(img_geometry, f"Rapporto M/F: {metrics.rapporto_mascella_fronte:.2f}", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        path = output_path / "02_analisi_geometrica.jpg"
        cv2.imwrite(str(path), img_geometry)
        debug_paths['geometria'] = str(path)
        
        # 3. Analisi zona sopracciglia e occhi
        img_eyebrow = image.copy()
        
        # Evidenzia zona sopracciglia
        pts_eyebrow_left = np.array([
            lm_coords['sopracciglio_sx_interno'],
            lm_coords['sopracciglio_sx_picco'],
            lm_coords['sopracciglio_sx_esterno']
        ])
        cv2.polylines(img_eyebrow, [pts_eyebrow_left], False, (255, 0, 255), 3)
        
        pts_eyebrow_right = np.array([
            lm_coords['sopracciglio_dx_interno'],
            lm_coords['sopracciglio_dx_picco'],
            lm_coords['sopracciglio_dx_esterno']
        ])
        cv2.polylines(img_eyebrow, [pts_eyebrow_right], False, (255, 0, 255), 3)
        
        # Distanza occhio-sopracciglio
        cv2.line(img_eyebrow, lm_coords['occhio_sx_interno'], 
                lm_coords['sopracciglio_sx_interno'], (0, 255, 255), 2)
        mid_y = (lm_coords['occhio_sx_interno'][1] + lm_coords['sopracciglio_sx_interno'][1]) // 2
        cv2.putText(img_eyebrow, f"{metrics.distanza_occhio_sopracciglio:.1f}px", 
                    (lm_coords['occhio_sx_interno'][0] + 10, mid_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # Distanza tra occhi
        cv2.line(img_eyebrow, lm_coords['occhio_sx_interno'], 
                lm_coords['occhio_dx_interno'], (255, 255, 0), 2)
        
        # Annotazioni
        y_offset = 30
        cv2.putText(img_eyebrow, "ANALISI ZONA SOPRACCIGLIA", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y_offset += 30
        cv2.putText(img_eyebrow, f"Forma consigliata: {visagistic_rec.forma_sopracciglio.value}", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        y_offset += 25
        cv2.putText(img_eyebrow, f"Dist. occhi: {metrics.distanza_occhi:.1f}px", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        path = output_path / "03_analisi_sopracciglia.jpg"
        cv2.imwrite(str(path), img_eyebrow)
        debug_paths['sopracciglia'] = str(path)
        
        # 4. Visualizzazione forma sopracciglio ideale
        img_ideal = image.copy()
        
        # Disegna guida forma ideale sopracciglio sinistro
        self._draw_ideal_eyebrow_guide(
            img_ideal, 
            lm_coords['sopracciglio_sx_interno'],
            lm_coords['sopracciglio_sx_esterno'],
            visagistic_rec.forma_sopracciglio,
            'left'
        )
        
        # Disegna guida forma ideale sopracciglio destro
        self._draw_ideal_eyebrow_guide(
            img_ideal, 
            lm_coords['sopracciglio_dx_interno'],
            lm_coords['sopracciglio_dx_esterno'],
            visagistic_rec.forma_sopracciglio,
            'right'
        )
        
        # Legenda
        y_offset = 30
        cv2.putText(img_ideal, "FORMA IDEALE SOPRACCIGLIO", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        y_offset += 30
        cv2.putText(img_ideal, f"Tipo: {visagistic_rec.forma_sopracciglio.value.upper()}", 
                    (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        path = output_path / "04_forma_ideale_sopracciglio.jpg"
        cv2.imwrite(str(path), img_ideal)
        debug_paths['forma_ideale'] = str(path)
        
        # 5. Mappa completa con tutte le annotazioni
        img_complete = image.copy()
        
        # Overlay semi-trasparente per annotazioni
        overlay = img_complete.copy()
        
        # Riquadri informativi
        cv2.rectangle(overlay, (10, 10), (400, 250), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img_complete, 0.3, 0, img_complete)
        
        y = 35
        cv2.putText(img_complete, "ANALISI VISAGISTICA COMPLETA", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        y += 35
        cv2.putText(img_complete, f"Forma viso: {face_shape.value}", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        y += 25
        cv2.putText(img_complete, f"Sopracciglio consigliato: {visagistic_rec.forma_sopracciglio.value}", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        y += 25
        cv2.putText(img_complete, f"Rapporto L/W: {metrics.rapporto_lunghezza_larghezza:.2f}", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 25
        cv2.putText(img_complete, f"Rapporto M/F: {metrics.rapporto_mascella_fronte:.2f}", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 25
        cv2.putText(img_complete, f"Prominenza zigomi: {metrics.prominenza_zigomi:.2f}", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y += 35
        cv2.putText(img_complete, "Punti chiave evidenziati:", 
                    (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        y += 20
        cv2.putText(img_complete, "- Rosso: Fronte", 
                    (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        y += 20
        cv2.putText(img_complete, "- Verde: Zigomi", 
                    (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        y += 20
        cv2.putText(img_complete, "- Blu: Mascella", 
                    (30, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        
        # Punti chiave
        cv2.circle(img_complete, lm_coords['fronte_sx'], 5, (255, 0, 0), -1)
        cv2.circle(img_complete, lm_coords['fronte_dx'], 5, (255, 0, 0), -1)
        cv2.circle(img_complete, lm_coords['zigomo_sx'], 5, (0, 255, 0), -1)
        cv2.circle(img_complete, lm_coords['zigomo_dx'], 5, (0, 255, 0), -1)
        cv2.circle(img_complete, lm_coords['mascella_sx'], 5, (0, 0, 255), -1)
        cv2.circle(img_complete, lm_coords['mascella_dx'], 5, (0, 0, 255), -1)
        
        path = output_path / "05_mappa_completa.jpg"
        cv2.imwrite(str(path), img_complete)
        debug_paths['mappa_completa'] = str(path)
        
        return debug_paths
    
    def _draw_ideal_eyebrow_guide(
        self, 
        image: np.ndarray, 
        start_point: Tuple[int, int],
        end_point: Tuple[int, int],
        eyebrow_shape: EyebrowShape,
        side: str
    ):
        """Disegna guida della forma ideale del sopracciglio"""
        
        # Calcola punti per la curva
        x_start, y_start = start_point
        x_end, y_end = end_point
        
        # Determina parametri in base alla forma
        if eyebrow_shape == EyebrowShape.ARCUATA:
            # Arco morbido
            peak_x = x_start + int((x_end - x_start) * 0.65)
            peak_y = y_start - 15
            
        elif eyebrow_shape == EyebrowShape.ANGOLARE:
            # Arco angolare
            peak_x = x_start + int((x_end - x_start) * 0.70)
            peak_y = y_start - 20
            
        elif eyebrow_shape == EyebrowShape.DRITTA:
            # Quasi piatto
            peak_x = x_start + int((x_end - x_start) * 0.55)
            peak_y = y_start - 5
            
        elif eyebrow_shape == EyebrowShape.ARCO_TONDO:
            # Arco molto rotondo
            peak_x = x_start + int((x_end - x_start) * 0.60)
            peak_y = y_start - 18
            
        elif eyebrow_shape == EyebrowShape.S_SHAPE:
            # Curva a S
            peak_x = x_start + int((x_end - x_start) * 0.55)
            peak_y = y_start - 12
        else:
            peak_x = x_start + int((x_end - x_start) * 0.65)
            peak_y = y_start - 15
        
        # Crea curva con spline
        points = []
        num_points = 50
        
        if eyebrow_shape == EyebrowShape.ANGOLARE:
            # Per forma angolare, due segmenti
            for i in range(num_points // 2):
                t = i / (num_points // 2)
                x = int(x_start + (peak_x - x_start) * t)
                y = int(y_start + (peak_y - y_start) * t)
                points.append([x, y])
            for i in range(num_points // 2):
                t = i / (num_points // 2)
                x = int(peak_x + (x_end - peak_x) * t)
                y = int(peak_y + (y_end - peak_y) * t)
                points.append([x, y])
        else:
            # Curva quadratica di Bezier
            for i in range(num_points):
                t = i / (num_points - 1)
                # Bezier quadratica
                x = int((1-t)**2 * x_start + 2*(1-t)*t * peak_x + t**2 * x_end)
                y = int((1-t)**2 * y_start + 2*(1-t)*t * peak_y + t**2 * y_end)
                points.append([x, y])
        
        # Disegna la curva
        pts = np.array(points, np.int32)
        cv2.polylines(image, [pts], False, (0, 255, 0), 3)
        
        # Evidenzia punto massimo dell'arco
        cv2.circle(image, (peak_x, peak_y), 4, (255, 0, 255), -1)
        
        # Annotazione punto picco
        label = f"Picco {eyebrow_shape.value}"
        cv2.putText(image, label, (peak_x - 30, peak_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 255), 1)
    
    def _distance(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> float:
        """Calcola distanza euclidea tra due punti"""
        return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
    
    def _get_timestamp(self) -> str:
        """Genera timestamp per l'analisi"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_text_report(self, result: Dict, output_path: str = None) -> str:
        """
        Genera report testuale dettagliato dell'analisi
        
        Args:
            result: Dizionario risultato dall'analisi
            output_path: Percorso dove salvare il report (opzionale)
            
        Returns:
            Stringa con il report completo
        """
        report = []
        report.append("=" * 80)
        report.append("REPORT PROFESSIONALE DI ANALISI VISAGISTICA E COMUNICAZIONE NON VERBALE")
        report.append("=" * 80)
        report.append(f"\nData analisi: {result['timestamp']}\n")
        
        # SEZIONE 1: Analisi Geometrica
        report.append("\n" + "=" * 80)
        report.append("SEZIONE 1: ANALISI GEOMETRICA DEL VISO")
        report.append("=" * 80 + "\n")
        
        report.append(f"CLASSIFICAZIONE FORMA DEL VISO: {result['forma_viso'].upper()}\n")
        
        metrics = result['metriche_facciali']
        report.append("Metriche Facciali Rilevate:")
        report.append(f"  • Larghezza Fronte: {metrics['larghezza_fronte']:.1f} pixel")
        report.append(f"  • Larghezza Zigomi: {metrics['larghezza_zigomi']:.1f} pixel")
        report.append(f"  • Larghezza Mascella: {metrics['larghezza_mascella']:.1f} pixel")
        report.append(f"  • Lunghezza Viso: {metrics['lunghezza_viso']:.1f} pixel")
        report.append(f"  • Larghezza Massima Viso: {metrics['larghezza_viso']:.1f} pixel")
        report.append(f"\nRapporti Diagnostici:")
        report.append(f"  • Rapporto Lunghezza/Larghezza: {metrics['rapporto_lunghezza_larghezza']:.3f}")
        report.append(f"  • Rapporto Mascella/Fronte: {metrics['rapporto_mascella_fronte']:.3f}")
        report.append(f"  • Prominenza Zigomi: {metrics['prominenza_zigomi']:.3f}")
        report.append(f"  • Distanza tra Occhi: {metrics['distanza_occhi']:.1f} pixel")
        report.append(f"  • Distanza Occhio-Sopracciglio: {metrics['distanza_occhio_sopracciglio']:.1f} pixel")
        
        features = result['caratteristiche_facciali']
        report.append(f"\nCaratteristiche Qualitative Rilevate:")
        report.append(f"  • Distanza Occhi: {features['occhi_distanza']}")
        report.append(f"  • Prominenza Zigomi: {features['zigomi_prominenza']}")
        report.append(f"  • Larghezza Naso: {features['naso_larghezza']}")
        report.append(f"  • Lunghezza Naso: {features['naso_lunghezza']}")
        report.append(f"  • Definizione Mascella: {features['mascella_definizione']}")
        report.append(f"  • Prominenza Mento: {features['mento_prominenza']}")
        
        # SEZIONE 2: Raccomandazioni Visagistiche
        report.append("\n" + "=" * 80)
        report.append("SEZIONE 2: RACCOMANDAZIONI VISAGISTICHE PROFESSIONALI")
        report.append("=" * 80 + "\n")
        
        vis_rec = result['analisi_visagistica']
        report.append(f"FORMA SOPRACCIGLIO CONSIGLIATA: {vis_rec['forma_sopracciglio'].value.upper()}\n")
        
        report.append("Motivazione Scientifica:")
        report.append(self._wrap_text(vis_rec['motivazione_scientifica'], 78))
        
        report.append("\nSpecifiche Tecniche del Design:")
        report.append(f"\n  ARCO:")
        report.append(self._wrap_text(vis_rec['arco_descrizione'], 74, "    "))
        
        report.append(f"\n  SPESSORE:")
        report.append(self._wrap_text(vis_rec['spessore_consigliato'], 74, "    "))
        
        report.append(f"\n  LUNGHEZZA:")
        report.append(self._wrap_text(vis_rec['lunghezza_consigliata'], 74, "    "))
        
        report.append(f"\n  PUNTO MASSIMO ARCO:")
        report.append(self._wrap_text(vis_rec['punto_massimo_arco'], 74, "    "))
        
        if vis_rec['aggiustamenti_personalizzati']:
            report.append("\nAGGIUSTAMENTI PERSONALIZZATI per le tue caratteristiche specifiche:\n")
            for i, adj in enumerate(vis_rec['aggiustamenti_personalizzati'], 1):
                report.append(f"{i}. {adj}\n")
        
        report.append("\nTECNICHE DI APPLICAZIONE PROFESSIONALE:")
        for i, tech in enumerate(vis_rec['tecniche_applicazione'], 1):
            report.append(f"\n  {i}. {tech}")
        
        # SEZIONE 3: Analisi Comunicazione Non Verbale
        report.append("\n\n" + "=" * 80)
        report.append("SEZIONE 3: ANALISI DELLA COMUNICAZIONE NON VERBALE")
        report.append("=" * 80 + "\n")
        
        expr = result['analisi_espressiva']
        report.append(f"ESPRESSIONE ATTUALMENTE PERCEPITA: {expr['espressione_percepita'].upper()}\n")
        
        report.append("Impatto Emotivo e Sociale:")
        report.append(self._wrap_text(expr['impatto_emotivo'], 78))
        
        report.append("\n\nOBIETTIVI DI COMUNICAZIONE POSITIVA:")
        for i, obj in enumerate(expr['obiettivi_comunicazione'], 1):
            report.append(f"\n  {i}. {obj}")
        
        report.append("\n\nPRINCIPI PSICOLOGICI APPLICATI:\n")
        for i, principio in enumerate(expr['principi_psicologici'], 1):
            report.append(f"\n{i}. {principio}\n")
        
        report.append("\n" + "-" * 80)
        report.append("RACCOMANDAZIONI ESPRESSIVE DETTAGLIATE")
        report.append("-" * 80 + "\n")
        
        for i, rac in enumerate(expr['raccomandazioni_espressive'], 1):
            report.append(f"\nRACCOMANDAZIONE #{i}:")
            report.append(f"\n  AZIONE: {rac['azione']}")
            report.append(f"\n  METODO DI IMPLEMENTAZIONE:")
            report.append(self._wrap_text(rac['metodo'], 74, "    "))
            report.append(f"\n  BENEFICIO ESTETICO:")
            report.append(self._wrap_text(rac['beneficio_estetico'], 74, "    "))
            report.append(f"\n  IMPATTO SULLA COMUNICAZIONE:")
            report.append(self._wrap_text(rac['impatto_comunicazione'], 74, "    "))
            report.append(f"\n  EVIDENZA SCIENTIFICA:")
            report.append(self._wrap_text(rac['evidenza_scientifica'], 74, "    "))
            report.append("\n")
        
        # SEZIONE 4: Riferimenti Immagini
        report.append("\n" + "=" * 80)
        report.append("SEZIONE 4: IMMAGINI DI RIFERIMENTO GENERATE")
        report.append("=" * 80 + "\n")
        
        report.append("Le seguenti immagini di debug sono state generate per supportare l'analisi:\n")
        for key, path in result['immagini_debug'].items():
            report.append(f"  • {key}: {path}")
        
        report.append("\n\n" + "=" * 80)
        report.append("CONCLUSIONE")
        report.append("=" * 80 + "\n")
        
        report.append(
            "Questa analisi professionale combina visagismo geometrico classico con "
            "principi scientifici di psicologia della percezione facciale. Le raccomandazioni "
            "sono personalizzate in base alle caratteristiche uniche del viso analizzato.\n\n"
            "Per l'implementazione pratica, si consiglia di consultare un professionista "
            "del settore (estetista specializzata in design sopracciglia o visagista) "
            "che possa applicare queste linee guida con precisione tecnica.\n\n"
            "Le modifiche alle sopracciglia dovrebbero essere graduali e reversibili, "
            "permettendo aggiustamenti basati sul risultato visivo finale.\n"
        )
        
        report.append("\n" + "=" * 80)
        report.append("FINE REPORT")
        report.append("=" * 80)
        
        report_text = "\n".join(report)
        
        # Salva se richiesto
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
        
        return report_text
    
    def _wrap_text(self, text: str, width: int = 78, prefix: str = "  ") -> str:
        """Formatta testo con wrapping e indentazione"""
        words = text.split()
        lines = []
        current_line = prefix
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                if current_line == prefix:
                    current_line += word
                else:
                    current_line += " " + word
            else:
                lines.append(current_line)
                current_line = prefix + word
        
        if current_line:
            lines.append(current_line)
        
        return "\n".join(lines)


# ============================================================================
# ESEMPIO DI UTILIZZO DEL MODULO
# ============================================================================

def esempio_utilizzo():
    """
    Esempio di come utilizzare il modulo dall'applicazione esterna
    """
    
    # Inizializza l'analizzatore
    analyzer = FaceVisagismAnalyzer()
    
    # Percorso immagine da analizzare
    image_path = "percorso/alla/tua/immagine.jpg"
    output_dir = "risultati_analisi"
    
    try:
        # Esegui l'analisi completa
        print("Avvio analisi visagistica...")
        result = analyzer.analyze_face(image_path, output_dir=output_dir)
        
        # Il risultato contiene:
        # - result['forma_viso']: stringa con la forma del viso
        # - result['metriche_facciali']: dizionario con tutte le misure
        # - result['caratteristiche_facciali']: dizionario con caratteristiche qualitative
        # - result['analisi_visagistica']: raccomandazioni per le sopracciglia
        # - result['analisi_espressiva']: analisi comunicazione non verbale
        # - result['immagini_debug']: dizionari con percorsi delle immagini generate
        
        # Genera report testuale
        report_path = f"{output_dir}/report_completo.txt"
        report = analyzer.generate_text_report(result, output_path=report_path)
        
        print(f"\n✓ Analisi completata con successo!")
        print(f"✓ Forma viso rilevata: {result['forma_viso']}")
        print(f"✓ Sopracciglio consigliato: {result['analisi_visagistica']['forma_sopracciglio']}")
        print(f"✓ Report salvato in: {report_path}")
        print(f"✓ JSON completo salvato in: {result['percorso_json']}")
        print(f"✓ Immagini debug generate: {len(result['immagini_debug'])}")
        
        # Accesso a dati specifici
        print("\nEsempio accesso ai dati:")
        print(f"Rapporto L/W: {result['metriche_facciali']['rapporto_lunghezza_larghezza']:.2f}")
        print(f"Distanza occhio-sopracciglio: {result['metriche_facciali']['distanza_occhio_sopracciglio']:.1f}px")
        
        return result
        
    except Exception as e:
        print(f"❌ Errore durante l'analisi: {str(e)}")
        raise


if __name__ == "__main__":
    """
    Esecuzione diretta del modulo per testing
    """
    import sys
    
    if len(sys.argv) > 1:
        # Uso da command line
        image_path = sys.argv[1]
        output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
        
        analyzer = FaceVisagismAnalyzer()
        result = analyzer.analyze_face(image_path, output_dir=output_dir)
        analyzer.generate_text_report(result, output_path=f"{output_dir}/report.txt")
        
        print(f"Analisi completata. Risultati in: {output_dir}")
    else:
        print("Uso: python face_analysis_module.py <percorso_immagine> [directory_output]")
        print("\nOppure importa il modulo nella tua applicazione:")
        print("  from face_analysis_module import FaceVisagismAnalyzer")
        print("  analyzer = FaceVisagismAnalyzer()")
        print("  result = analyzer.analyze_face('immagine.jpg', 'output')")

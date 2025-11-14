#usage :python landmarkPredict.py predictImage  testList.txt

import os
import sys
import numpy as np
import cv2
# import caffe  # Sostituito con MediaPipe per compatibilità
import mediapipe as mp
import dlib
import matplotlib.pyplot as plt

system_height = 650
system_width = 1280
channels = 1
test_num = 1
# pointNum rimosso - ora è dinamico in base ai landmark MediaPipe trovati!

S0_width = 60
S0_height = 60
vgg_height = 224
vgg_width = 224
M_left = -0.15
M_right = +1.15
M_top = -0.10
M_bottom = +1.25
pose_name = ['Pitch', 'Yaw', 'Roll']     # respect to  ['head down','out of plane left','in plane right']

def recover_coordinate(largetBBox, facepoint, width, height):
    point = np.zeros(np.shape(facepoint))
    cut_width = largetBBox[1] - largetBBox[0]
    cut_height = largetBBox[3] - largetBBox[2]
    scale_x = cut_width*1.0/width;
    scale_y = cut_height*1.0/height;
    point[0::2]=[float(j * scale_x + largetBBox[0]) for j in facepoint[0::2]]
    point[1::2]=[float(j * scale_y + largetBBox[2]) for j in facepoint[1::2]]
    return point

def show_image(img, facepoint, bboxs, headpose=None):
    for faceNum in range(0,facepoint.shape[0]):
        # Determina il colore del bounding box basato sulla pose
        bbox_color = (0, 0, 255)  # Rosso di default
        
        if headpose is not None:
            pitch, yaw, roll = headpose[faceNum, 0], headpose[faceNum, 1], headpose[faceNum, 2]
            
            # Considera frontale se tutti gli angoli sono entro ±10 gradi
            if abs(pitch) <= 10 and abs(yaw) <= 10 and abs(roll) <= 10:
                bbox_color = (0, 255, 0)  # Verde per pose frontale
            elif abs(pitch) <= 20 and abs(yaw) <= 20 and abs(roll) <= 20:
                bbox_color = (0, 255, 255)  # Giallo per pose quasi frontale
        
        # Disegna bounding box con colore appropriato
        cv2.rectangle(img, (int(bboxs[faceNum,0]), int(bboxs[faceNum,2])), 
                     (int(bboxs[faceNum,1]), int(bboxs[faceNum,3])), bbox_color, 3)
        
        # Mostra valori di pose
        if headpose is not None:
            for p in range(0,3):
                # Colore del testo basato sul valore
                text_color = (255, 255, 255)  # Bianco di default
                angle_value = headpose[faceNum,p]
                
                if abs(angle_value) <= 10:
                    text_color = (0, 255, 0)  # Verde per valori buoni
                elif abs(angle_value) <= 20:
                    text_color = (0, 255, 255)  # Giallo per valori accettabili
                else:
                    text_color = (0, 0, 255)  # Rosso per valori fuori range
                
                cv2.putText(img, '{:s}: {:.1f}°'.format(pose_name[p], angle_value),
                           (int(bboxs[faceNum,0]), int(bboxs[faceNum,2])-(p+1)*25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2)
        
        # Disegna TUTTI i landmarks con colori diversi per diverse zone del viso
        landmarks_drawn = 0
        for i in range(0, facepoint.shape[1]//2):
            x = int(round(facepoint[faceNum,i*2]))
            y = int(round(facepoint[faceNum,i*2+1]))
            
            # Disegna TUTTI i punti, anche quelli con coordinate zero per debug
            if x >= 0 and y >= 0:
                landmarks_drawn += 1
                
                # Colori diversi per zone diverse del viso
                if i < 17:  # Contorno viso (0-16)
                    color = (255, 0, 0)    # Blu
                    radius = 2
                elif i < 27:  # Sopracciglia (17-26)
                    color = (0, 255, 255)  # Giallo
                    radius = 2
                elif i < 36:  # Naso (27-35)
                    color = (255, 255, 0)  # Ciano
                    radius = 2
                elif i < 48:  # Occhi (36-47)
                    color = (255, 0, 255)  # Magenta
                    radius = 3
                else:  # Bocca (48-67)
                    color = (0, 255, 0)    # Verde
                    radius = 2
                
                # Colore speciale per punti non validi (coordinate molto basse)
                if x <= 1 or y <= 1:
                    color = (128, 128, 128)  # Grigio per punti non validi
                
                cv2.circle(img, (x, y), radius, color, -1)
                
                # Numeri sui landmark per debug (ogni 3° punto per chiarezza)
                if i % 3 == 0:
                    cv2.putText(img, str(i), (x+3, y-3), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 255, 255), 1)
        
        # Mostra conteggio landmark disegnati
        cv2.putText(img, f'Landmarks: {landmarks_drawn}/68', (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Aggiungi legenda colori
    legend_y = 30
    cv2.putText(img, "Landmark Colors:", (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(img, "Face: Blue, Brows: Yellow, Nose: Cyan, Eyes: Magenta, Mouth: Green", 
               (10, legend_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    # Aggiungi stato pose
    if headpose is not None and facepoint.shape[0] > 0:
        pitch, yaw, roll = headpose[0, 0], headpose[0, 1], headpose[0, 2]
        if abs(pitch) <= 10 and abs(yaw) <= 10 and abs(roll) <= 10:
            status_text = "POSE: FRONTALE PERFETTA!"
            status_color = (0, 255, 0)
        elif abs(pitch) <= 20 and abs(yaw) <= 20 and abs(roll) <= 20:
            status_text = "POSE: Quasi frontale"
            status_color = (0, 255, 255)
        else:
            status_text = "POSE: Non frontale"
            status_color = (0, 0, 255)
        
        cv2.putText(img, status_text, (10, img.shape[0] - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
    
    # Ridimensiona se necessario
    height = img.shape[0]
    width = img.shape[1]
    if height > system_height or width > system_width:
        height_radius = system_height*1.0/height
        width_radius = system_width*1.0/width
        radius = min(height_radius,width_radius)
        img = cv2.resize(img, (0,0), fx=radius, fy=radius)

    cv2.imshow('Face Landmark Detection',img)



def recoverPart(point,bbox,left,right,top,bottom,img_height,img_width,height,width):
    largeBBox = getCutSize(bbox,left,right,top,bottom)
    retiBBox = retifyBBoxSize(img_height,img_width,largeBBox)
    recover = recover_coordinate(retiBBox,point,height,width)
    recover=recover.astype('float32')
    return recover


def getRGBTestPart(bbox,left,right,top,bottom,img,height,width):
    largeBBox = getCutSize(bbox,left,right,top,bottom)
    retiBBox = retifyBBox(img,largeBBox)
    # cv2.rectangle(img, (int(retiBBox[0]), int(retiBBox[2])), (int(retiBBox[1]), int(retiBBox[3])), (0,0,255), 2)
    # cv2.imshow('f',img)
    # cv2.waitKey(0)
    face = img[int(retiBBox[2]):int(retiBBox[3]), int(retiBBox[0]):int(retiBBox[1]), :]
    face = cv2.resize(face,(height,width),interpolation = cv2.INTER_AREA)
    face=face.astype('float32')
    return face

def batchRecoverPart(predictPoint,totalBBox,totalSize,left,right,top,bottom,height,width):
    recoverPoint = np.zeros(predictPoint.shape)
    for i in range(0,predictPoint.shape[0]):
        recoverPoint[i] = recoverPart(predictPoint[i],totalBBox[i],left,right,top,bottom,totalSize[i,0],totalSize[i,1],height,width)
    return recoverPoint



def retifyBBox(img,bbox):
    img_height = np.shape(img)[0] - 1
    img_width = np.shape(img)[1] - 1
    if bbox[0] <0:
        bbox[0] = 0
    if bbox[1] <0:
        bbox[1] = 0
    if bbox[2] <0:
        bbox[2] = 0
    if bbox[3] <0:
        bbox[3] = 0
    if bbox[0] > img_width:
        bbox[0] = img_width
    if bbox[1] > img_width:
        bbox[1] = img_width
    if bbox[2]  > img_height:
        bbox[2] = img_height
    if bbox[3]  > img_height:
        bbox[3] = img_height
    return bbox

def retifyBBoxSize(img_height,img_width,bbox):
    if bbox[0] <0:
        bbox[0] = 0
    if bbox[1] <0:
        bbox[1] = 0
    if bbox[2] <0:
        bbox[2] = 0
    if bbox[3] <0:
        bbox[3] = 0
    if bbox[0] > img_width:
        bbox[0] = img_width
    if bbox[1] > img_width:
        bbox[1] = img_width
    if bbox[2]  > img_height:
        bbox[2] = img_height
    if bbox[3]  > img_height:
        bbox[3] = img_height
    return bbox

def getCutSize(bbox,left,right,top,bottom):   #left, right, top, and bottom

    box_width = bbox[1] - bbox[0]
    box_height = bbox[3] - bbox[2]
    cut_size=np.zeros((4))
    cut_size[0] = bbox[0] + left * box_width
    cut_size[1] = bbox[1] + (right - 1) * box_width
    cut_size[2] = bbox[2] + top * box_height
    cut_size[3] = bbox[3] + (bottom-1) * box_height
    return cut_size


def detectFace(img):
    detector = dlib.get_frontal_face_detector()
    dets = detector(img,1)
    bboxs = np.zeros((len(dets),4))
    for i, d in enumerate(dets):
        bboxs[i,0] = d.left();
        bboxs[i,1] = d.right();
        bboxs[i,2] = d.top();
        bboxs[i,3] = d.bottom();
    return bboxs;


def get_all_mediapipe_landmarks(mediapipe_landmarks, img_width, img_height):
    """Estrae TUTTI i landmark MediaPipe (468 punti) senza limitazioni dlib"""
    
    # MediaPipe Face Mesh ha 468 landmark - li prendiamo TUTTI!
    num_landmarks = len(mediapipe_landmarks.landmark)
    print(f"🔥 MediaPipe ha rilevato {num_landmarks} landmark totali!")
    
    # Array dinamico per tutti i punti trovati
    all_landmarks = np.zeros((num_landmarks, 2))
    
    # Estrai OGNI singolo landmark senza limitazioni
    for i in range(num_landmarks):
        landmark = mediapipe_landmarks.landmark[i]
        
        # Coordinate normalizzate da MediaPipe (0.0-1.0)
        x = landmark.x * img_width
        y = landmark.y * img_height
        
        # Validazione coordinate (mantieni dentro l'immagine)
        x = max(1, min(img_width-1, x))
        y = max(1, min(img_height-1, y))
        
        all_landmarks[i, 0] = x
        all_landmarks[i, 1] = y
    
    print(f"✅ Estratti TUTTI i {len(all_landmarks)} landmark MediaPipe!")
    return all_landmarks

def calculate_head_pose(landmarks, img_width, img_height):
    """Calcola la pose della testa (pitch, yaw, roll) dai landmark"""
    
    # Punti di riferimento per il calcolo della pose
    # Usando indici dlib standard
    nose_tip = landmarks[30]  # Punta del naso
    chin = landmarks[8]       # Mento
    left_eye = landmarks[36]  # Angolo interno occhio sinistro
    right_eye = landmarks[45] # Angolo interno occhio destro
    left_mouth = landmarks[48] # Angolo sinistro bocca
    right_mouth = landmarks[54] # Angolo destro bocca
    
    # Punti 3D del modello ideale del volto
    model_points = np.array([
        (0.0, 0.0, 0.0),             # Punta del naso
        (0.0, -330.0, -65.0),        # Mento
        (-225.0, 170.0, -135.0),     # Angolo occhio sinistro
        (225.0, 170.0, -135.0),      # Angolo occhio destro
        (-150.0, -150.0, -125.0),    # Angolo sinistro bocca
        (150.0, -150.0, -125.0)      # Angolo destro bocca
    ], dtype=np.float32)
    
    # Punti 2D corrispondenti dall'immagine
    image_points = np.array([
        nose_tip,
        chin,
        left_eye,
        right_eye,
        left_mouth,
        right_mouth
    ], dtype=np.float32)
    
    # Parametri della camera (approssimati)
    focal_length = img_width
    center = (img_width/2, img_height/2)
    camera_matrix = np.array([
        [focal_length, 0, center[0]],
        [0, focal_length, center[1]],
        [0, 0, 1]
    ], dtype=np.float32)
    
    # Coefficienti di distorsione (assumiamo zero)
    dist_coeffs = np.zeros((4,1))
    
    try:
        # Risolvi PnP per ottenere vettori di rotazione e traslazione
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs)
        
        if success:
            # Converti il vettore di rotazione in matrice di rotazione
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            
            # Estrai gli angoli di Eulero (pitch, yaw, roll)
            # Conversione da matrice di rotazione ad angoli di Eulero
            sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
            
            singular = sy < 1e-6
            
            if not singular:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
                roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180.0 / np.pi
            else:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = 0
                roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1]) * 180.0 / np.pi
            
            return np.array([pitch, yaw, roll])
    except:
        pass
    
    return np.array([0.0, 0.0, 0.0])

def predict_image_webcam():
    # Inizializza MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles
    
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Errore: Impossibile aprire la webcam")
        return
    
    print("Webcam attiva. Premi 'q' per uscire.")

    while True:
        ret, colorImage = cap.read()
        if not ret:
            print("Errore nella lettura del frame")
            break
            
        # Flip orizzontale per effetto specchio
        colorImage = cv2.flip(colorImage, 1)
        
        # Converti BGR to RGB
        rgb_frame = cv2.cvtColor(colorImage, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                h, w = colorImage.shape[:2]
                
                # Ottieni TUTTI i landmark MediaPipe (NON limitati a 68!)
                all_landmarks = get_all_mediapipe_landmarks(face_landmarks, w, h)
                
                # Aggiorna pointNum per riflettere i landmark reali
                actual_pointNum = len(all_landmarks)
                print(f"🎯 Usando {actual_pointNum} landmark invece di soli 68!")
                
                # Converti in formato richiesto dalla funzione show_image  
                predictpoints = np.zeros((1, actual_pointNum*2))
                
                # Copia TUTTI i landmark trovati (non limitati a 68!)
                for i in range(actual_pointNum):
                    predictpoints[0, i*2] = all_landmarks[i, 0]
                    predictpoints[0, i*2+1] = all_landmarks[i, 1]
                
                # Calcola bounding box
                landmarks_x = predictpoints[0, 0::2]
                landmarks_y = predictpoints[0, 1::2]
                valid_x = landmarks_x[landmarks_x > 0]
                valid_y = landmarks_y[landmarks_y > 0]
                
                if len(valid_x) > 0 and len(valid_y) > 0:
                    x_min, x_max = np.min(valid_x), np.max(valid_x)
                    y_min, y_max = np.min(valid_y), np.max(valid_y)
                    
                    margin = 20
                    bboxs = np.array([[max(0, x_min-margin), min(w, x_max+margin), 
                                     max(0, y_min-margin), min(h, y_max+margin)]])
                    
                    # Calcola la pose della testa usando i primi 68 punti per compatibilità
                    if actual_pointNum >= 68:
                        first_68_landmarks = all_landmarks[:68]
                        head_pose = calculate_head_pose(first_68_landmarks, w, h)
                        predictpose = np.array([head_pose])
                    else:
                        # Fallback: pose neutrale
                        head_pose = [0.0, 0.0, 0.0]  # pitch, yaw, roll = 0
                        predictpose = np.array([head_pose])
                    
                    show_image(colorImage, predictpoints, bboxs, predictpose)
                else:
                    cv2.imshow('frame', colorImage)
        else:
            cv2.imshow('frame', colorImage)
            
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    predict_image_webcam()

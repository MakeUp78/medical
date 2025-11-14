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

def get_all_mediapipe_landmarks(mediapipe_landmarks, img_width, img_height):
    """Estrae TUTTI i landmark MediaPipe (468 punti) senza limitazioni dlib"""
    
    # MediaPipe Face Mesh ha 468 landmark - li prendiamo TUTTI!
    num_landmarks = len(mediapipe_landmarks.landmark)
    print(f"🔥 STATIC: MediaPipe ha rilevato {num_landmarks} landmark totali!")
    
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
    
    print(f"✅ STATIC: Estratti TUTTI i {len(all_landmarks)} landmark MediaPipe!")
    return all_landmarks

def calculate_head_pose(landmarks, img_width, img_height):
    """Calcola la pose della testa (pitch, yaw, roll) dai landmark"""
    
    try:
        # Punti chiave per il calcolo della pose
        nose_tip = landmarks[30]    # Punta del naso
        chin = landmarks[8]         # Mento
        left_eye = landmarks[36]    # Angolo interno occhio sinistro
        right_eye = landmarks[45]   # Angolo interno occhio destro
        left_mouth = landmarks[48]  # Angolo sinistro bocca
        right_mouth = landmarks[54] # Angolo destro bocca
        
        # Verifica validità punti
        points_2d = np.array([nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth])
        if np.any(np.isnan(points_2d)) or np.any(points_2d <= 0):
            return np.array([0.0, 0.0, 0.0])
        
        # Modello 3D del volto
        model_points = np.array([
            (0.0, 0.0, 0.0),             # Punta del naso
            (0.0, -330.0, -65.0),        # Mento
            (-225.0, 170.0, -135.0),     # Angolo occhio sinistro
            (225.0, 170.0, -135.0),      # Angolo occhio destro
            (-150.0, -150.0, -125.0),    # Angolo sinistro bocca
            (150.0, -150.0, -125.0)      # Angolo destro bocca
        ], dtype=np.float32)
        
        image_points = np.array([
            nose_tip, chin, left_eye, right_eye, left_mouth, right_mouth
        ], dtype=np.float32)
        
        # Parametri camera
        focal_length = img_width
        center = (img_width/2, img_height/2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float32)
        
        dist_coeffs = np.zeros((4,1))
        
        # Risolvi PnP
        success, rotation_vector, translation_vector = cv2.solvePnP(
            model_points, image_points, camera_matrix, dist_coeffs)
        
        if success:
            rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
            
            # Calcola angoli di Eulero
            sy = np.sqrt(rotation_matrix[0,0]**2 + rotation_matrix[1,0]**2)
            
            if sy > 1e-6:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = np.arctan2(rotation_matrix[1,0], rotation_matrix[0,0]) * 180.0 / np.pi
                roll = np.arctan2(rotation_matrix[2,1], rotation_matrix[2,2]) * 180.0 / np.pi
            else:
                pitch = np.arctan2(-rotation_matrix[2,0], sy) * 180.0 / np.pi
                yaw = 0
                roll = np.arctan2(-rotation_matrix[1,2], rotation_matrix[1,1]) * 180.0 / np.pi
            
            return np.array([pitch, yaw, roll])
            
    except Exception as e:
        pass
    
    return np.array([0.0, 0.0, 0.0])

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
    """Visualizza immagine con landmark e pose migliorati"""
    
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
        
        # Mostra valori di pose usando cv2.putText invece di plt.text
        if headpose is not None:
            for p in range(0,3):
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
        
        # Disegna TUTTI i landmarks con colori diversi per zone del viso
        for i in range(0, facepoint.shape[1]//2):
            x = int(round(facepoint[faceNum,i*2]))
            y = int(round(facepoint[faceNum,i*2+1]))
            
            # Evita di disegnare punti con coordinate invalide
            if x <= 0 or y <= 0:
                continue
                
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
            
            cv2.circle(img, (x, y), radius, color, -1)
    
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
    
    height = img.shape[0]
    width = img.shape[1]
    if height > system_height or width > system_width:
        height_radius = system_height*1.0/height
        width_radius = system_width*1.0/width
        radius = min(height_radius,width_radius)
        img = cv2.resize(img, (0,0), fx=radius, fy=radius)

    # Converti BGR a RGB per matplotlib
    img = img[:,:,[2,1,0]]
    plt.figure(figsize=(15,10))
    plt.imshow(img)
    plt.axis('off')
    plt.title('Face Landmark Detection - MediaPipe Enhanced')
    plt.show()


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


def predictSingleImage(image_path):
    """Funzione per predire landmark da una singola immagine usando MediaPipe"""
    
    print(f"Elaborazione immagine: {image_path}")
    
    # Inizializza MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=True,   # True per immagini statiche
        max_num_faces=5,          # Supporta più volti per immagine
        refine_landmarks=True,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    try:
        # Verifica che il file esista
        if not os.path.exists(image_path):
            print(f"ERRORE: File {image_path} non trovato!")
            return
        
        # Carica immagine
        colorImage = cv2.imread(image_path)
        if colorImage is None:
            print(f"ERRORE: Impossibile caricare {image_path}")
            return
        
        h, w = colorImage.shape[:2]
        print(f"Dimensioni immagine: {w}x{h}")
        
        # Converti BGR to RGB per MediaPipe
        rgb_image = cv2.cvtColor(colorImage, cv2.COLOR_BGR2RGB)
        
        # Processa con MediaPipe
        results = face_mesh.process(rgb_image)
        
        if results.multi_face_landmarks:
            faceNum = len(results.multi_face_landmarks)
            print(f"Rilevati {faceNum} volti")
            
            # Prima passata per determinare il numero massimo di landmark
            max_landmarks = 0
            all_face_landmarks = []
            
            for face_landmarks in results.multi_face_landmarks:
                # Estrai TUTTI i landmark MediaPipe (NON limitati a 68!)
                all_landmarks = get_all_mediapipe_landmarks(face_landmarks, w, h)
                all_face_landmarks.append(all_landmarks)
                max_landmarks = max(max_landmarks, len(all_landmarks))
            
            print(f"🎯 STATIC: Usando {max_landmarks} landmark per volto invece di soli 68!")
            
            # Array dinamico basato sui landmark reali
            predictpoints = np.zeros((faceNum, max_landmarks*2))
            predictpose = np.zeros((faceNum, 3))
            bboxs = np.zeros((faceNum, 4))
            
            for i, all_landmarks in enumerate(all_face_landmarks):
                # Popola array predictpoints con TUTTI i landmark
                for j in range(len(all_landmarks)):
                    predictpoints[i, j*2] = all_landmarks[j, 0]
                    predictpoints[i, j*2+1] = all_landmarks[j, 1]
                
                # Calcola bounding box
                landmarks_x = predictpoints[i, 0::2]
                landmarks_y = predictpoints[i, 1::2]
                valid_x = landmarks_x[landmarks_x > 0]
                valid_y = landmarks_y[landmarks_y > 0]
                
                if len(valid_x) > 0 and len(valid_y) > 0:
                    x_min, x_max = np.min(valid_x), np.max(valid_x)
                    y_min, y_max = np.min(valid_y), np.max(valid_y)
                    
                    margin = 20
                    bboxs[i] = [max(0, x_min-margin), min(w, x_max+margin), 
                               max(0, y_min-margin), min(h, y_max+margin)]
                
                # Calcola pose della testa usando i primi 68 punti per compatibilità
                if len(all_landmarks) >= 68:
                    first_68_landmarks = all_landmarks[:68]
                    head_pose = calculate_head_pose(first_68_landmarks, w, h)
                    predictpose[i] = head_pose
                    print(f"Volto {i+1}: Pose -> Pitch: {head_pose[0]:.1f}°, Yaw: {head_pose[1]:.1f}°, Roll: {head_pose[2]:.1f}°")
                else:
                    # Fallback: pose neutrale
                    head_pose = [0.0, 0.0, 0.0]
                    predictpose[i] = head_pose
                    print(f"Volto {i+1}: Pose neutrale (meno di 68 landmark)")
            
            # Mostra risultato
            show_image(colorImage, predictpoints, bboxs, predictpose)
            print(f"✅ Elaborazione completata per {image_path}")
        else:
            print(f"❌ Nessun volto rilevato in {image_path}")
    
    except Exception as e:
        print(f"ERRORE durante l'elaborazione: {e}")
    finally:
        face_mesh.close()

def predictImage(filename):
    """Funzione per predire landmark da file di immagini usando MediaPipe"""
    
    print("Inizializzazione MediaPipe Face Mesh...")
    
    # Inizializza MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    
    face_mesh = mp_face_mesh.FaceMesh(
        static_image_mode=True,   # True per immagini statiche
        max_num_faces=5,          # Supporta più volti per immagine
        refine_landmarks=True,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )
    
    try:
        f = open(filename, 'r', encoding='utf-8')
        line = f.readline()
        index = 0

        while line:
            print("Processing image", index)
            line = line.strip()
            info = line.split(' ')
            imgPath = info[0]
            print("Image path:", imgPath)
            
            # Verifica che il file esista
            if not os.path.exists(imgPath):
                print(f"ATTENZIONE: File {imgPath} non trovato!")
                line = f.readline()
                index = index + 1
                continue
            
            # Carica immagine
            colorImage = cv2.imread(imgPath)
            if colorImage is None:
                print(f"ERRORE: Impossibile caricare {imgPath}")
                line = f.readline()
                index = index + 1
                continue
            
            h, w = colorImage.shape[:2]
            print(f"Dimensioni immagine: {w}x{h}")
            
            # Converti BGR to RGB per MediaPipe
            rgb_image = cv2.cvtColor(colorImage, cv2.COLOR_BGR2RGB)
            
            # Processa con MediaPipe
            results = face_mesh.process(rgb_image)
            
            if results.multi_face_landmarks:
                faceNum = len(results.multi_face_landmarks)
                print(f"Rilevati {faceNum} volti")
                
                # Use 468 landmarks (MediaPipe Face Mesh standard) or determine dynamically
                max_landmarks = 468  # MediaPipe Face Mesh has 468 landmarks
                predictpoints = np.zeros((faceNum, max_landmarks*2))
                max_landmarks = 0
                all_face_landmarks = []
                
                for face_landmarks in results.multi_face_landmarks:
                    # Estrai TUTTI i landmark MediaPipe (NON limitati a 68!)
                    all_landmarks = get_all_mediapipe_landmarks(face_landmarks, w, h)
                    all_face_landmarks.append(all_landmarks)
                    max_landmarks = max(max_landmarks, len(all_landmarks))
                
                print(f"🎯 BATCH: Usando {max_landmarks} landmark per volto invece di soli 68!")
                
                # Array dinamico basato sui landmark reali
                predictpoints = np.zeros((faceNum, max_landmarks*2))
                predictpose = np.zeros((faceNum, 3))
                bboxs = np.zeros((faceNum, 4))
                
                for i, all_landmarks in enumerate(all_face_landmarks):
                    # Popola array predictpoints con TUTTI i landmark
                    for j in range(len(all_landmarks)):
                        predictpoints[i, j*2] = all_landmarks[j, 0]
                        predictpoints[i, j*2+1] = all_landmarks[j, 1]
                    
                    # Calcola bounding box dal volto
                    valid_x = [x for x in predictpoints[i, 0::2] if x > 0]
                    valid_y = [y for y in predictpoints[i, 1::2] if y > 0]
                    
                    if valid_x and valid_y:
                        x_min, x_max = min(valid_x), max(valid_x)
                        y_min, y_max = min(valid_y), max(valid_y)
                        
                        margin = 30
                        bboxs[i] = [
                            max(0, x_min-margin),      # x_min
                            min(w, x_max+margin),      # x_max
                            max(0, y_min-margin),      # y_min
                            min(h, y_max+margin)       # y_max
                        ]
                        
                        # Calcola pose della testa usando i primi 68 punti per compatibilità
                        if len(all_landmarks) >= 68:
                            first_68_landmarks = all_landmarks[:68]
                            head_pose = calculate_head_pose(first_68_landmarks, w, h)
                        else:
                            head_pose = np.array([0.0, 0.0, 0.0])
                        predictpose[i] = head_pose
                        
                        print(f"Volto {i+1}: Pitch={head_pose[0]:.1f}°, Yaw={head_pose[1]:.1f}°, Roll={head_pose[2]:.1f}°")
                
                # Mostra risultati
                show_image(colorImage.copy(), predictpoints, bboxs, predictpose)
            else:
                print("Nessun volto rilevato nell'immagine")
                # Mostra comunque l'immagine
                plt.figure(figsize=(12, 8))
                plt.imshow(cv2.cvtColor(colorImage, cv2.COLOR_BGR2RGB))
                plt.axis('off')
                plt.title(f'Nessun volto rilevato - {os.path.basename(imgPath)}')
                plt.show()
            
            line = f.readline()
            index = index + 1
            
        f.close()
        
    except FileNotFoundError:
        print(f"ERRORE: File {filename} non trovato!")
    except Exception as e:
        print(f"ERRORE durante l'elaborazione: {e}")
    finally:
        face_mesh.close()
        print("Elaborazione completata.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        func = globals()[sys.argv[1]]
        func(*sys.argv[2:])
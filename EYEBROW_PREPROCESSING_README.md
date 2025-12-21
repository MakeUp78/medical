# Eyebrow Preprocessing Workflow - Documentation

## Overview

This feature enhances the green dots detection workflow for facial images by introducing advanced preprocessing and visualization specifically targeting eyebrow regions.

## Features

### 1. Backend Preprocessing (`src/green_dots_processor.py`)

The `GreenDotsProcessor` class has been extended with the following new methods:

#### `detect_eyebrow_landmarks(image)`
- Detects eyebrow landmarks using MediaPipe Face Mesh
- Returns landmarks for left and right eyebrows
- Uses MediaPipe indices optimized for eyebrow detection

#### `calculate_eyebrow_bounding_box_from_landmarks(landmarks, expand_factor)`
- Calculates bounding boxes for eyebrow regions
- Supports expansion factor for additional context (default: 50%)
- Returns coordinates in (x_min, y_min, x_max, y_max) format

#### `create_eyebrow_mask(image_size, bbox)`
- Generates binary masks from bounding boxes
- Masks are used to extract only eyebrow regions

#### `apply_color_correction(image, mask)`
- Applies color correction to emphasize green hues
- Desaturates skin tones to improve green dot detection
- Uses HSV color space for precise color manipulation

#### `preprocess_eyebrow_region(image, side, expand_factor, apply_color_correction_flag)`
- Main preprocessing workflow method
- Combines all preprocessing steps
- Returns debug images and metadata

### 2. Backend API (`webapp/api/main.py`)

#### New Endpoint: `POST /api/eyebrow/preprocess`

**Request:**
```json
{
  "image": "data:image/png;base64,...",
  "side": "left" | "right",
  "expand_factor": 0.5,
  "apply_color_correction": true
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "uuid",
  "side": "left",
  "landmarks": [{"x": 100, "y": 150, "z": 0.1}, ...],
  "bbox": {
    "x_min": 50,
    "y_min": 100,
    "x_max": 200,
    "y_max": 180,
    "width": 150,
    "height": 80
  },
  "mask_area": 12000,
  "debug_images": {
    "bbox_overlay": "data:image/png;base64,...",
    "mask": "data:image/png;base64,...",
    "masked_region": "data:image/png;base64,...",
    "color_corrected": "data:image/png;base64,..."
  },
  "preprocessing_metadata": {
    "expand_factor": 0.5,
    "color_correction_applied": true,
    "landmarks_count": 10,
    "bbox_area": 12000,
    "mask_area": 12000
  },
  "timestamp": "2025-12-21T03:00:00.000Z"
}
```

### 3. Frontend Visualization (`webapp/static/js/eyebrow-preprocessing.js`)

#### Main Functions:

##### `preprocessLeftEyebrow()` / `preprocessRightEyebrow()`
- Entry points for preprocessing workflow
- Call API and visualize results

##### `callPreprocessingAPI(imageBase64, side, expandFactor, applyColorCorrection)`
- Handles API communication
- Returns preprocessing results

##### `addDebugImageOverlay(imageDataUrl, layerName, opacity)`
- Adds debug images as overlays on canvas
- Supports multiple layers with different opacities

##### `drawBoundingBox(bbox, color, lineWidth)`
- Visualizes bounding boxes on canvas
- Customizable colors and line widths

##### `drawLandmarks(landmarks, color, radius)`
- Draws eyebrow landmarks as circles on canvas
- Color-coded for easy identification

##### `showDebugImagesWindow(debugImages, side, bbox, landmarks)`
- Opens modal window with all debug images
- Displays preprocessing metadata
- Allows zooming and downloading

##### `addPreprocessingMetadataToTable(metadata, side)`
- Adds preprocessing data to Data Analysis table
- Shows landmarks count, bbox area, mask area, etc.

##### `clearAllPreprocessing()`
- Removes all preprocessing overlays and metadata
- Resets preprocessing state

## Usage

### Step 1: Load an Image
Load a facial image in the application using one of the source options (file upload, webcam, video).

### Step 2: Access Preprocessing
Navigate to the "CORREZIONE PROGETTAZIONE" section in the left sidebar.

### Step 3: Run Preprocessing
Click one of the preprocessing buttons:
- **🔬 Preprocessa Sinistro** - Preprocess left eyebrow
- **🔬 Preprocessa Destro** - Preprocess right eyebrow

### Step 4: View Results
The system will:
1. Detect eyebrow landmarks using MediaPipe
2. Calculate and expand bounding box
3. Generate mask for the region
4. Apply color correction (optional)
5. Display debug images in a modal window
6. Add metadata to the Data Analysis table
7. Draw bounding box and landmarks on canvas

### Step 5: Clean Up
Use **🗑️ Pulisci Preprocessing** button to remove all preprocessing overlays and metadata.

## Debug Images

The preprocessing generates 4 debug images:

1. **📐 Bounding Box + Landmarks**
   - Shows the original image with bounding box rectangle
   - Red dots indicate detected eyebrow landmarks

2. **🎭 Maschera Regione**
   - Binary mask visualization
   - White areas show the eyebrow region of interest

3. **✂️ Regione Estratta**
   - Extracted eyebrow region
   - Background is masked out (black)

4. **🎨 Correzione Colore**
   - Color-corrected image
   - Green hues enhanced, skin tones desaturated

## Data Analysis Table

The preprocessing metadata is added to the measurements table:

| Tipo Misurazione | Valore | Unità | Stato |
|-----------------|--------|-------|-------|
| Landmarks Rilevati | 10 | punti | ✅ OK |
| Bounding Box Area | 12000 | px² | ✅ OK |
| Mask Area | 12000 | px² | ✅ OK |
| Expand Factor | 50 | % | ✅ OK |
| Color Correction | Applicata | | ✅ OK |

## Technical Details

### Dependencies

**Backend:**
- OpenCV (`opencv-python`) - Image processing
- MediaPipe (`mediapipe`) - Facial landmark detection
- NumPy (`numpy`) - Numerical operations
- Pillow (`PIL`) - Image manipulation

**Frontend:**
- Fabric.js - Canvas manipulation
- Fetch API - Backend communication

### MediaPipe Eyebrow Indices

Left Eyebrow: `[70, 63, 105, 66, 107, 55, 65, 52, 53, 46]`
Right Eyebrow: `[300, 293, 334, 296, 336, 285, 295, 282, 283, 276]`

### Color Correction Algorithm

1. Convert image to HSV color space
2. Identify green pixels (hue 30-90°)
3. Increase saturation by 30% for green pixels
4. Identify skin tone pixels (hue 0-30°)
5. Decrease saturation by 30% for skin pixels
6. Convert back to BGR color space

## Troubleshooting

### "MediaPipe non disponibile"
**Solution:** Ensure MediaPipe is installed: `pip install mediapipe`

### "Impossibile rilevare landmarks facciali"
**Solutions:**
- Ensure the image contains a clear, frontal face
- Check image quality and lighting
- Verify the face is not too far or too close

### "Bounding box non valido"
**Solutions:**
- Try with a different image
- Ensure eyebrows are visible in the image
- Check that green dots are present

### Debug images not displaying
**Solutions:**
- Check browser console for errors
- Ensure Fabric.js is loaded correctly
- Verify canvas is initialized

## Future Enhancements

Potential improvements for this feature:

1. **Adaptive Expansion**: Automatically adjust expansion factor based on eyebrow size
2. **Multiple Color Spaces**: Support different color correction algorithms
3. **Batch Processing**: Process both eyebrows simultaneously
4. **History**: Save and compare preprocessing results over time
5. **Export**: Export debug images as a report
6. **Real-time Preview**: Show preprocessing results in real-time as parameters change

## API Testing

You can test the API endpoint using curl:

```bash
curl -X POST http://localhost:8001/api/eyebrow/preprocess \
  -H "Content-Type: application/json" \
  -d '{
    "image": "data:image/png;base64,iVBORw0KGgo...",
    "side": "left",
    "expand_factor": 0.5,
    "apply_color_correction": true
  }'
```

Or using the FastAPI interactive documentation at: `http://localhost:8001/docs`

## Support

For issues or questions, please refer to:
- Main project README
- API documentation at `/docs` endpoint
- GitHub issues

---

**Version:** 1.0  
**Last Updated:** 2025-12-21  
**Author:** GitHub Copilot

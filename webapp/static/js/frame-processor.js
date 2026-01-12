// ============================================================================
// FRAME PROCESSOR UNIFICATO
// Gestisce cattura, standardizzazione e analisi di frame da qualsiasi sorgente
// ============================================================================

const FRAME_CONFIG = {
  standardWidth: 1280,
  standardHeight: 720,
  jpegQuality: 0.7,
  maxBufferSize: 10,
  earlyStopThreshold: 0.92,
  minFramesForEarlyStop: 5,
  samplingInterval: 66 // ~15 FPS
};

// ============================================================================
// TOP-K BUFFER
// ============================================================================
class TopKFrameBuffer {
  constructor(maxSize = 10, earlyStopThreshold = 0.92) {
    this.frames = [];
    this.maxSize = maxSize;
    this.earlyStopThreshold = earlyStopThreshold;
    this.totalProcessed = 0;
  }

  add(frameData) {
    this.totalProcessed++;
    const score = frameData.result?.frontality_score || frameData.score || 0;

    if (this.frames.length < this.maxSize) {
      this.frames.push(frameData);
      this.frames.sort((a, b) => this._getScore(b) - this._getScore(a));
    } else if (score > this._getScore(this.frames[this.frames.length - 1])) {
      this.frames[this.frames.length - 1] = frameData;
      this.frames.sort((a, b) => this._getScore(b) - this._getScore(a));
    }
  }

  _getScore(frameData) {
    return frameData.result?.frontality_score || frameData.score || 0;
  }

  getBest() {
    return this.frames[0];
  }

  getTop(n = 10) {
    return this.frames.slice(0, n);
  }

  shouldEarlyStop() {
    if (this.frames.length < FRAME_CONFIG.minFramesForEarlyStop) return false;
    return this._getScore(this.frames[0]) >= this.earlyStopThreshold;
  }

  get bestScore() {
    return this.frames.length > 0 ? this._getScore(this.frames[0]) : 0;
  }

  get worstScore() {
    return this.frames.length > 0 ? this._getScore(this.frames[this.frames.length - 1]) : 0;
  }

  get size() {
    return this.frames.length;
  }

  clear() {
    this.frames = [];
    this.totalProcessed = 0;
  }
}

// ============================================================================
// FRAME SOURCE ABSTRACTION
// ============================================================================
class FrameSource {
  constructor(source, type) {
    this.source = source;
    this.type = type; // 'image', 'video', 'webcam'
    this.isActive = false;
  }

  async captureFrame(time = null) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    switch (this.type) {
      case 'image': {
        const img = this.source;
        canvas.width = img.naturalWidth || img.width;
        canvas.height = img.naturalHeight || img.height;
        ctx.drawImage(img, 0, 0);
        break;
      }
      case 'video': {
        const video = this.source;
        if (time !== null) {
          video.currentTime = time;
          await new Promise(resolve => {
            const onSeeked = () => {
              video.removeEventListener('seeked', onSeeked);
              resolve();
            };
            video.addEventListener('seeked', onSeeked);
          });
        }
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        break;
      }
      case 'webcam': {
        const video = this.source;
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        break;
      }
    }

    return canvas;
  }

  isStreamSource() {
    return this.type === 'video' || this.type === 'webcam';
  }

  getDuration() {
    if (this.type === 'video') {
      return this.source.duration;
    }
    return null;
  }
}

// ============================================================================
// STANDARDIZZAZIONE RISOLUZIONE
// ============================================================================
function standardizeResolution(sourceCanvas, targetWidth = FRAME_CONFIG.standardWidth, targetHeight = FRAME_CONFIG.standardHeight) {
  const canvas = document.createElement('canvas');
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const ctx = canvas.getContext('2d');

  const sourceRatio = sourceCanvas.width / sourceCanvas.height;
  const targetRatio = targetWidth / targetHeight;

  let drawWidth, drawHeight, offsetX = 0, offsetY = 0;

  if (sourceRatio > targetRatio) {
    drawHeight = targetHeight;
    drawWidth = sourceCanvas.width * (targetHeight / sourceCanvas.height);
    offsetX = (targetWidth - drawWidth) / 2;
  } else {
    drawWidth = targetWidth;
    drawHeight = sourceCanvas.height * (targetWidth / sourceCanvas.width);
    offsetY = (targetHeight - drawHeight) / 2;
  }

  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, targetWidth, targetHeight);
  ctx.drawImage(sourceCanvas, offsetX, offsetY, drawWidth, drawHeight);

  return canvas;
}

// ============================================================================
// FRAME PROCESSOR PRINCIPALE
// ============================================================================
class UnifiedFrameProcessor {
  constructor() {
    this.buffer = new TopKFrameBuffer(FRAME_CONFIG.maxBufferSize, FRAME_CONFIG.earlyStopThreshold);
    this.isProcessing = false;
    this.intervalId = null;
  }

  async processFrame(frameSource, timestamp = Date.now(), options = {}) {
    try {
      const rawCanvas = await frameSource.captureFrame(options.time);
      const standardCanvas = standardizeResolution(rawCanvas);
      const base64Image = standardCanvas.toDataURL('image/jpeg', FRAME_CONFIG.jpegQuality);

      const result = await analyzeImageViaAPI(base64Image);

      if (result && result.frontality_score) {
        const frameData = {
          canvas: rawCanvas,
          standardCanvas: standardCanvas,
          result: result,
          timestamp: timestamp,
          time: options.time || 0,
          sourceType: frameSource.type
        };

        this.buffer.add(frameData);

        if (options.onFrameProcessed) {
          options.onFrameProcessed(frameData);
        }

        return frameData;
      }
    } catch (error) {
      // Non logga errori di "nessun volto rilevato" - sono normali in alcuni frame
      if (!error.message || !error.message.includes('Nessun volto rilevato')) {
        console.error('Frame processing error:', error);
      }
      return null;
    }
  }

  async processSingleFrame(frameSource) {
    this.isProcessing = true;
    const result = await this.processFrame(frameSource);
    this.isProcessing = false;
    return result;
  }

  async processStream(frameSource, options = {}) {
    if (this.isProcessing) return;

    this.isProcessing = true;
    this.buffer.clear();

    const duration = frameSource.getDuration();
    const stepSize = options.stepSize || 0.33;

    if (frameSource.type === 'video' && duration) {
      for (let time = 0; time < duration; time += stepSize) {
        if (!this.isProcessing) break;

        await this.processFrame(frameSource, Date.now(), { time, onFrameProcessed: options.onProgress });

        if (this.buffer.shouldEarlyStop()) {
          console.log('Early stop - excellent frame found');
          break;
        }

        await new Promise(resolve => setTimeout(resolve, 100));
      }
    } else if (frameSource.type === 'webcam') {
      this.intervalId = setInterval(async () => {
        if (!this.isProcessing) {
          clearInterval(this.intervalId);
          return;
        }

        await this.processFrame(frameSource, Date.now(), { onFrameProcessed: options.onProgress });

        if (this.buffer.shouldEarlyStop() && this.buffer.size >= FRAME_CONFIG.minFramesForEarlyStop) {
          this.stop();
        }
      }, FRAME_CONFIG.samplingInterval);
    }

    if (options.onComplete) {
      if (frameSource.type === 'webcam') {
        return;
      }
      this.isProcessing = false;
      options.onComplete(this.buffer.getTop());
    }
  }

  stop() {
    this.isProcessing = false;
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  getResults() {
    return this.buffer.getTop();
  }

  getBestFrame() {
    return this.buffer.getBest();
  }
}

// Export globale
window.TopKFrameBuffer = TopKFrameBuffer;
window.FrameSource = FrameSource;
window.UnifiedFrameProcessor = UnifiedFrameProcessor;
window.standardizeResolution = standardizeResolution;
window.FRAME_CONFIG = FRAME_CONFIG;

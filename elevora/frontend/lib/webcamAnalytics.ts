import type { FaceLandmarkerResult } from "@mediapipe/tasks-vision";

/**
 * Client-side face-visibility/movement tracking for the interview room.
 *
 * CONFIDENCE NOTE — read this before trusting the numbers this produces:
 *
 * The API calls below (FilesetResolver.forVisionTasks, FaceLandmarker.
 * createFromOptions, detectForVideo, the FaceLandmarkerResult shape) were
 * checked against the actual installed @mediapipe/tasks-vision@1.0.1
 * package's vision.d.ts in this sandbox — not recalled from training data.
 * That part is as solid as reading real source can make it.
 *
 * What was NOT verified, because no camera or browser exists here:
 *   - That the model actually downloads and initializes correctly at
 *     runtime from the CDN URL below.
 *   - That detectForVideo() behaves as expected against a live video feed
 *     rather than a static image.
 *   - The "looking away" math below (see estimateForwardAlignment).
 *
 * This is, by a meaningful margin, the least-verified code in the entire
 * project — more uncertain than VoiceControls or CameraPreview, because
 * those wrap simple, long-stable browser APIs (getUserMedia,
 * MediaRecorder) I'm confident about independent of any package version.
 * This wraps a specific ML package version whose model files live on a
 * CDN I can't reach from here to confirm are still at this path.
 *
 * Fails silently everywhere on purpose: if this breaks, webcam metrics
 * just don't get submitted (Delivery/webcam stay "Not available" on the
 * report) rather than breaking the interview itself.
 */

const WASM_BASE_URL =
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";
const FACE_LANDMARKER_MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

// A face turned directly at the camera has a forward-alignment (see below)
// close to 1. Below this threshold counts as "looking away" for one sample.
const LOOKING_AWAY_THRESHOLD = 0.85;

// Frame-to-frame landmark centroid displacement (in normalized 0-1
// coordinates) above this counts as "movement" for one sample. Not
// calibrated against real recordings.
const MOVEMENT_THRESHOLD = 0.015;

/**
 * Approximates how directly the face points at the camera using the
 * (2,2) entry of the 4x4 facial transformation matrix MediaPipe provides.
 *
 * Why this specific entry, and why it's more robust than it looks: that
 * entry sits on the matrix diagonal, so it has the same flattened array
 * index (10) whether the matrix is row-major or column-major — the two
 * conventions only disagree on off-diagonal entries. For a rotation matrix
 * representing "how the canonical face is rotated to match the detected
 * face," that diagonal entry approximates the cosine of the angle between
 * the face's forward direction and the camera's viewing axis: close to 1
 * facing the camera, dropping as the head turns in ANY direction (yaw,
 * pitch, or both). Using this magnitude — rather than trying to recover a
 * signed yaw/pitch/roll — deliberately avoids needing to get the exact
 * row/column-major convention and axis-sign convention right, since a
 * mistake there would silently flip left/right or up/down without
 * crashing anything. This does mean the tracker can say "looking away"
 * without saying which way — an acceptable trade for something that
 * could not be checked against a real face.
 */
function estimateForwardAlignment(result: FaceLandmarkerResult): number | null {
  const matrix = result.facialTransformationMatrixes?.[0];
  if (!matrix || matrix.data.length < 16) return null;
  return matrix.data[10]; // index 10 = row 2, col 2 either way (see above)
}

function landmarkCentroid(result: FaceLandmarkerResult): { x: number; y: number } | null {
  const landmarks = result.faceLandmarks?.[0];
  if (!landmarks || landmarks.length === 0) return null;
  let x = 0;
  let y = 0;
  for (const point of landmarks) {
    x += point.x;
    y += point.y;
  }
  return { x: x / landmarks.length, y: y / landmarks.length };
}

export interface WebcamAnalyticsAggregate {
  faceVisibleRate: number;
  lookingAwayRate: number;
  movementRate: number;
  sampledFrames: number;
}

export class WebcamAnalyticsTracker {
  private landmarker: import("@mediapipe/tasks-vision").FaceLandmarker | null = null;
  private initFailed = false;
  private initPromise: Promise<void> | null = null;

  private totalSamples = 0;
  private faceVisibleSamples = 0;
  private lookingAwaySamples = 0;
  private movementSamples = 0;
  private lastCentroid: { x: number; y: number } | null = null;

  private async ensureInitialized(): Promise<void> {
    if (this.landmarker || this.initFailed) return;
    if (this.initPromise) return this.initPromise;

    this.initPromise = (async () => {
      try {
        const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
        const filesetResolver = await FilesetResolver.forVisionTasks(WASM_BASE_URL);
        this.landmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
          baseOptions: { modelAssetPath: FACE_LANDMARKER_MODEL_URL, delegate: "GPU" },
          runningMode: "VIDEO",
          numFaces: 1,
          outputFacialTransformationMatrixes: true,
        });
      } catch {
        this.initFailed = true;
      }
    })();

    return this.initPromise;
  }

  /** Call roughly once per second with the interview room's video element.
   * Safe to call even if initialization hasn't finished or has failed —
   * it just no-ops. Never throws. */
  async sample(video: HTMLVideoElement): Promise<void> {
    try {
      await this.ensureInitialized();
      if (!this.landmarker || video.readyState < 2) return;

      const result = this.landmarker.detectForVideo(video, performance.now());
      this.totalSamples += 1;

      const hasFace = (result.faceLandmarks?.length ?? 0) > 0;
      if (!hasFace) return; // don't count alignment/movement for a frame with no face

      this.faceVisibleSamples += 1;

      const alignment = estimateForwardAlignment(result);
      if (alignment !== null && alignment < LOOKING_AWAY_THRESHOLD) {
        this.lookingAwaySamples += 1;
      }

      const centroid = landmarkCentroid(result);
      if (centroid) {
        if (this.lastCentroid) {
          const dx = centroid.x - this.lastCentroid.x;
          const dy = centroid.y - this.lastCentroid.y;
          const displacement = Math.sqrt(dx * dx + dy * dy);
          if (displacement > MOVEMENT_THRESHOLD) this.movementSamples += 1;
        }
        this.lastCentroid = centroid;
      }
    } catch {
      // Never let analytics collection break the interview.
    }
  }

  /** Returns the aggregate, or null if too little data was collected to be
   * worth submitting (init failed, camera was off the whole time, etc.). */
  getAggregate(): WebcamAnalyticsAggregate | null {
    if (this.totalSamples < 3) return null;
    return {
      faceVisibleRate: this.faceVisibleSamples / this.totalSamples,
      lookingAwayRate: this.faceVisibleSamples > 0 ? this.lookingAwaySamples / this.faceVisibleSamples : 0,
      movementRate: this.faceVisibleSamples > 0 ? this.movementSamples / this.faceVisibleSamples : 0,
      sampledFrames: this.totalSamples,
    };
  }
}

"""
Vision layer for NeuroHex.

Converts camera frames into a single looming-strength signal in [0, 1] that
drives the LC4/LPLC2 visual sensory neurons in the SNN (see snn_brain.py).

Looming (an object rapidly approaching/expanding in the visual field, as
opposed to something merely moving sideways) is detected via the divergence
of the dense optical flow field: an expanding object produces flow vectors
that point radially outward from a focus of expansion, which shows up as
positive divergence. Simple panning/translation does not produce this
signature, which is what makes divergence a reasonable cheap proxy for
"is something approaching me" rather than "is something moving".

Camera backend: tries picamera2 first (the only working path for a
Raspberry Pi CSI camera module on modern Raspberry Pi OS -- Bookworm and
later dropped the legacy V4L2 camera stack, so plain cv2.VideoCapture opens
the device node but never actually reads a frame from it), then falls back
to cv2.VideoCapture (USB webcams, or a Mac's built-in camera during dev),
then to a synthetic expanding-circle stimulus if neither is available, so
the rest of the pipeline (SNN + motor layer) can still be developed and
tested without a camera at all.
"""

import cv2
import numpy as np

try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except Exception:
    _PICAMERA2_AVAILABLE = False


class LoomingDetector:
    def __init__(self, camera_index=0, frame_width=320, frame_height=240):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.backend = None
        self._picam2 = None
        self.cap = None

        if _PICAMERA2_AVAILABLE:
            try:
                self._picam2 = Picamera2()
                config = self._picam2.create_preview_configuration(
                    main={"size": (frame_width, frame_height), "format": "RGB888"}
                )
                self._picam2.configure(config)
                self._picam2.start()
                self.backend = 'picamera2'
            except Exception as e:
                print(f"Warning: picamera2 present but failed to start ({e}); trying OpenCV instead.")
                self._picam2 = None

        if self.backend is None:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    self.cap = cap
                    self.backend = 'opencv'
                else:
                    cap.release()

        self.available = self.backend is not None
        if not self.available:
            print(f"Warning: no usable camera found (tried picamera2 and OpenCV index {camera_index}). "
                  "LoomingDetector will generate a synthetic looming stimulus instead.")

        self.prev_gray = None
        self._synthetic_t = 0

    def _read_frame_gray(self):
        if self.backend == 'picamera2':
            frame = self._picam2.capture_array()
            return cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        elif self.backend == 'opencv':
            ok, frame = self.cap.read()
            if not ok:
                return None
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            return self._synthetic_frame()

    def read_looming_signal(self):
        """Returns a float in [0, 1]: 0 = no threat, 1 = maximal looming."""
        gray = self._read_frame_gray()
        if gray is None:
            return 0.0

        if self.prev_gray is None:
            self.prev_gray = gray
            return 0.0

        flow = cv2.calcOpticalFlowFarneback(
            self.prev_gray, gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0
        )
        self.prev_gray = gray

        divergence = self._flow_divergence(flow)
        # Looming = positive divergence (expansion). Contraction/negative
        # regions aren't threat-relevant here, so they're excluded rather
        # than allowed to cancel out real expansion elsewhere in the frame.
        expansion = np.clip(divergence, 0, None)
        looming_strength = float(np.mean(expansion))

        # NOTE: this scale factor is a rough starting point, not a calibrated
        # constant -- validated only against a MacBook webcam during dev.
        # Expect to retune it against this camera/lens once mounted on the
        # actual robot (distance-to-threat and FOV will both differ).
        normalized = np.clip(looming_strength * 40.0, 0.0, 1.0)
        return normalized

    @staticmethod
    def _flow_divergence(flow):
        fx, fy = flow[..., 0], flow[..., 1]
        dfx_dx = np.gradient(fx, axis=1)
        dfy_dy = np.gradient(fy, axis=0)
        return dfx_dx + dfy_dy

    def _synthetic_frame(self):
        """Synthetic expanding-circle stimulus, for development without a camera."""
        frame = np.zeros((self.frame_height, self.frame_width), dtype=np.uint8)
        self._synthetic_t += 1
        cycle = self._synthetic_t % 60
        radius = 5 + int(cycle * 1.5)
        center = (self.frame_width // 2, self.frame_height // 2)
        cv2.circle(frame, center, radius, 255, -1)
        return frame

    def release(self):
        if self.backend == 'picamera2':
            self._picam2.stop()
            self._picam2.close()
        elif self.backend == 'opencv':
            self.cap.release()


if __name__ == '__main__':
    print("Running LoomingDetector standalone (Ctrl+C to stop)...")
    detector = LoomingDetector()
    print(f"Backend: {detector.backend or 'synthetic (no camera found)'}")
    try:
        for i in range(100):
            signal = detector.read_looming_signal()
            print(f"frame {i:3d} | looming_signal = {signal:.3f}")
    except KeyboardInterrupt:
        pass
    finally:
        detector.release()

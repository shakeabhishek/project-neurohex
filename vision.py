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

On a machine with no camera (or without camera permission granted to this
process), falls back to a synthetic expanding-circle stimulus so the rest of
the pipeline (SNN + motor layer) can still be developed and tested.
"""

import cv2
import numpy as np


class LoomingDetector:
    def __init__(self, camera_index=0, frame_width=320, frame_height=240):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.cap = cv2.VideoCapture(camera_index)
        self.available = self.cap.isOpened()
        if not self.available:
            print(f"Warning: could not open camera {camera_index} (no camera, or permission not granted). "
                  "LoomingDetector will generate a synthetic looming stimulus instead.")
        self.prev_gray = None
        self._synthetic_t = 0

    def read_looming_signal(self):
        """Returns a float in [0, 1]: 0 = no threat, 1 = maximal looming."""
        if self.available:
            ok, frame = self.cap.read()
            if not ok:
                return 0.0
            frame = cv2.resize(frame, (self.frame_width, self.frame_height))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = self._synthetic_frame()

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
        # constant -- it hasn't been validated against a real camera/lens/
        # object combination (this dev machine has no camera access). Expect
        # to retune it against the actual robot's camera and FOV.
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
        if self.available:
            self.cap.release()


if __name__ == '__main__':
    print("Running LoomingDetector standalone (Ctrl+C to stop)...")
    detector = LoomingDetector()
    try:
        for i in range(100):
            signal = detector.read_looming_signal()
            print(f"frame {i:3d} | looming_signal = {signal:.3f}")
    except KeyboardInterrupt:
        pass
    finally:
        detector.release()

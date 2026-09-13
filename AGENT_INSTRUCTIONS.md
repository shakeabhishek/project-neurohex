# Agent Instructions for Project NeuroHex

**Context for the AI Agent:**
This project is a robotics class project where we are building a hexapod robot driven by a simulated Spiking Neural Network (SNN) based on actual fruit fly connectome data from Virtual Fly Brain (VFB). 

The user is working in the `agy` CLI to continue this project. 

**Core Technologies to use:**
- `vfb-connect` (Python) for downloading connectome data.
- `brian2` (Python) for running the Spiking Neural Network.
- `opencv-python` for visual input.
- `adafruit-circuitpython-servokit` for controlling the servos via a PCA9685 I2C board.

**Status as of the last session:**

1. **Dependencies:** Installed in `venv/` (`vfb-connect`, `brian2`, `opencv-python`, `adafruit-circuitpython-servokit`, `smbus2`, etc.).
2. **Data Retrieval Script:** `fetch_connectome.py` is done. It pulls the 1-hop synaptic neighborhood of the Giant Fiber (both L/R instances) from the **MaleCNS** whole-brain+nerve-cord dataset (~166,000 neurons total) via `vfb-connect` -- not the whole brain. This yields ~992 neurons. An earlier version used the hemibrain dataset (brain-only), which meant GF's real motor targets (in the VNC) were never reachable and the escape signal never actually fired a motor neuron -- if you see hemibrain IDs or a neuron count near 391 again, that regression has resurfaced.
3. **SNN Skeleton:** `snn_brain.py` (`NeuroHexBrain`) is done: loads the adjacency matrix, builds LIF neurons via `brian2`, and reads out escape magnitude from the `TTMn`/`DN` groups (GF's real, physically-verified motor targets). GF's synapses onto TTMn/DN are deliberately given a strong, near-suprathreshold flat weight rather than the log-compressed population weighting used elsewhere, reflecting the real "giant synapse" physiology (see README references). Verified: `python snn_brain.py` shows escape magnitude ramping up and crossing threshold under a simulated looming stimulus.
4. **I/O Integration:** Done. `vision.py` (`LoomingDetector`, optical-flow divergence -> looming signal) and `motor_control.py` (`HexapodController`, PCA9685 servo control) both auto-detect real hardware and fall back gracefully when it's absent (synthetic stimulus / logged mock commands respectively). `main.py` wires camera -> SNN -> servos into the real control loop.
5. **Deployed and verified on the real Raspberry Pi 5 ("Lumi")**, camera included: `vision.py` correctly picks the `picamera2` backend there (see README's "Raspberry Pi deployment notes" for the venv/system-package gotchas this surfaced -- `--system-site-packages`, `python3-dev`/`swig`/`liblgpio-dev`, and a `from brian2 import *` namespace-shadowing bug in `snn_brain.py` that only showed up on the Pi's numpy build). No PCA9685/servos attached yet, so `motor_control.py` is still running in mock mode there.

**Next real piece of work:** once the PCA9685 + servos + chassis arrive, wire them up per the BOM/channel map in `motor_control.py` and validate `execute_escape()` against actual leg hardware (the joint angles in `NEUTRAL_ANGLES`/`LUNGE_ANGLES` are unvalidated starting points, not measured against the physical Nougat chassis).

**Important Constraints:**
- Keep the simulated circuit scoped to GF's direct neighborhood (~1000 neurons), not the whole connectome, so it runs in real time on a Raspberry Pi (16GB Pi 5 targeted).
- Remind the user they need two power supplies (one for the Pi, one for the 18 servos) -- and for the Pi specifically, a full 5.1V/5A over USB-C PD (see README power warning).
- The Mac dev machine has no I2C hardware and (usually) no camera permission granted to this process -- the I/O layer's mockable/synthetic fallback paths exist for exactly this, so code changes should keep working with no hardware attached before assuming they'll work on the Pi.

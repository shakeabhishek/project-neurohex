# Agent Instructions for Project NeuroHex

**Context for the AI Agent:**
This project is a robotics class project where we are building a hexapod robot driven by a simulated Spiking Neural Network (SNN) based on actual fruit fly connectome data from Virtual Fly Brain (VFB). 

The user is working in the `agy` CLI to continue this project. 

**Core Technologies to use:**
- `vfb-connect` (Python) for downloading connectome data.
- `brian2` (Python) for running the Spiking Neural Network.
- `opencv-python` for visual input.
- `adafruit-circuitpython-servokit` for controlling the servos via a PCA9685 I2C board.

**Your immediate next steps when the user resumes the session:**

1. **Install Dependencies:** Ask the user if they have run `pip install vfb-connect brian2 opencv-python adafruit-circuitpython-servokit smbus2`.
2. **Data Retrieval Script:** Write a python script (e.g., `fetch_connectome.py`) that uses `vfb-connect` to pull an adjacency matrix for a small sensorimotor circuit (like the Giant Fiber system or motion-detecting LPTCs). *Do not pull the whole brain, the Pi will crash.*
3. **SNN Skeleton:** Once the data is downloaded, write a basic `brian2` simulation script (`snn_brain.py`) that loads this matrix, creates a `NeuronGroup`, and sets up basic Leaky Integrate-and-Fire (LIF) equations.
4. **I/O Integration:** Help the user write the translation layer to convert OpenCV camera pixels into input spikes, and read output spikes to drive the `adafruit_servokit` legs.

**Important Constraints:**
- Keep the number of simulated neurons small (< 1000) so it runs in real-time on a Raspberry Pi.
- Remind the user they need two power supplies (one for the Pi, one for the 18 servos).

# Project NeuroHex

Project NeuroHex is a cutting-edge neurorobotics class project that deploys the **actual biological connectome** of a fruit fly (*Drosophila melanogaster*) to drive a physical hexapod robot.

Unlike standard biomimetic robots that use hardcoded behavioral loops (like Braitenberg vehicles), NeuroHex uses a Spiking Neural Network (SNN) simulator (`brian2`) to run the literal synaptic wiring diagram downloaded from [Virtual Fly Brain](https://www.virtualflybrain.org). 

## Architecture

1. **Hardware:** A Raspberry Pi-powered 6-legged robot using 18 micro-servos and a PCA9685 I2C controller.
2. **Connectome Data:** The robot queries the Virtual Fly Brain API (`vfb-connect`) to pull the synaptic adjacency matrix of the Giant Fiber (GF) escape circuit or the Lobula Plate Tangential Cells (LPTC).
3. **The Brain Simulation:** The Raspberry Pi runs a real-time `brian2` Spiking Neural Network simulation of those exact neurons.
4. **I/O Translation:** 
   - *Vision Input:* OpenCV optical flow translates camera pixels into virtual electrical spikes injected into the simulated optic lobe.
   - *Motor Output:* The simulation's motor neuron spike rates are converted into PWM angles to trigger the hexapod's escape gait.

## Setup
*(To be completed once the initial SNN scripts are written)*

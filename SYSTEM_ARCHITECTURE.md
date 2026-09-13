# Project NeuroHex: System Architecture & Schematics

![Hardware Wiring Schematic](system_schematic.jpg)

This document provides detailed schematics of the entire NeuroHex system, breaking down the hardware wiring, the software data flow, and the physical power delivery.

---

## 1. High-Level System Architecture

This diagram shows how the physical hardware interfaces with the biological Spiking Neural Network (SNN).

```mermaid
graph TD
    subgraph Input [Sensory Input]
        Cam[Raspberry Pi Camera V2] --> |Video Frames| OpenCV[OpenCV Optical Flow]
        OpenCV --> |Motion Vectors| SpikeGen[Brian2 Spike Generator]
    end

    subgraph Brain [Simulated Connectome]
        SpikeGen --> |Input Spikes| VisualNeurons[Simulated Visual Neurons]
        VFB[(Virtual Fly Brain API)] -.-> |Wiring Data| Network[Brian2 SNN Graph]
        Network --- VisualNeurons
        VisualNeurons --> |Synapses| Interneurons[Giant Fiber Interneurons]
        Interneurons --> |Synapses| MotorNeurons[Simulated Motor Neurons]
    end

    subgraph Output [Motor Control]
        MotorNeurons --> |Spike Rates| Translator[Python Spike-to-PWM Translator]
        Translator --> |I2C Commands| PCA[PCA9685 PWM Controller]
        PCA --> |PWM Signals| Legs[18x Micro Servos]
    end

    classDef hardware fill:#444,stroke:#333,stroke-width:2px,color:#fff;
    classDef software fill:#0066cc,stroke:#004499,stroke-width:2px,color:#fff;
    classDef bio fill:#009933,stroke:#006622,stroke-width:2px,color:#fff;
    
    class Cam,PCA,Legs hardware;
    class OpenCV,Translator,VFB software;
    class SpikeGen,VisualNeurons,Interneurons,MotorNeurons,Network bio;
```

---

## 2. Hardware & Wiring Schematic

This diagram details the physical pin connections and, crucially, the split power delivery system required to prevent the 18 servos from crashing the Raspberry Pi.

```mermaid
graph TD
    subgraph Power [Power Supplies]
        BatteryPi[5V USB Power Bank]
        BatteryServo[7.4V 2S LiPo Battery]
        Buck[5V High-Current Buck Converter]
        BatteryServo --> |7.4V| Buck
    end

    subgraph Compute [Raspberry Pi 4/5]
        PiPower[USB-C Power In]
        PiI2C[GPIO 2 & 3: SDA/SCL]
        PiCamPort[CSI Camera Port]
    end

    subgraph Peripherals
        Camera[Pi Camera Module]
        PCA9685[PCA9685 16-Ch I2C Driver #1]
        PCA9685_2[PCA9685 16-Ch I2C Driver #2]
        Servos[18x SG90/MG90S Servos]
    end

    %% Power Routing
    BatteryPi ==> |5V| PiPower
    Buck ==> |5V High Current| PCA9685
    Buck ==> |5V High Current| PCA9685_2
    
    %% Data Routing
    Camera --- |Ribbon Cable| PiCamPort
    PiI2C <--> |I2C Data/Clock| PCA9685
    PCA9685 <--> |I2C Daisy Chain| PCA9685_2
    
    %% Servo Routing
    PCA9685 ==> |PWM + 5V Power| Servos
    PCA9685_2 ==> |PWM + 5V Power| Servos

    classDef pwr fill:#d9534f,stroke:#d43f3a,stroke-width:2px,color:#fff;
    classDef data fill:#f0ad4e,stroke:#eea236,stroke-width:2px,color:#fff;
    
    class BatteryPi,BatteryServo,Buck,PiPower pwr;
    class PiI2C,PCA9685,PCA9685_2,Camera,PiCamPort data;
```

---

## 3. Spiking Neural Network (SNN) Data Flow

This outlines the translation layer logic inside the Python scripts.

```mermaid
sequenceDiagram
    participant Cam as Pi Camera
    participant CV as OpenCV
    participant SNN as Brian2 Simulator
    participant PWM as PCA9685 Driver
    participant Leg as Servos

    Cam->>CV: Capture Frame
    Note over CV: Calculate Optical Flow<br/>Detect left/right looming
    CV->>SNN: Inject Spikes (Hz proportional to threat)
    Note over SNN: SNN solves Leaky Integrate-and-Fire ODEs<br/>(10ms steps)
    SNN->>SNN: Action Potentials propagate<br/>through Giant Fiber connectome
    SNN-->>CV: Read output Motor Neuron spike rates
    Note over CV: Inverse Kinematics Gait Math:<br/>Map spike rate to stride length
    CV->>PWM: Send Target Angles (I2C)
    PWM->>Leg: Adjust PWM Duty Cycle
    Leg-->>Cam: Robot moves (New visual state)
```

# Project NeuroHex: Bill of Materials (BOM)

## Off-the-Shelf Hardware (To Buy/Source)

### Compute & Control
* **1x** Raspberry Pi 5 (16GB RAM). The escape circuit itself is small (~1,000 neurons), so the 16GB is mainly headroom for OpenCV and dev tooling rather than a hard requirement of the SNN.
* **1x** Raspberry Pi Camera Module V2 (or similar)
* **2x** PCA9685 16-Channel I2C PWM Servo Drivers (We need 2 because we have 18 servos, and each board only holds 16).
* **18x** 21g Metal Gear Servos (Required for the Nougat chassis. Standard 9g micro-servos like the MG90S will be too small and weak to fit the brackets or lift the heavier frame).

### Power Delivery
* **1x** Portable USB-C PD power bank explicitly rated for **5V⎓5A (25W+) output** (e.g., a Talentcell 12V 7000mAh-class PD pack) - for untethered walking. Most PD power banks cap the 5V rung at 3A and only hit higher wattage at 9V/12V/20V, which the Pi 5 won't accept; check the bank's spec sheet for "5V/5A" explicitly, not just its peak wattage. Use the official Raspberry Pi 5 27W USB-C PD supply (5.1V/5A) for stationary bench testing/development.
* **1x** 2S LiPo Battery (7.4V, ~2000mAh+) - To power the servos.
* **1x** 5V High-Current Buck Converter (e.g., LM2596 or a 10A UBEC) - To step the 7.4V LiPo down to a safe 5V for the PCA9685 boards and servos.

### Fasteners & Wiring
* Assorted M2 and M3 bolts and nuts (for assembling the 3D printed joints and mounting the servos).
* Female-to-Female jumper wires (for I2C connections between Pi and PCA boards).
* Optional: 6x Small rubber caps/feet for the tips of the legs to provide grip on smooth floors.

---

## 3D Printed Parts Required

**Official Chassis Selection:** [Hexapod Nougat by RookiDroid](https://rookidroid.com/build-your-own-nougat/). 
*You can download the `nougat.3mf` files from their GitHub. This is an aggressive, larger chassis that requires beefier 21g servos instead of the standard 9g micro-servos.*

### Body/Chassis
* **1x Main Thorax (Baseplate):** The central hub. Needs mounting standoffs/holes for the Raspberry Pi on top, and mounting rails for the two PCA9685 boards underneath.
* **1x Battery/Abdomen Caddy:** A bracket to hold the USB power bank and the LiPo battery securely to the rear or underside of the Thorax.
* **1x Head Bracket:** An angled mount for the camera module at the front.

### Leg Assemblies (Print 6 sets of the following)
* **6x Coxa (Hip) Brackets:** Mounts the first servo to the main Thorax baseplate.
* **6x Femur (Thigh) Brackets:** A U-shaped bracket that connects the horn of the Coxa servo to the body of the Femur servo.
* **6x Tibia (Knee/Shin) Links:** Connects to the horn of the Femur servo and extends downward to the floor to act as the actual leg/foot.

"""
NeuroHex main control loop.

Wires together the three layers described in README.md's system architecture:
camera -> optical-flow looming signal -> spiking Giant Fiber escape circuit
-> servo commands.
"""

import argparse

from snn_brain import NeuroHexBrain
from vision import LoomingDetector
from motor_control import HexapodController


def main():
    parser = argparse.ArgumentParser(description='NeuroHex main control loop')
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--step-ms', type=float, default=20.0,
                         help='Simulated brain time advanced per camera frame')
    parser.add_argument('--escape-threshold', type=float, default=0.5)
    parser.add_argument('--max-steps', type=int, default=None,
                         help='Stop after N steps (for testing); default runs until Ctrl+C')
    args = parser.parse_args()

    print("Initializing NeuroHex Brain...")
    brain = NeuroHexBrain()
    print("Initializing vision...")
    vision = LoomingDetector(camera_index=args.camera)
    print("Initializing motor controller...")
    motors = HexapodController()

    print("NeuroHex running. Press Ctrl+C to stop.")
    step = 0
    was_escaping = False
    try:
        while args.max_steps is None or step < args.max_steps:
            looming = vision.read_looming_signal()
            output = brain.step(visual_input=looming, mechanosensory_input=0.0, duration_ms=args.step_ms)
            magnitude = output['escape_magnitude']
            is_escaping = magnitude > args.escape_threshold

            if is_escaping:
                # Re-issue every step while escaping: execute_escape() alternates
                # tripods each call to produce the push-off "flee" motion.
                motors.execute_escape(magnitude)
                status = ">>> ESCAPING"
            elif was_escaping:
                # Only re-issue stand() on the transition back to idle, not
                # every idle step -- there's nothing new to command otherwise,
                # and at 20ms/step that's 18 redundant servo writes/prints a
                # second doing nothing but drowning out the actual signal.
                motors.stand()
                status = ""
            else:
                status = ""

            was_escaping = is_escaping
            print(f"step={step:5d} looming={looming:.2f} escape={magnitude:.3f} {status}")
            step += 1
    except KeyboardInterrupt:
        print("\nStopping NeuroHex...")
    finally:
        motors.release()
        vision.release()


if __name__ == '__main__':
    main()

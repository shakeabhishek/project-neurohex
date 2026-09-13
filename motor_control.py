"""
Motor layer for NeuroHex.

Maps the SNN's escape command (a single 0-1 magnitude, from
NeuroHexBrain.get_motor_output()) onto the 18 leg servos via two PCA9685
I2C PWM boards, executing either a neutral standing pose or a tripod escape
lunge scaled by escape strength.

On a machine with no I2C hardware (e.g. this dev machine, or any non-Pi
board Adafruit Blinka doesn't recognize), falls back to a mock ServoKit that
logs the angles it would have sent, so the control loop is still runnable
and testable without the physical robot.
"""

try:
    from adafruit_servokit import ServoKit
    _HARDWARE_AVAILABLE = True
except Exception:
    _HARDWARE_AVAILABLE = False


NUM_LEGS = 6
JOINT_ORDER = ['coxa', 'femur', 'tibia']

# Channel map: legs 0-4 (15 channels) on PCA9685 board 0, leg 5 on board 1.
# The project's earlier hand-drawn wiring diagrams (docs/SYSTEM_ARCHITECTURE.md)
# were illustrative, not an exact channel spec -- this is the explicit mapping
# the code actually uses.
def _channel_for(leg_index, joint_index):
    global_channel = leg_index * len(JOINT_ORDER) + joint_index
    board, channel = divmod(global_channel, 16)
    return board, channel


# Starting-point joint angles (degrees), not yet validated against the
# physical Nougat chassis -- verify servo range/direction and adjust before
# trusting this on real hardware.
NEUTRAL_ANGLES = {'coxa': 90, 'femur': 90, 'tibia': 90}
LUNGE_ANGLES = {'coxa': 90, 'femur': 40, 'tibia': 160}

# Alternating tripod sets for the escape lunge (legs 0-5 front-to-back on one side, then the other).
TRIPOD_A = [0, 2, 4]
TRIPOD_B = [1, 3, 5]


class _MockChannel:
    """Standin for a single ServoKit channel; logs instead of driving I2C."""

    def __init__(self, board_id, channel_index):
        self.board_id = board_id
        self.channel_index = channel_index
        self._angle = None

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self._angle = value
        print(f"[mock servo] board=0x{self.board_id:02x} ch={self.channel_index:2d} -> {value:6.1f} deg")


class _MockServoKit:
    def __init__(self, board_id):
        self.servo = [_MockChannel(board_id, i) for i in range(16)]


class HexapodController:
    def __init__(self, i2c_addresses=(0x40, 0x41)):
        self.boards = []
        for addr in i2c_addresses:
            if _HARDWARE_AVAILABLE:
                try:
                    self.boards.append(ServoKit(channels=16, address=addr))
                    continue
                except Exception as e:
                    print(f"Warning: could not initialize PCA9685 at {hex(addr)}: {e}. Falling back to mock.")
            self.boards.append(_MockServoKit(addr))

        if not _HARDWARE_AVAILABLE:
            print("Warning: adafruit_servokit/Blinka not available (no supported I2C board detected). "
                  "Running in mock mode -- servo commands will be logged, not sent.")

        self._lunge_phase = 0
        self.stand()

    def _set_leg(self, leg_index, angles):
        for joint_index, joint in enumerate(JOINT_ORDER):
            board, channel = _channel_for(leg_index, joint_index)
            self.boards[board].servo[channel].angle = angles[joint]

    def stand(self):
        """Move all legs to the neutral standing pose."""
        for leg in range(NUM_LEGS):
            self._set_leg(leg, NEUTRAL_ANGLES)

    def execute_escape(self, escape_magnitude):
        """
        Executes one tripod-lunge step, scaled by escape_magnitude (0-1).
        Call repeatedly (once per control-loop iteration) while the escape
        command remains active; each call advances to the opposite tripod,
        producing an alternating push-off "flee" motion rather than a single
        static pose.
        """
        if escape_magnitude <= 0:
            return
        blend = min(1.0, escape_magnitude)
        lunge = {
            joint: NEUTRAL_ANGLES[joint] + (LUNGE_ANGLES[joint] - NEUTRAL_ANGLES[joint]) * blend
            for joint in NEUTRAL_ANGLES
        }
        active_tripod = TRIPOD_A if self._lunge_phase % 2 == 0 else TRIPOD_B
        for leg in active_tripod:
            self._set_leg(leg, lunge)
        self._lunge_phase += 1

    def release(self):
        self.stand()


if __name__ == '__main__':
    print("Running HexapodController standalone smoke test...")
    controller = HexapodController()
    print("\n-- standing --")
    controller.stand()
    print("\n-- escape lunge, magnitude=0.3 --")
    controller.execute_escape(0.3)
    print("\n-- escape lunge, magnitude=0.9 --")
    controller.execute_escape(0.9)
    print("\n-- back to standing --")
    controller.stand()

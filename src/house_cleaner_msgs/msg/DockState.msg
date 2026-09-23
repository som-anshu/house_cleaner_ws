# DockState.msg
#
# State published BY the dock hardware: is the robot seated, is charging
# active, and what current is being drawn.  Published on /dock/state.
# The simulator (battery_sim) and the real dock controller (battery_hw)
# both publish this, so the mission supervisor has one contract.

uint8 STATE_IDLE = 0
uint8 STATE_CHARGING = 1
uint8 STATE_FAULT = 2

bool seated              # robot physically at the dock (laser/limit verified)
bool charging            # power is flowing into the battery
uint8 state              # one of STATE_* above
float32 current          # A currently drawn by the charger
float32 voltage          # V at the dock terminals
uint64 stamp_seq         # increments on every state change
# DockCommand.msg
#
# Command sent TO the dock hardware: start charging, stop charging, or
# report a fault.  Published by the mission supervisor on /dock/command.
# The same message is consumed by the simulator (battery_sim) and the
# real dock controller (battery_hw), so the supervisor never needs two
# interfaces.

uint8 CMD_START = 0
uint8 CMD_STOP = 1
uint8 CMD_FAULT = 2

uint8 command
float32 current_limit   # A; 0.0 = no limit (sim ignores it)
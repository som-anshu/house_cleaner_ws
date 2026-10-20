.PHONY: help setup build launch start stop verify check logs monitor clean

WS_PATH := $(shell pwd)
# Distro comes from the same detection every other script uses.
ROS_DISTRO ?= $(shell . "$(WS_PATH)/ros-distro.sh" >/dev/null 2>&1; echo "$$ROS_DISTRO")

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install all dependencies
	sudo apt-get update
	sudo apt-get install -y \
		ros-$(ROS_DISTRO)-turtlebot3-gazebo \
		ros-$(ROS_DISTRO)-slam-toolbox \
		ros-$(ROS_DISTRO)-nav2-bringup \
		ros-$(ROS_DISTRO)-foxglove-bridge

build: ## Build the workspace
	cd $(WS_PATH) && colcon build --symlink-install

launch: ## Kill stale instances, launch the full GUI stack, verify
	./run_all.sh

start: launch ## Alias for launch

stop: ## Kill stale instances (container, watchdog, battery monitor)
	./run_all.sh --stop

verify: ## Health-check the running stack
	./run_all.sh --verify

check: ## Check system health
	@echo "=== Process Check ==="
	@for p in gazebo slam_toolbox mission_supervisor; do \
		pgrep -f $$p > /dev/null && echo "  [OK] $$p" || echo "  [DEAD] $$p"; \
	done
	@echo "=== Topic Check ==="
	@source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(WS_PATH)/install/setup.bash && \
		for t in /scan /odom /map /cmd_vel /battery_state; do \
			count=$$(ros2 topic info $$t 2>/dev/null | grep "Publisher count" | awk '{print $$3}'); \
			if [ "$$count" != "0" ] && [ -n "$$count" ]; then \
				echo "  [OK] $$t ($$count publishers)"; \
			else \
				echo "  [SILENT] $$t"; \
			fi; \
		done
	@echo "=== Nav2 Lifecycle ==="
	@source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(WS_PATH)/install/setup.bash && \
		for n in bt_navigator controller_server planner_server behavior_server; do \
			state=$$(ros2 lifecycle get /$$n 2>/dev/null); \
			echo "  $$n: $$state"; \
		done

logs: ## Show recent mission supervisor logs
	@source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(WS_PATH)/install/setup.bash && \
		timeout 3s ros2 topic echo /rosout --once 2>/dev/null | grep -i mission | tail -20

monitor: ## Monitor robot motion
	@source /opt/ros/$(ROS_DISTRO)/setup.bash && source $(WS_PATH)/install/setup.bash && \
	echo "Monitoring robot position (Ctrl+C to stop)..." && \
	while true; do \
		pos=$$(timeout 2s ros2 topic echo /odom --once 2>/dev/null | grep -A3 "position:" | grep "x:\|y:" | tr '\n' ' '); \
		echo "[$$(date +%T)] $$pos"; \
		sleep 5; \
	done

clean: ## Clean build artifacts
	rm -rf $(WS_PATH)/build $(WS_PATH)/install $(WS_PATH)/log
	@echo "Cleaned build/, install/, log/"

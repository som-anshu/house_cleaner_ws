cmake_minimum_required(VERSION 3.8)
project(house_cleaner_bringup)

find_package(ament_cmake REQUIRED)

# Install launch and config directories
install(DIRECTORY launch config worlds models
  DESTINATION share/${PROJECT_NAME}/
)

# Install package.xml
install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}/
)

# Install resource index marker
install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages/
)

# Install the runner script
install(PROGRAMS ${CMAKE_CURRENT_SOURCE_DIR}/run_fake_sim.py
  DESTINATION lib/${PROJECT_NAME}/run_fake_sim
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install fake_sim.py as an executable directly
install(PROGRAMS ${CMAKE_CURRENT_SOURCE_DIR}/house_cleaner_bringup/fake_sim.py
  DESTINATION lib/${PROJECT_NAME}/fake_sim
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install house_cleaner_assistant.py as the launchable executable
# (flat name under lib/<pkg>/, so `ros2 launch` Node(executable=...) resolves it)
install(PROGRAMS ${CMAKE_CURRENT_SOURCE_DIR}/house_cleaner_bringup/house_cleaner_assistant.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME house_cleaner_assistant
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install the __init__.py to make it a proper package
install(FILES house_cleaner_bringup/__init__.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
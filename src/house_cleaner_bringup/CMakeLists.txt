cmake_minimum_required(VERSION 3.8)
project(house_cleaner_bringup)

find_package(ament_cmake REQUIRED)
find_package(rclpy REQUIRED)

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

# Install fake_sim.py as an executable
install(PROGRAMS ${CMAKE_CURRENT_SOURCE_DIR}/house_cleaner_bringup/fake_sim.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME fake_sim
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install house_cleaner_assistant.py as the launchable executable
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
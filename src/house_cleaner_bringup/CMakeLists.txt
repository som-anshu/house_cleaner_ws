cmake_minimum_required(VERSION 3.8)
project(house_cleaner_bringup)

find_package(ament_cmake REQUIRED)

# Install launch, config, worlds, and models directories
install(DIRECTORY launch config worlds models
  DESTINATION share/${PROJECT_NAME}/
)

# Install package.xml
install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}/
)

# Install resource index marker for ament
install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages/
)

# Install Python modules (executable scripts)
# Install at lib/<package>/<executable> for proper ROS2 discovery
# The setup.py entry_points will also create these, but CMake install
# ensures they're available even if setup.py is not run
install(PROGRAMS
  ${CMAKE_CURRENT_SOURCE_DIR}/house_cleaner_bringup/house_cleaner_assistant.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME house_cleaner_assistant
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)
install(PROGRAMS
  ${CMAKE_CURRENT_SOURCE_DIR}/house_cleaner_bringup/fake_sim.py
  DESTINATION lib/${PROJECT_NAME}
  RENAME fake_sim
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Install Python package init
install(FILES house_cleaner_bringup/__init__.py
  DESTINATION lib/${PROJECT_NAME}/
)

ament_package()
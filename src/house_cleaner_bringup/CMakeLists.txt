cmake_minimum_required(VERSION 3.8)
project(house_cleaner_bringup)

find_package(ament_cmake REQUIRED)

# Launch files, config, worlds, models, scripts — no compiled code.
install(DIRECTORY launch config worlds models
  DESTINATION share/${PROJECT_NAME}/
)

install(PROGRAMS
  scripts/battery_monitor.py
  scripts/kill_house_cleaner.sh
  DESTINATION lib/${PROJECT_NAME}
)

install(FILES package.xml
  DESTINATION share/${PROJECT_NAME}/
)

# Resource index marker for ament discovery
install(FILES resource/${PROJECT_NAME}
  DESTINATION share/ament_index/resource_index/packages/
)

ament_package()
from setuptools import find_packages, setup

setup(
    name="house_cleaner_mission",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/house_cleaner_mission"]),
        ("share/house_cleaner_mission", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="koko",
    maintainer_email="koko@example.com",
    description="Mission supervisor for house cleaner robot (hardware-agnostic)",
    license="MIT",
    entry_points={
        "console_scripts": [
            "mission_supervisor = house_cleaner_mission.mission_supervisor:main",
        ],
    },
)
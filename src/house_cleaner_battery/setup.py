from setuptools import find_packages, setup

setup(
    name="house_cleaner_battery",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/house_cleaner_battery"]),
        ("share/house_cleaner_battery", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="koko",
    maintainer_email="koko@example.com",
    description="Battery + dock backend for house cleaner robot (sim and real)",
    license="MIT",
    entry_points={
        "console_scripts": [
            "battery_sim = house_cleaner_battery.battery_sim:main",
            "battery_hw = house_cleaner_battery.battery_hw:main",
        ],
    },
)
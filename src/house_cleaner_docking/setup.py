from setuptools import find_packages, setup

setup(
    name="house_cleaner_docking",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/house_cleaner_docking"]),
        ("share/house_cleaner_docking", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="koko",
    maintainer_email="koko@example.com",
    description="Laser-guided docking controller for house cleaner robot",
    license="MIT",
    entry_points={
        "console_scripts": [
            "docking_controller = house_cleaner_docking.docking_controller:main",
        ],
    },
)
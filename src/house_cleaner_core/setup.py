from setuptools import find_packages, setup

setup(
    name="house_cleaner_core",
    version="0.1.0",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/house_cleaner_core"]),
        ("share/house_cleaner_core", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="koko",
    maintainer_email="koko@example.com",
    description="Pure-Python geometry + coverage planning for house cleaner",
    license="MIT",
)
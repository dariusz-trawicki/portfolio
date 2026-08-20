from setuptools import setup,find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="MLOPS-IRIS",
    version="0.1",
    author="",
    packages=find_packages(),
    install_requires = requirements,
)
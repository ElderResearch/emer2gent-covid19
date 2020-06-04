from setuptools import setup, find_packages

setup(
    name="trent",
    version="0.0.1",
    author="Elder Research, Inc.",
    description="COVID-19 source code.",
    url="https://github.com/ElderResearch/emer2gent-covid19",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)

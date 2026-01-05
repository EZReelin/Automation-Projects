"""
Setup script for Dart Performance Coach
"""

from pathlib import Path
from setuptools import setup, find_packages

# Read requirements
requirements = []
req_file = Path(__file__).parent / "requirements.txt"
if req_file.exists():
    with open(req_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                requirements.append(line)

# Read README
readme_file = Path(__file__).parent.parent / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file) as f:
        long_description = f.read()

setup(
    name="dart-coach",
    version="1.0.0",
    author="Dart Performance Coach",
    description="Comprehensive dart performance tracking and coaching system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'dart_coach': [
            'config/*.yaml',
            'config/*.example',
            'schemas/*.json',
        ]
    },
    install_requires=requirements,
    python_requires=">=3.9",
    entry_points={
        'console_scripts': [
            'dart-coach=dart_coach.main:main',
            'dart-coach-scheduler=dart_coach.scheduler:start_scheduler',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Games/Entertainment",
    ],
)

"""
This file is used to configure your package for distribution.
It tells python how to install your package, what dependencies it has, and what scripts to run.

"""

from setuptools import find_packages, setup

setup(
    name="ocp-diag-autoval",
    version="0.1.0",
    Packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "lxml",  # adding other dependencies
    ],
    entry_points={
        "console_scripts": [
            "autoval-test=autoval_test_runner:main",  # adding the main entry point,
        ],
    },
    description="OCP Diag Autoval - Core framework for Autoval Tests",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/opencomputeproject/ocp-diag-autoval",
    python_requires=">=3.10",
)

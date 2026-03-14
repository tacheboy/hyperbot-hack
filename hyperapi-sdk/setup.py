"""
HyperAPI Python SDK Setup
"""

from setuptools import setup, find_packages

setup(
    name="hyperapi",
    version="0.1.0",
    description="HyperAPI Python SDK for financial document processing",
    author="HyperAPI Team",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.27.0",
    ],
    python_requires=">=3.8",
)

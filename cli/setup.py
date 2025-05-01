from setuptools import setup, find_packages

setup(
    name="buildandburn",
    version="0.1.0",
    description="A tool for creating and managing build-and-burn environments",
    author="Platform Engineering Team",
    packages=find_packages(),
    include_package_data=True,
    py_modules=["buildandburn", "deploy_env", "builder"],
    entry_points={
        "console_scripts": [
            "buildandburn=buildandburn:main",
            "build-and-burn=buildandburn:main",
            "bb-deploy=deploy_env:main",
        ],
    },
    install_requires=[
        "pyyaml>=6.0",
        "boto3>=1.28.0",
        "botocore>=1.31.0",
        "python-dotenv>=1.0.0",
        "click>=8.1.0",
        "requests>=2.31.0",
        "kubernetes>=28.1.0",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
) 
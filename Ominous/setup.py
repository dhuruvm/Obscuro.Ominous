from setuptools import find_packages, setup

setup(
    name="obscuro-ominous",
    version="2.0.0",
    description="Obscuro Ominous - Autonomous AI Data Pipeline & Training System",
    packages=find_packages(),
    py_modules=["cli", "reader", "generate_dummy"],
    install_requires=[
        "rich>=13.0.0",
        "requests>=2.31.0",
        "httpx>=0.27.0",
        "beautifulsoup4>=4.12.0",
        "tiktoken>=0.7.0",
        "numpy>=1.24.0",
    ],
    entry_points={
        "console_scripts": [
            "obscuro=cli:main",
            "obscuro-ominous=cli:main",
            "datacollector=cli:main",
        ],
    },
    python_requires=">=3.8",
)

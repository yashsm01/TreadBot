from setuptools import setup, find_packages

setup(
    name="crypto-straddle-strategy",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn>=0.24.0",
        "sqlalchemy>=2.0.23",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "python-telegram-bot>=20.0",
        "psycopg2-binary>=2.9.9",  # PostgreSQL adapter
        "pandas>=2.0.0",  # For data analysis
        "numpy>=1.24.0",  # Required by pandas
        "python-binance>=1.0.19",  # Binance API client
        "apscheduler>=3.10.0",  # For scheduling tasks
    ],
    python_requires=">=3.8",
)

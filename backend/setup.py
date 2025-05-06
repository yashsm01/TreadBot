from setuptools import setup, find_packages

setup(
    name="crypto-straddle-strategy",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.1",  # Web framework
        "uvicorn>=0.24.0",  # ASGI server
        "sqlalchemy>=2.0.23",  # ORM
        "python-dotenv>=1.0.0",  # Environment variables
        "pydantic>=2.0.0",  # Data validation
        "python-telegram-bot>=20.0",  # Telegram bot API
        "psycopg2-binary>=2.9.9",  # PostgreSQL adapter
        "pandas>=2.0.0",  # For data analysis
        "numpy>=1.24.0",  # Required by pandas
        "python-binance>=1.0.19",  # Binance API client
        "apscheduler>=3.10.0",  # For scheduling tasks
        "celery>=5.3.0",  # For background tasks
        "redis>=4.5.0",  # For Redis
        "flower>=2.0.0"  # For monitoring Celery tasks
    ],
    python_requires=">=3.8",
)

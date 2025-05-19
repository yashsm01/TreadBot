@echo off
alembic revision --autogenerate -m "add_missing_tables"
alembic upgrade head
pause

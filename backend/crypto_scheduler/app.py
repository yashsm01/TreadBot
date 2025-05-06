from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv

load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_DB_BROKER = os.getenv('REDIS_DB_BROKER', '0')
REDIS_DB_BACKEND = os.getenv('REDIS_DB_BACKEND', '1')

# Create Celery app
app = Celery('crypto_trading')

# Configure using Redis
app.conf.broker_url = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_BROKER}'
app.conf.result_backend = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB_BACKEND}'

# Configure Celery
app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # Worker settings
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    broker_connection_retry_on_startup=True,

    # Beat schedule
    beat_schedule={
        'market-check-every-minute': {
            'task': 'crypto_scheduler.scheduler.tasks.market_check',
            'schedule': 60.0,  # Run every 60 seconds
        },
        'portfolio-update-hourly': {
            'task': 'crypto_scheduler.scheduler.tasks.portfolio_update',
            'schedule': crontab(minute=0),  # Run at the start of every hour
        },
        'daily-strategy-update': {
            'task': 'crypto_scheduler.scheduler.tasks.strategy_update',
            'schedule': crontab(hour=11, minute=0),  # Run at 11:00 AM every day
        },
    }
)

# Auto-discover tasks
app.autodiscover_tasks(['crypto_scheduler.scheduler'])

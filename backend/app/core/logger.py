import logging
from .config import settings

def setup_logger():
    """Configure and setup application logging"""
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT
    )

    # Create logger instance
    logger = logging.getLogger(settings.APP_NAME)

    # Add handlers if needed (file handler, etc.)
    if settings.DEBUG:
        # Add more detailed logging for debug mode
        logger.setLevel(logging.DEBUG)

        # Create console handler with a higher log level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )

        # Add formatter to console handler
        console_handler.setFormatter(formatter)

        # Add console handler to logger
        logger.addHandler(console_handler)

    return logger

# Create and export logger instance
logger = setup_logger()

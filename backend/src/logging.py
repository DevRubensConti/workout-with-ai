import logging
import sys

from loguru import logger

from src.config import get_settings

settings = get_settings()


class InterceptHandler(logging.Handler):
    """Redireciona logs da biblioteca standard 'logging' para a Loguru."""

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # DEV: colorido e detalhado. Demais ambientes: JSON (uma linha por log).
    is_dev = settings.ENVIRONMENT == "development"

    log_format = (
        (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )
        if is_dev
        else "{message}"
    )

    logger.configure(
        handlers=[
            {
                "sink": sys.stdout,
                "format": log_format,
                "serialize": not is_dev,
            }
        ]
    )

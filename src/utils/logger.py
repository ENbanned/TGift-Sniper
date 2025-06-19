import sys
from pathlib import Path
from loguru import logger

from src.core.constants import FileConstants


def setup_logger(debug: bool = False) -> None:
    logger.remove()
    
    level = "DEBUG" if debug else "INFO"
    
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        level=level,
        colorize=True
    )
    
    logs_dir = Path(FileConstants.LOGS_DIR)
    logs_dir.mkdir(exist_ok=True)
    
    logger.add(
        logs_dir / FileConstants.LOG_FILE_PATTERN,
        rotation="1 day",
        retention=f"{FileConstants.LOG_RETENTION_DAYS} days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
               "{name}:{function}:{line} - {message}"
    )


__all__ = [
    "logger", 
    "setup_logger"
]

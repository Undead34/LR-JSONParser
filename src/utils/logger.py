import logging
from logging.handlers import RotatingFileHandler
import os
from os import path

import humanfriendly
from rich.console import Console
from rich.logging import RichHandler

def configure_logger(debug: bool, verbose: bool) -> logging.Logger:
    # Configurar el logger
    logger = logging.getLogger("applogger")
    logger.setLevel(logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING)
    
    # Crear un console handler con rich
    console = Console()
    handler = RichHandler(console=console, show_time=True, show_level=True, show_path=False)
    
    # Usar RichHandler como el handler del logger
    logger.addHandler(handler)
    
    return logger

def get_logger():
    return logging.getLogger("applogger")


def setup_source_logger(logger_name: str, log_directory: str, 
                        max_num_files: int, max_file_size: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)

    os.makedirs(log_directory, exist_ok=True)

    log_file = path.join(log_directory, "source.log")

    max_file_size_bytes = humanfriendly.parse_size(max_file_size)

    file_handler = RotatingFileHandler(log_file, maxBytes=max_file_size_bytes, backupCount=max_num_files, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter("%(message)s")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger

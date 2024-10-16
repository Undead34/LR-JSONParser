from colorama import Fore, Style
import humanfriendly
import logging
from logging.handlers import RotatingFileHandler
import os
from os import path

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app import Config

def configure_logger(debug: bool, verbose: bool) -> logging.Logger:
    logger = logging.getLogger("applogger")
    logger.setLevel(logging.DEBUG if debug else logging.INFO if verbose else logging.WARNING)
    
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    return logger

def get_logger():
    return logging.getLogger("applogger")

def print_status(config: 'Config'):
    for _, entity_config in config.entities.items():
        # Imprime el nombre de la entidad en verde
        print(f"{Fore.GREEN}{Style.BRIGHT}Entity: {entity_config.name}{Style.RESET_ALL}")
        
        for tech_name, tech_config in entity_config.technologies.items():
            # Imprime el nombre de la tecnología en azul
            print(f"  {Fore.CYAN}Technology: {tech_name}{Style.RESET_ALL}")
            print(f"      {Fore.WHITE}Authentication: {tech_config.authentication}{Style.RESET_ALL}")
            
            for source_name, source_config in tech_config.sources.items():
                # Imprime el nombre de la fuente en amarillo
                print(f"    {Fore.YELLOW}Source: {source_name}{Style.RESET_ALL}")
                
                # Si quieres imprimir detalles adicionales de cada fuente:
                print(f"      {Fore.WHITE}Enabled: {source_config.enabled}{Style.RESET_ALL}")
                print(f"      {Fore.WHITE}Endpoint: {source_config.endpoint}{Style.RESET_ALL}")


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

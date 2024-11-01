#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

if sys.version_info < (3, 10):
    print("LogRhythm Report Tool requires Python 3.10 or higher.")
    sys.exit(1)

from colorama import init

from cli import parse_arguments
from utils.logger import configure_logger, logging
from app import run_main_program
from app.config import load_config

def main():
    # sys.argv += ["-d", "--config-file", ".\config.toml"]

    args = parse_arguments()
    logger = configure_logger(args.debug, args.verbose)
    init(autoreset=True)

    config = load_config(args.config_file)

    # Ejecución del flujo principal
    try:
        logger.info("Ejecutando el flujo principal del programa...")
        # prepare enviroment
        run_main_program(args, config)
    except Exception as e:
        logger.error("Error en el flujo principal del programa: %s", e)
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("Interrupción del usuario.")
        sys.exit(0)
    except Exception as e:
        logging.critical("Error inesperado: %s", e)
        sys.exit(1)

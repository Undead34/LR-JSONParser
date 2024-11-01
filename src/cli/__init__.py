import argparse, sys

import argparse
import sys

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="LR-JSONParser",
        description="Escribe logs en formato JSON de diferentes tipos de API, para ser leídos por Filebeat.",
        epilog="Desarrollado por el equipo de Ciberseguridad NetReady Solutions.",
    )
    parser.add_argument("--config-file", type=str, help="ruta al archivo de configuración")
    parser.add_argument("-d", "--debug", action="store_true", help="activar modo debug")
    parser.add_argument("-v", "--verbose", action="store_true", help="activar modo verbose")
    parser.add_argument("-V", "--version", action="version", version="LR-JSONParser 1.0.0")

    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()
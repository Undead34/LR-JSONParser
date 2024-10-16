import argparse, sys

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Escribe losg en formato JSON de diferentes tipos de API, para ser leídos por Filebeat.")
    parser.add_argument('-i', '--interactive', action='store_true', help='modo interactivo')
    parser.add_argument('--config-file', type=str, help='ruta al archivo de configuración')
    parser.add_argument('-d', '--debug', action='store_true', help='activar modo debug')
    parser.add_argument('-v', '--verbose', action='store_true', help='activar salida detallada')
    parser.add_argument('-e', '--export', action='store_true', help='activar salida csv')
    
    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit(0)

    return parser.parse_args()

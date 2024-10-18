import os
import time
from os import path
import schedule

from utils.logger import get_logger, print_status
from utils import topological_sort
from utils.app import process_entities, identify_isolated_technologies, schedule_isolated_technologies, schedule_dependencies
from .config import Config


def run_interactive_mode(args) -> Config:
    logger = get_logger()
    return config


def run_main_program(args, config: Config) -> None:
    logger = get_logger()
    logger.info("Configuración cargada")

    base_path = path.realpath(path.dirname(args.config_file))
    entities_path = path.join(base_path, "entities")
    logger.info("Directorio base: %s", base_path)
    os.makedirs(entities_path, exist_ok=True)

    print_status(config)

    # Procesar entidades y construir el grafo de dependencias
    dependency_graph, source_config_map = process_entities(config, entities_path, logger)

    # Identificar tecnologías aisladas
    isolated_technologies = identify_isolated_technologies(dependency_graph)

    # Crear un grafo sin las tecnologías aisladas
    dependency_graph_without_isolated = {
        tech: dependencies for tech, dependencies in dependency_graph.items()
        if tech not in isolated_technologies
    }

    # Programar tecnologías aisladas
    schedule_isolated_technologies(isolated_technologies, source_config_map, entities_path)

    # Ordenar las fuentes restantes topológicamente
    try:
        sorted_sources = topological_sort(dependency_graph_without_isolated)
        
        modified_sources = []
        
        for source_name in sorted_sources:
            tech_config, source_config = source_config_map[source_name]
            modified_sources.append((tech_config, source_config, source_name))
        
        schedule_dependencies(modified_sources, entities_path)
    except Exception as e:
        logger.exception("Error en el ordenamiento topológico", exc_info=e)

    # Ejecutar el scheduler en un bucle infinito
    while True:
        schedule.run_pending()
        time.sleep(1)

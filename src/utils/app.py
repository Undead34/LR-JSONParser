from datetime import datetime
from collections import defaultdict
import schedule
import arrow
import os
from os import path

from utils import cleanup_logs_for_sources
from utils.logger import get_logger, setup_source_logger
from app.apis import process_source
from . import querystring_parse

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.config import Config

def schedule_source(entity_name: str, tech_name: str, source_name: str, tech_config, source_config, entities_path: str):
    logger = get_logger()
    source_path = path.join(entities_path, entity_name, tech_name, source_name)
    os.makedirs(source_path, exist_ok=True)
    logger_name = f"{entity_name}.{tech_name}.{source_name}"

    querystring_parse(source_config)

    source_logger = setup_source_logger(
        logger_name, source_path,
        max_num_files=tech_config.max_num_files,
        max_file_size=tech_config.max_file_size
    )

    schedule.every(source_config.interval).seconds.do(
        process_source, tech_config, source_config, source_logger
    )
    logger.info(f"Fuente programada: {source_name}")

def process_entities(config: 'Config', entities_path: str, logger):
    """Procesa las entidades y tecnologías y construye el grafo de dependencias."""
    dependency_graph = defaultdict(list)
    source_config_map = {}

    for entity_name, entity_config in config.entities.items():
        logger.info("Procesando entidad: %s", entity_config.name)
        entity_path = path.join(entities_path, entity_name)
        os.makedirs(entity_path, exist_ok=True)

        for tech_name, tech_config in entity_config.technologies.items():
            if not tech_config.enabled:
                logger.info("Tecnología deshabilitada: %s", tech_config.source_name)
                continue

            logger.info("Procesando tecnología: %s", tech_config.source_name)
            tech_path = path.join(entity_path, tech_name)
            os.makedirs(tech_path, exist_ok=True)

            # Comprobar si el token va a expirar
            if tech_config.expiration_date_token != datetime.max:
                expiration_date_token = arrow.get(tech_config.expiration_date_token).to('local')
                days_remaining = (expiration_date_token - arrow.now()).days

                if days_remaining <= 7:
                    logger.warning(
                        f"El token de la tecnología {tech_name} "
                        f"va a vencer en {expiration_date_token.humanize()}!"
                    )
                else:
                    logger.info(f"El token expira {expiration_date_token.humanize()}.")

            # Limpiar logs para los log_sources_ids
            cleanup_logs_for_sources(tech_config.log_sources_ids, logger)

            # Procesar las fuentes
            for source_name, source_config in tech_config.sources.items():
                if source_config.enabled:
                    unique_source_key = f"{entity_name}.{tech_name}.{source_name}"
                    source_config_map[unique_source_key] = (tech_config, source_config)

                    if unique_source_key not in dependency_graph:
                        dependency_graph[unique_source_key] = []

                    if source_config.dependencies:
                        for dependency_name in source_config.dependencies:
                            unique_dependency_key = f"{entity_name}.{tech_name}.{dependency_name}"
                            if unique_dependency_key not in dependency_graph:
                                dependency_graph[unique_dependency_key] = []
                            dependency_graph[unique_dependency_key].append(unique_source_key)

    return dependency_graph, source_config_map


def identify_isolated_technologies(dependency_graph):
    """Identifica las tecnologías aisladas en el grafo."""
    depended_upon = set()
    for dependencies in dependency_graph.values():
        for dep in dependencies:
            depended_upon.add(dep)

    depends_on_others = set(tech for tech, dependencies in dependency_graph.items() if dependencies)

    all_techs = set(dependency_graph.keys())

    # Tecnologías aisladas: No dependen de otras y nadie depende de ellas
    isolated_technologies = all_techs - depended_upon - depends_on_others
    return isolated_technologies


def schedule_isolated_technologies(isolated_technologies, source_config_map, entities_path):
    """Programa las tecnologías aisladas."""
    for tech in isolated_technologies:
        entity_name, tech_name, source_name = tech.split(".")
        tech_config, source_config = source_config_map[tech]
        schedule_source(entity_name, tech_name, source_name, tech_config, source_config, entities_path)

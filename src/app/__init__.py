import os
import time
from os import path
from datetime import datetime
from collections import defaultdict

import arrow
import schedule

from utils.logger import get_logger, print_status, setup_source_logger
from utils import cleanup_logs_for_sources, querystring_parse, topological_sort
from .config import Config
from .apis import process_source


def run_interactive_mode(args) -> Config:
    logger = get_logger()
    return config


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


def run_main_program(args, config: Config) -> None:
    logger = get_logger()
    logger.info("Configuración cargada")

    base_path = path.realpath(path.dirname(args.config_file))
    entities_path = path.join(base_path, "entities")
    logger.info("Directorio base: %s", base_path)
    os.makedirs(entities_path, exist_ok=True)

    print_status(config)

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

            for source_name, source_config in tech_config.sources.items():
                if source_config.enabled:
                    unique_source_key = f"{entity_name}.{tech_name}.{source_name}"
                    source_config_map[unique_source_key] = (tech_config, source_config)

                    if source_config.dependents:
                        for dependent_name in source_config.dependents:
                            unique_dependent_key = f"{entity_name}.{tech_name}.{dependent_name}"
                            dependency_graph[unique_dependent_key].append(unique_source_key)
                    else:
                        schedule_source(entity_name, tech_name, source_name, tech_config, source_config, entities_path)

    try:
        sorted_sources = topological_sort(dependency_graph)

        for unique_source_key in sorted_sources:
            if unique_source_key in source_config_map:
                tech_config, source_config = source_config_map[unique_source_key]
                entity_name, tech_name, source_name = unique_source_key.split('.')
                schedule_source(entity_name, tech_name, source_name, tech_config, source_config, entities_path)

    except Exception as e:
        logger.exception("Error en el ordenamiento topológico", exc_info=e)

    while True:
        schedule.run_pending()
        time.sleep(1)

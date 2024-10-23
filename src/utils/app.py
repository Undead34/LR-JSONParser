from datetime import datetime
from collections import defaultdict
import schedule
import arrow
import os
from os import path
from copy import deepcopy
import rich

from utils import cleanup_logs_for_sources
from utils.logger import get_logger, setup_source_logger
from app.apis import process_source
from . import querystring_parse

from typing import TYPE_CHECKING
from typing import List, Tuple, Set
if TYPE_CHECKING:
    from app.config import Config, IsolatedSources, DependentSources

def process_entities(config: 'Config', logger):
    source_graph = defaultdict(list)

    for entity_name, entity_config in config.entities.items():
        for tech_name, tech_config in entity_config.technologies.items():
            if not tech_config.enabled:
                logger.info("Tecnología deshabilitada: %s", tech_config.source_name)
                continue

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

            cleanup_logs_for_sources(tech_config.log_sources_ids, logger)

            for source_name, source_config in tech_config.sources.items():
                if not source_config.enabled:
                    logger.info("Fuente deshabilitada: %s", source_name)
                    continue

                if source_graph[f"{entity_name}.{tech_name}"] == []:
                    source_graph[f"{entity_name}.{tech_name}"].append((entity_config, tech_config, (entity_name, tech_name)))
                    source_graph[f"{entity_name}.{tech_name}"].append((source_config, source_name))
                else:
                    source_graph[f"{entity_name}.{tech_name}"].append((source_config, source_name))

                

    return source_graph

def schedule_isolated(isolated_sources: 'IsolatedSources', entities_path: str, names: Tuple[str, str]):
    entity_config, tech_config = isolated_sources.entity_config, isolated_sources.technology_config

    for source_config, source_name in isolated_sources.sources:
        logger = get_logger()
        entity_name, tech_name = names
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

def extract_values_from_path(data, keys):
    """
    Recorre las claves especificadas en `keys` para extraer los valores de `data`.
    Si encuentra una lista en el camino, la recorre y continúa el proceso.
    """
    # Inicializamos una lista que almacenará los valores finales
    extracted_values = []
    
    def recursive_extract(current_data, current_keys):
        # Si no quedan claves, almacenamos el valor actual
        if not current_keys:
            extracted_values.append(current_data)
            return
        
        # Tomamos la siguiente clave a procesar
        current_key = current_keys[0]
        
        # Si el valor actual es un diccionario, navegamos por la clave
        if isinstance(current_data, dict) and current_key in current_data:
            next_data = current_data[current_key]
            recursive_extract(next_data, current_keys[1:])
        
        # Si es una lista, iteramos sobre cada elemento y continuamos la recursión
        elif isinstance(current_data, list):
            for item in current_data:
                recursive_extract(item, current_keys)
    
    # Iniciamos la extracción recursiva
    recursive_extract(data, keys)
    
    return extracted_values

def schedule_dependencies(dependencies_sources: 'DependentSources', entities_path: str, names: Tuple[str, str]):
    logger = get_logger()

    entity_name, tech_name = names

    source_logger_path = path.join(entities_path, entity_name, tech_name)
    processed_results_dict = {}

    for source_config, source_name in dependencies_sources.sources:
        os.makedirs(source_logger_path, exist_ok=True)
        source_logger = setup_source_logger(
            f"{entity_name}.{tech_name}.{source_name}", path.join(source_logger_path, source_name),
            max_num_files=dependencies_sources.technology_config.max_num_files,
            max_file_size=dependencies_sources.technology_config.max_file_size
        )

        if source_config.dependencies and source_config.extract_from:
            for dependency_name in source_config.dependencies:
                if dependency_name not in processed_results_dict:
                    raise ValueError(f"No se encontraron resultados para la dependencia '{dependency_name}'")

            to_process = []

            for param, path_str in source_config.extract_from.items():
                path_keys = path_str.split(".")
                first_key = path_keys[0]

                if first_key not in processed_results_dict:
                    raise ValueError(f"No se encontraron resultados para la clave '{first_key}' en el diccionario global")

                processed_data = processed_results_dict[first_key]

                if not isinstance(processed_data, list):
                    extracted_values = extract_values_from_path(processed_data, path_keys[1:])

                    for extracted_value in extracted_values:
                        source_config_copy = deepcopy(source_config)
                        source_config_copy.endpoint = source_config_copy.endpoint.replace(f"{{{param}}}", str(extracted_value))
                        to_process.append((source_config_copy, str(extracted_value)))
                else:
                    for processed_data_item in processed_data:
                        if "extracted_value" not in processed_data_item or "result" not in processed_data_item:
                            raise ValueError(f"El diccionario de resultados no tiene el formato esperado")
                        
                        extracted_value = processed_data_item["extracted_value"]
                        result = processed_data_item["result"]

                        extracted_values = extract_values_from_path(result, path_keys[1:])

                        for extracted_value in extracted_values:
                            for i in range(len(to_process)):
                                if to_process[i][0].name == source_config.name:
                                    source_config_copy = deepcopy(to_process[i][0])
                                    source_config_copy.endpoint = source_config_copy.endpoint.replace(f"{{{param}}}", str(extracted_value))
                                    to_process[i] = (source_config_copy, str(extracted_value))

            process_results = []
            for source_config_copy, extracted_value in to_process:
                result = process_source(dependencies_sources.technology_config, source_config_copy, source_logger)
                process_results.append({
                    'extracted_value': extracted_value,
                    'result': result
                })
            processed_results_dict[source_name] = process_results
        else:
            result = process_source(dependencies_sources.technology_config, source_config, source_logger)
            processed_results_dict[source_name] = result

    return processed_results_dict

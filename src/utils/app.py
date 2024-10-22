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
from typing import List, Tuple
if TYPE_CHECKING:
    from app.config import Config, SourceConfig, TechnologyConfig, DependentSources

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

def schedule_isolated(isolated_technologies, source_config_map, entities_path):
    """Programa las tecnologías aisladas."""
    for tech in isolated_technologies:
        entity_name, tech_name, source_name = tech.split(".")
        tech_config, source_config = source_config_map[tech]
        schedule_source(entity_name, tech_name, source_name, tech_config, source_config, entities_path)

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
                if not dependency_name in processed_results_dict:
                    raise ValueError(f"No se encontraron resultados para la dependencia '{dependency_name}'")
            
            for param, path_str in source_config.extract_from.items():
                path_keys = path_str.split(".")
                first_key = path_keys[0]

                if not first_key in processed_results_dict:
                    raise ValueError(f"No se encontraron resultados para la clave '{first_key}' en el diccionario global")

                current_data = processed_results_dict[first_key]
                remaining_keys = path_keys[1:]

                logger.debug(f"Extrayendo '{param}' de '{dependency_name}' con la ruta: {path_keys}")

                extracted_values = extract_values_from_path(current_data, remaining_keys)
                
                logger.debug(f"Valores extraídos para '{param}': {extracted_values}")

                # Procesar cada valor extraído de manera individual
                for value in extracted_values:
                    # Creamos una copia del source_config para cada valor extraído
                    source_config_copy = deepcopy(source_config)
                    source_config_copy.endpoint = source_config_copy.endpoint.replace(f"{{{param}}}", str(value))

                    # Procesar el endpoint con el valor reemplazado
                    result = process_source(dependencies_sources.technology_config, source_config_copy, source_logger)

                    # Guardar o acumular los resultados según sea necesario
                    if source_name in processed_results_dict:
                        existing_results = processed_results_dict[source_name]
                        if isinstance(existing_results, list):
                            existing_results.append(result)
                        else:
                            processed_results_dict[source_name] = [existing_results, result]
                    else:
                        processed_results_dict[source_name] = result

        result = process_source(dependencies_sources.technology_config, source_config, source_logger)

        # Guardar o acumular los resultados según sea necesario
        if source_name in processed_results_dict:
            existing_results = processed_results_dict[source_name]
            if isinstance(existing_results, list):
                existing_results.append(result)
            else:
                processed_results_dict[source_name] = [existing_results, result]
        else:
            processed_results_dict[source_name] = result

    # logger = get_logger()

    # # Diccionario global para almacenar todos los resultados


    # # Función auxiliar para procesar una fuente y sus dependencias
    # def process_source_with_dependencies(tech_config: 'TechnologyConfig', source_config: 'SourceConfig', source_xpath):
    #     entity_name, tech_name, source_name = source_xpath.split(".")
    #     if source_name in processed_sources:
    #         return  # Ya procesado

    #     # Procesar dependencias primero
    #     if source_config.dependencies:
    #         for dependency_name in source_config.dependencies:
    #             # Verificar si la dependencia ya ha sido procesada
    #             if dependency_name not in processed_sources:
    #                 # Buscar la fuente de la que depende
    #                 dependency = next(
    #                     (t, s, x) for t, s, x in dependency_graph if x.endswith(dependency_name)
    #                 )
    #                 process_source_with_dependencies(*dependency)

    #     # Ahora procesar la fuente actual
    #     source_path = path.join(entities_path, entity_name, tech_name, source_name)
    #     os.makedirs(source_path, exist_ok=True)
    #     source_logger = setup_source_logger(
    #         source_xpath, source_path,
    #         max_num_files=tech_config.max_num_files,
    #         max_file_size=tech_config.max_file_size
    #     )

    #     # Si la fuente tiene extract_from y replace_in, procesamos los valores necesarios
    #     if source_config.dependencies and source_config.extract_from:
    #         # Obtener los resultados de las dependencias
    #         for dependency_name in source_config.dependencies:
    #             dependency_results = processed_results_dict.get(dependency_name)
    #             if not dependency_results:
    #                 raise ValueError(f"No se encontraron resultados para la dependencia '{dependency_name}'")

    #             # Iteramos sobre las claves en `extract_from`
    #             for param, path_str in source_config.extract_from.items():
    #                 path_keys = path_str.split(".")  # Dividimos la cadena en claves

    #                # Usamos la primera clave para buscar en el diccionario global
    #                 first_key = path_keys[0]
    #                 if first_key not in processed_results_dict:
    #                     raise ValueError(f"No se encontraron resultados para la clave '{first_key}' en el diccionario global")
                    
    #                 # Tomamos los resultados iniciales de la primera clave
    #                 current_data = processed_results_dict[first_key]
                    
    #                 # Continuamos con las claves restantes
    #                 remaining_keys = path_keys[1:]

    #                 logger.debug(f"Extrayendo '{param}' de '{dependency_name}' con la ruta: {path_keys}")

    #                 # Extraemos los valores finales siguiendo la ruta de claves
    #                 extracted_values = extract_values_from_path(current_data, remaining_keys)
    #                 logger.debug(f"Valores extraídos para '{param}': {extracted_values}")

    #                 # Para cada valor extraído, reemplazar en el endpoint
    #                 for value in extracted_values:
    #                     updated_source_config = deepcopy(source_config)
    #                     # Reemplazar el parámetro en el endpoint
    #                     if param in updated_source_config.extract_from:
    #                         updated_source_config.endpoint = updated_source_config.endpoint.replace(
    #                             f"{{{param}}}", str(value)
    #                         )


    #                     # Procesar la fuente con el endpoint actualizado
    #                     # logger.info(f"Procesando fuente '{updated_source_config}' con el endpoint actualizado")
    #                     result = process_source(tech_config, updated_source_config, source_logger)

    #                     # Guardar o acumular los resultados según sea necesario
    #                     if source_name in processed_results_dict:
    #                         # Si ya hay resultados, agregamos el nuevo
    #                         existing_results = processed_results_dict[source_name]
    #                         if isinstance(existing_results, list):
    #                             existing_results.append(result)
    #                         else:
    #                             processed_results_dict[source_name] = [existing_results, result]
    #                     else:
    #                         processed_results_dict[source_name] = result

    #     else:
    #         # Fuente sin dependencias o sin reemplazos, procesamos directamente
    #         result = process_source(tech_config, source_config, source_logger)
    #         processed_results_dict[source_name] = result

    #     # Marcar la fuente como procesada
    #     processed_sources.add(source_name)

    # # Procesar todas las fuentes
    # for tech_config, source_config, source_xpath in dependency_graph:
    #     process_source_with_dependencies(tech_config, source_config, source_xpath)

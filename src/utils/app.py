from datetime import datetime
from collections import defaultdict
import schedule
import arrow
import os
from os import path
from copy import deepcopy

from utils import cleanup_logs_for_sources
from utils.logger import get_logger, setup_source_logger
from app.apis import process_source
from . import querystring_parse

from typing import TYPE_CHECKING
from typing import List, Tuple
if TYPE_CHECKING:
    from app.config import Config, SourceConfig, TechnologyConfig

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


def schedule_dependencies(dependency_graph: List[Tuple['TechnologyConfig', 'SourceConfig', str]], entities_path: str):
    # Diccionario global para almacenar todos los resultados
    processed_results_dict = {}
    processed_sources = set()

    # Función auxiliar para procesar una fuente y sus dependencias
    def process_source_with_dependencies(tech_config: 'TechnologyConfig', source_config: 'SourceConfig', source_xpath):
        entity_name, tech_name, source_name = source_xpath.split(".")
        if source_name in processed_sources:
            return  # Ya procesado

        # Procesar dependencias primero
        if source_config.dependencies:
            for dependency_name in source_config.dependencies:
                # Verificar si la dependencia ya ha sido procesada
                if dependency_name not in processed_sources:
                    # Buscar la fuente de la que depende
                    dependency = next(
                        (t, s, x) for t, s, x in dependency_graph if x.endswith(dependency_name)
                    )
                    process_source_with_dependencies(*dependency)

        # Ahora procesar la fuente actual
        source_path = path.join(entities_path, entity_name, tech_name, source_name)
        os.makedirs(source_path, exist_ok=True)
        logger = setup_source_logger(
            source_xpath, source_path,
            max_num_files=tech_config.max_num_files,
            max_file_size=tech_config.max_file_size
        )

        # Si la fuente tiene extract_from y replace_in, procesamos los valores necesarios
        if source_config.dependencies and source_config.extract_from:
            # Obtener los resultados de las dependencias
            for dependency_name in source_config.dependencies:
                dependency_results = processed_results_dict.get(dependency_name)
                if not dependency_results:
                    raise ValueError(f"No se encontraron resultados para la dependencia '{dependency_name}'")

                # Iteramos sobre las claves en `extract_from`
                for param, path_str in source_config.extract_from.items():
                    path_keys = path_str.split(".")  # Dividimos la cadena en claves

                   # Usamos la primera clave para buscar en el diccionario global
                    first_key = path_keys[0]
                    if first_key not in processed_results_dict:
                        raise ValueError(f"No se encontraron resultados para la clave '{first_key}' en el diccionario global")
                    
                    # Tomamos los resultados iniciales de la primera clave
                    current_data = processed_results_dict[first_key]
                    
                    # Continuamos con las claves restantes
                    remaining_keys = path_keys[1:]

                    print(f"Extrayendo '{param}' de '{dependency_name}' con la ruta: {path_keys}")

                    # Extraemos los valores finales siguiendo la ruta de claves
                    extracted_values = extract_values_from_path(current_data, remaining_keys)
                    print(f"Valores extraídos para '{param}': {extracted_values}")


                    # Para cada valor extraído, reemplazar en el endpoint
                    for value in extracted_values:
                        updated_source_config = deepcopy(source_config)
                        # Reemplazar el parámetro en el endpoint
                        if param in updated_source_config.extract_from:
                            updated_source_config.endpoint = updated_source_config.endpoint.replace(
                                f"{{{param}}}", str(value)
                            )


                        # # Procesar la fuente con el endpoint actualizado
                        # result = process_source(tech_config, updated_source_config, logger)

                        # # Guardar o acumular los resultados según sea necesario
                        # if source_name in processed_results_dict:
                        #     # Si ya hay resultados, agregamos el nuevo
                        #     existing_results = processed_results_dict[source_name]
                        #     if isinstance(existing_results, list):
                        #         existing_results.append(result)
                        #     else:
                        #         processed_results_dict[source_name] = [existing_results, result]
                        # else:
                        #     processed_results_dict[source_name] = result

        else:
            # Fuente sin dependencias o sin reemplazos, procesamos directamente
            result = process_source(tech_config, source_config, logger)
            processed_results_dict[source_name] = result

        # Marcar la fuente como procesada
        processed_sources.add(source_name)

    # Procesar todas las fuentes
    for tech_config, source_config, source_xpath in dependency_graph:
        process_source_with_dependencies(tech_config, source_config, source_xpath)

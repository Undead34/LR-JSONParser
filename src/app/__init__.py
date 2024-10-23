import os
import time
from os import path
import schedule
from collections import defaultdict

from utils.logger import get_logger
from utils import topological_sort
from utils.app import process_entities, schedule_isolated, schedule_dependencies
from .config import DependentSources, IsolatedSources


from typing import TYPE_CHECKING
from typing import Tuple, List, Set, cast
if TYPE_CHECKING:
    from .config import Config, EntityConfig, TechnologyConfig, SourceConfig


import rich

def run_interactive_mode(args) -> 'Config':
    logger = get_logger()
    return config

def classify_sources(config: 'Config', entities_path) -> List[Tuple[DependentSources, IsolatedSources, Tuple[str, str]]]:
    logger = get_logger()

    # Procesar entidades y construir el grafo de dependencias
    source_graph = process_entities(config, logger)

    entities_technologies = []

    for sources in source_graph.values():
        entity_config, tech_config, names = cast(Tuple['EntityConfig', 'TechnologyConfig', Tuple[str, str]], sources[0])
        sources.pop(0)

        sources = cast(List[Tuple['SourceConfig', str]], sources)

        isolated_sources: Set[Tuple['SourceConfig', str]] = set()
        dependent_sources: Set[Tuple['SourceConfig', str]] = set()

        # Paso 1: Identificar las fuentes que tienen dependencias
        for source_config, source_name in sources:
            if source_config.dependencies:
                dependent_sources.add((source_config, source_name))

        # Paso 2: Asegurarse de que todas las dependencias estén en dependent_sources
        temp_dependent_sources: Set[Tuple[SourceConfig, str]] = set()
        for dependent_source, _ in dependent_sources:
            for source_config, source_name in sources:
                if source_name in dependent_source.dependencies:
                    temp_dependent_sources.add((source_config, source_name))

        dependent_sources.update(temp_dependent_sources)

        # Paso 3: Identificar las fuentes sin dependencias que tampoco son dependientes
        for source_config, source_name in sources:
            if not source_config.dependencies:
                # Verificar que no esté en dependent_sources ni en las dependencias de otras fuentes
                is_dependent = False
                for dep_source, dep_name in dependent_sources:
                    if source_name in dep_source.dependencies:
                        is_dependent = True
                        break

                if not is_dependent and (source_config, source_name) not in dependent_sources:
                    isolated_sources.add((source_config, source_name))

        # Paso 4: Crear el grafo de dependencias SOLO para fuentes dependientes
        dependency_graph = defaultdict(list)

        for dependent_source, dependent_name in dependent_sources:
            for source_config, source_name in sources:
                if source_name in dependent_source.dependencies:
                    dependency_graph[source_name].append(dependent_name)

        try:
            tmp_sorted_sources: List[str] = topological_sort(dependency_graph)
            if isinstance(tmp_sorted_sources, str):
                raise Exception(tmp_sorted_sources)
            
            logger.info("Ordenamiento topológico exitoso")
            logger.info("Fuentes ordenadas: %s", tmp_sorted_sources)
            
            sorted_sources = []
            for source_name in tmp_sorted_sources:
                for source_config, name in sources:
                    if name == source_name:
                        sorted_sources.append((source_config, name))
                        break

            dependent_sources = DependentSources(
                entity_config = entity_config,
                technology_config = tech_config,
                sources_name = [name for _, name in sorted_sources],
                sources = sorted_sources
            )

            _isolated_sources = IsolatedSources(
                entity_config = entity_config,
                technology_config = tech_config,
                sources_name = [name for _, name in isolated_sources],
                sources = isolated_sources
            )

            entities_technologies.append((dependent_sources, _isolated_sources, names))

        except Exception as e:
            logger.exception("Error en el ordenamiento topológico", exc_info=e)

    return entities_technologies

def run_main_program(args, config: 'Config') -> None:
    logger = get_logger()
    logger.info("Configuración cargada")

    base_path = path.realpath(path.dirname(args.config_file))
    entities_path = path.join(base_path, "entities")
    logger.info("Directorio base: %s", base_path)
    os.makedirs(entities_path, exist_ok=True)

    # Clasificar las fuentes en dependientes y aisladas
    entities_technologies = classify_sources(config, entities_path)

    for dependencies_sources, isolated_sources, names in entities_technologies:
        rich.print("_" * 80)
        rich.print(f"[bold]Entidad:[/bold] {dependencies_sources.entity_config.name}")
        rich.print(f"[bold]Tecnología:[/bold] {dependencies_sources.technology_config.source_name}")
        rich.print(f"[bold]Fuentes dependientes:[/bold] {dependencies_sources.sources_name}")
        rich.print(f"[bold]Fuentes aisladas:[/bold] {[source_name for _, source_name in isolated_sources.sources]}")
        rich.print("_" * 80)

        schedule_dependencies(dependencies_sources, entities_path, names)
        schedule_isolated(isolated_sources, entities_path, names)

    while True:
        schedule.run_pending()
        time.sleep(1)

import winreg
import arrow
import os

from rich import pretty
from rich.console import Console
from io import StringIO

def format_text(text: str) -> str:
        console = Console(file=StringIO())
        console.print(pretty.Pretty(text))
        formatted_text = console.file.getvalue()
        return formatted_text

def get_agent_state_path(log_source_id) -> str:
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\LogRhythm\scsm")
        agent_state, _ = winreg.QueryValueEx(key, "STATEPATH")
        return os.path.normpath(f"{agent_state}\\state\\{log_source_id}")
    except Exception as e:
        raise

def cleanup_logs_for_sources(log_sources_ids, logger):
    if isinstance(log_sources_ids, int):
        log_sources_ids = [log_sources_ids]

    if not log_sources_ids:
        logger.error("No log sources provided for cleanup.")
        return

    for log_source_id in log_sources_ids:
        try:
            state_path = get_agent_state_path(log_source_id)
            if not os.path.exists(state_path):
                logger.warning(f"LogRhythm status directory not found for {log_source_id}.")
                continue

            logger.info(f"Cleaning residues for agent: {state_path}")
            removed_files = process_pos_files(state_path, logger)

            logger.info(f"{removed_files} files removed for log source ID {log_source_id}.")
        except Exception as e:
            logger.error(f"Error while cleaning logs for source {log_source_id}: {e}")

def process_pos_files(state_path, logger) -> int:
    removed_files = 0
    for file in os.listdir(state_path):
        if file.endswith(".pos"):
            pos_file_path = os.path.join(state_path, file)
            try:
                with open(pos_file_path, "r") as f:
                    pos_file = f.read().splitlines()

                    # Verificar si el archivo de log mencionado existe y si su tamaño coincide
                    if os.path.exists(pos_file[0]) and os.path.getsize(pos_file[0]) == int(pos_file[1]):
                        os.remove(pos_file[0])
                        logger.info(f"Removed file: {pos_file[0]}")
                        removed_files += 1
            except Exception as e:
                logger.error(f"Failed to process {file}: {e}")
    return removed_files

def querystring_parse(source_config):
    for key, querystring in source_config.querystring.items():
        if isinstance(querystring, dict) and 'value' in querystring and 'type' in querystring:
            value_type = querystring.get("type")
            value = querystring.get("value")

            if value_type == "ISO8601":
                try:
                    time = arrow.utcnow().dehumanize(value)
                    formatted_value = time.isoformat()
                    source_config.querystring[key] = formatted_value
                except ValueError:
                    print(f"Could not dehumanize {key}: {value}")
            else:
                try:
                    formatted_value = arrow.utcnow().dehumanize(value).strftime(value_type)
                    source_config.querystring[key] = formatted_value
                except Exception as e:
                    print(f"Could not format {key}: {e}")
    
    return source_config

from collections import defaultdict, deque

# Función para realizar el ordenamiento topológico
def topological_sort(dependency_graph):
    # Diccionario para contar el número de dependencias entrantes de cada nodo
    in_degree = defaultdict(int)

    # Inicializar el in_degree con el conteo de aristas entrantes para cada nodo
    for node in dependency_graph:
        for neighbor in dependency_graph[node]:
            in_degree[neighbor] += 1

    # Cola para almacenar los nodos sin dependencias entrantes
    queue = deque([node for node in dependency_graph if in_degree[node] == 0])

    # Lista para almacenar el orden topológico
    topo_order = []

    while queue:
        # Tomamos el primer nodo sin dependencias
        current = queue.popleft()
        topo_order.append(current)

        # Reducimos el grado entrante de los nodos vecinos
        for neighbor in dependency_graph[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Si el orden topológico contiene todos los nodos, hemos terminado exitosamente
    if len(topo_order) == len(dependency_graph):
        return topo_order
    else:
        # Si no, existe un ciclo en el grafo
        return "Error: El grafo tiene un ciclo y no se puede realizar el ordenamiento topológico"

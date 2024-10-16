from typing import TYPE_CHECKING, Dict, Optional, Union

from utils.logger import get_logger, setup_source_logger

import requests, json, os
from os import path
from requests.exceptions import RequestException
from retry import retry

if TYPE_CHECKING:
    from config import SourceConfig, TechnologyConfig, EntityConfig

logger = get_logger()

@retry(RequestException, tries=3, delay=1)
def fetch(
    url: str,
    method: str = "GET",
    query_params: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    data: Optional[Dict] = None
) -> Union[Dict, str, None]:
    headers = headers or {}
    query_params = query_params or {}
    data = data or {}
    try:
        logger.info(f"Fetching URL: {url} with method: {method}, params: {query_params} and data: {data}")

        if method.upper() == "GET":
            response = requests.get(url, params=query_params, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, headers=headers)
        elif method.upper() == "PUT":
            response = requests.put(url, json=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, params=query_params, headers=headers)
        else:
            raise ValueError(f"HTTP method {method} not supported")

        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type and response.content:
                logger.info(f"Successful JSON response from {url}")
                return response.json()  # Devuelve un diccionario si es JSON
            else:
                logger.info(f"Successful non-JSON response from {url}")
                return response.text  # Devuelve un string si no es JSON
        elif response.status_code == 429:
            logger.warning(f"Rate limit exceeded for {url}, retrying...")
            raise RequestException(f"HTTP 429: Rate limit exceeded for {url}")
        else:
            logger.error(f"Failed request to {url}: {response.status_code} - {response.text}")
            return None
    except RequestException as e:
        logger.exception(f"Request to {url} failed with exception: {e}")
        raise  # Re-lanzar la excepción para que `retry` la capture


def paginated_link_api(url: str, headers: Dict, method, source_config: 'SourceConfig', next_link_key, items_key) -> Dict:
    items = []
    results = {}
    next_link = None

    while True:
        # Si no hay next_link, usa el querystring del source_config
        query_params = source_config.querystring if next_link is None else {}
        request_url = url if next_link is None else next_link

        r = fetch(request_url, method, query_params=query_params, headers=headers)

        if r and isinstance(r, dict):
            if items_key in r and isinstance(r[items_key], list):
                items.extend(r[items_key])  # Acumula los items

            if next_link_key not in r or not r[next_link_key]:
                # Si no hay más nextLink, termina el ciclo
                results = r
                results[items_key] = items  # Agrega los items acumulados al resultado
                break

            # Actualiza next_link para la siguiente iteración
            next_link = r.get(next_link_key)
        else:
            logger.error("Failed to retrieve data or unexpected response format.")
            break

    return results

def process_source(tech_config: 'TechnologyConfig', source_config: 'SourceConfig', source_logger):
    url = tech_config.base_url + source_config.endpoint

    headers = {}
    if tech_config.authentication.lower() == "bearer":
        headers["Authorization"] = f"Bearer {tech_config.api_token}"
    headers.update(source_config.headers)

    method = source_config.method.upper()

    if tech_config.pagination:
        next_link_key = tech_config.pagination.get("next_link_key")
        items_key = tech_config.pagination.get("items_key")
        results = paginated_link_api(url, headers, method, source_config, next_link_key, items_key)

        if results:            
            for item in results.get(items_key, []):                
                source_logger.info(json.dumps(item))
            
            return results
    else:
        raise NotImplementedError("Pagination method not implemented yet.")
    
def process_dependents_source(logger_name, source_path, entity_config: 'EntityConfig', tech_config: 'TechnologyConfig', source_config: 'SourceConfig', dependents: list['SourceConfig']):
    logger.info(f"Processing dependents for source: {source_config.name}")
    print(dependents)
    # source_logger = setup_source_logger(logger_name, source_path, max_num_files=tech_config.max_num_files, max_file_size=tech_config.max_file_size)



# extract_from = source_config.extract_from.split('.')
# if "items_key" in extract_from:
#     extract_from.pop(extract_from.index("items_key"))
# extract_data = []
#             for key in extract_from:
#         extract_data.append(item.get(key, None))

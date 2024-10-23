from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, List, Optional, Set
import toml
from toml.decoder import InlineTableDict
from datetime import datetime
import os

@dataclass
class SourceConfig:
    enabled: bool
    interval: int
    name: str
    endpoint: str
    method: str
    headers: Dict[str, Any] = field(default_factory=dict)
    querystring: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    extract_from: Optional[Dict[str, str]] = None

    def __hash__(self):
        def make_hashable(value):
            if isinstance(value, dict):
                return frozenset((k, make_hashable(v)) for k, v in value.items())
            elif isinstance(value, list):
                return tuple(make_hashable(v) for v in value)
            elif isinstance(value, InlineTableDict):
                return frozenset(value.items())
            return value

        headers_hashable = make_hashable(self.headers)
        querystring_hashable = make_hashable(self.querystring)
        extract_from_hashable = make_hashable(self.extract_from) if self.extract_from else None

        return hash((
            self.enabled,
            self.interval,
            self.name,
            self.endpoint,
            self.method,
            headers_hashable,  # Usar la versión hashable de headers
            querystring_hashable,  # Usar la versión hashable de querystring
            tuple(self.dependencies),  # Convertir la lista de dependencias en una tupla
            extract_from_hashable  # Usar la versión hashable de extract_from o None si es None
        ))


    def __eq__(self, other):
        if not isinstance(other, SourceConfig):
            return False
        return (
            self.enabled == other.enabled and
            self.interval == other.interval and
            self.name == other.name and
            self.endpoint == other.endpoint and
            self.method == other.method and
            self.headers == other.headers and
            self.querystring == other.querystring and
            self.dependencies == other.dependencies and
            self.extract_from == other.extract_from
        )

@dataclass
class TechnologyConfig:
    enabled: bool
    source_name: str
    base_url: str
    api_token: str
    expiration_date_token: datetime
    authentication: str
    log_sources_ids: List[int]
    max_num_files: int
    max_file_size: str
    sources: Dict[str, SourceConfig] = field(default_factory=dict)
    pagination: Optional[Dict[str, str]] = None

@dataclass
class EntityConfig:
    name: str
    path: Optional[str]
    technologies: Dict[str, TechnologyConfig] = field(default_factory=dict)

@dataclass
class Config:
    version: str
    developer: str
    entities: Dict[str, EntityConfig] = field(default_factory=dict)


@dataclass
class IsolatedSources:
    entity_config: EntityConfig
    technology_config: TechnologyConfig
    sources_name: List[str]
    sources: Set[Tuple['SourceConfig', str]]

@dataclass
class DependentSources:
    entity_config: EntityConfig
    technology_config: TechnologyConfig
    sources_name: List[str]
    sources: List[Tuple[SourceConfig, str]]

# Función para cargar y mapear el archivo TOML a las clases
def load_config(file_path: str) -> Config:
    data = toml.load(file_path)
    
    version = data.get("version", "")
    developer = data.get("developer", "")
    
    entities = {}
    for entity_name, entity_data in data.items():
        if entity_name in ("version", "developer"):
            continue  # Saltamos claves no relacionadas con entidades
        if not isinstance(entity_data, dict):
            continue  # Saltamos si no es un diccionario
        
        entity_config = EntityConfig(
            name=entity_data.get("name", ""),
            path=entity_data.get("path", None),
            technologies={}
        )
        
        if entity_config.path is not None:
            _entity_data = toml.load(os.path.realpath(entity_config.path))
            entity_data.update(_entity_data.get(entity_name, {}))
        

        for tech_name, tech_data in entity_data.items():
            if not isinstance(tech_data, dict) or 'enabled' not in tech_data:
                continue  # Saltamos claves que no son tecnologías


            # Procesamos la fecha para evitar el error de strptime
            expiration_date_token = tech_data.get("expiration_date_token", datetime.max)
            if isinstance(expiration_date_token, str):
                expiration_date_token = datetime.strptime(expiration_date_token, "%Y-%m-%dT%H:%M:%SZ")

            # Extraemos campos de la tecnología
            tech_config = TechnologyConfig(
                enabled=tech_data.get("enabled", False),
                source_name=tech_data.get("source_name", ""),
                base_url=tech_data.get("base_url", ""),
                api_token=tech_data.get("api_token", ""),
                expiration_date_token=expiration_date_token,
                authentication=tech_data.get("authentication", ""),
                log_sources_ids=list(tech_data.get("log_sources_ids", [])),
                max_num_files=tech_data.get("max_num_files", 0),
                max_file_size=tech_data.get("max_file_size", ""),
                pagination=tech_data.get("pagination", None),
                sources={}
            )
            
            # Procesamos las fuentes dentro de la tecnología
            for source_name, source_data in tech_data.items():
                if not isinstance(source_data, dict) or 'enabled' not in source_data:
                    continue  # Saltamos claves que no son fuentes

                # Extraemos campos de la fuente
                
                source_config = SourceConfig(
                    enabled=source_data.get("enabled", False),
                    interval=source_data.get("interval", None),
                    name=source_data.get("name", ""),
                    endpoint=source_data.get("endpoint", ""),
                    method=source_data.get("method", ""),
                    headers=dict(source_data.get("headers", {})),
                    querystring=dict(source_data.get("querystring", {})),
                    dependencies=list(source_data.get("dependencies", [])),
                    extract_from=dict(source_data.get("extract_from", None)) if source_data.get("extract_from", None) else None
                )
                
                tech_config.sources[source_name] = source_config
            
            entity_config.technologies[tech_name] = tech_config
        
        entities[entity_name] = entity_config
    
    return Config(
        version=version,
        developer=developer,
        entities=entities
    )

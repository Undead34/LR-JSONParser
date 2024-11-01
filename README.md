# LR-JSONParser

Este repositorio facilita la integración de múltiples APIs en LogRhythm y es útil para otros contextos donde se requiera una configuración similar.

El archivo de configuración utiliza el formato [TOML](https://toml.io/en/), que permite una configuración legible y fácil de editar.

---

## Funcionamiento

LR-JSONParser permite la integración de diversas fuentes y endpoints para cada entidad, como se muestra en el siguiente diagrama:

```mermaid
graph LR
A[Entity A] --> B1[Technology A.1] --> E1[Source / Endpoint A.1.1]
B1 --> E2[Source / Endpoint A.1.2]
A --> C1[Technology A.2] --> E3[Source / Endpoint A.2.1]
C1 --> E4[Source / Endpoint A.2.2]
D[Entity B] --> B2[Technology B.1] --> E5[Source / Endpoint B.1.1]
B2 --> E6[Source / Endpoint B.1.2]
D --> C2[Technology B.2] --> E7[Source / Endpoint B.2.1]
C2 --> E8[Source / Endpoint B.2.2]
```

El siguiente diagrama de secuencia describe cómo interactúan los componentes principales del sistema:

```mermaid
sequenceDiagram
    participant A as Cloud API
    participant B as LR-JSONParser
    participant C as File System
    participant D as Elastic Filebeat
    participant E as System Monitor

    A ->> B: Enviar datos
    B ->> C: Escribir en el archivo
    C ->> D: Monitorear cambios
    D ->> E: Reenviar datos vía puerto 5044
```

---

## Requisitos

El script fue desarrollado en Python 3.10.9; se recomienda Python 3.10 o superior para evitar problemas de compatibilidad.

### Dependencias

- **Git** para clonar el repositorio.
- **Python 3.10** o superior.
- **Pip** para instalar las dependencias.

---

## Instalación

Siga estos pasos para instalar y configurar el proyecto en sistemas Linux/macOS y Windows.

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Undead34/LR-JSONParser.git
cd LR-JSONParser
```

### 2. Crear un Entorno Virtual

Utilizar un entorno virtual es recomendado para instalar las dependencias de manera aislada.

#### En Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### En Windows

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Instalar Dependencias

Con el entorno virtual activo, instala las dependencias listadas en `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

## Configuración del Archivo `config.toml`

En la raíz del proyecto encontrarás un archivo `config.example.toml` que sirve como plantilla para crear el archivo de configuración `config.toml`. Este archivo permite integrar diferentes tecnologías y APIs en LogRhythm.

### Ejemplo de Configuración: Integración con Trend Vision One™

#### 1. Crear una Entidad

Para definir una entidad, crea un bloque en `config.toml` con el nombre de la entidad. Se recomienda utilizar el mismo nombre de las entidades en LogRhythm.

```toml
[amazing_organization]
name = "Amazing Organization"
```

#### 2. Agregar una Tecnología a la Entidad

Una vez definida la entidad, añade una tecnología a la misma. A continuación, se muestra la configuración para Trend Vision One™:

```toml
[amazing_organization]
name = "Amazing Organization"

[amazing_organization.trend_vision_one]
source_name = "Trend Vision One™"
enabled = true
base_url = "https://api.xdr.trendmicro.com"
api_token = "eyJ0eZA....eL32hIom"
authentication = "Bearer"
expiration_date_token = 2024-12-31T23:59:59-04:00
max_num_files = 10
max_file_size = "10 MB"
pagination = { next_link_key = "nextLink", items_key = "items" }
```

**Descripción de los campos:**

- `source_name`: Nombre descriptivo de la tecnología.
- `enabled`: Activa o desactiva la tecnología.
- `base_url`: URL base de la API.
- `api_token`: Token de autenticación de la API.
- `authentication`: Tipo de autenticación (`Bearer` para autenticación con token).
- `expiration_date_token`: Fecha de expiración del token en formato ISO 8601.
- `max_num_files`: Número máximo de archivos que rotará el logger.
- `max_file_size`: Tamaño máximo de los archivos del logger (por ejemplo, `10 MB`).
- `pagination`: Parámetros de paginación.

> **Nota:** El campo `authentication` se actualizará en futuras versiones para incluir tipos de autenticación más complejos.

#### 3. Agregar un Endpoint a la Tecnología

Una vez definida la tecnología, añade un endpoint configurando sus detalles:

```toml
[amazing_organization.trend_vision_one.oat]
enabled = true
interval = 300
name = "amazing_organization_trend_vision_one_oat"
endpoint = "/v3.0/oat/detections"
method = "GET"
headers = { TMV1-Filter = "(riskLevel eq 'medium') or (riskLevel eq 'high') or (riskLevel eq 'critical')" }

[amazing_organization.trend_vision_one.oat.querystring]
top = 200
detectedStartDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "5 minutes ago" }
detectedEndDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "just now" }
```

**Descripción de los campos del endpoint:**

- `enabled`: Activa o desactiva el endpoint.
- `interval`: Intervalo en segundos para llamar al endpoint.
- `name`: Nombre del endpoint.
- `endpoint`: Ruta específica de la API.
- `method`: Método HTTP (por ejemplo, `GET` o `POST`).
- `headers`: Encabezados adicionales, como filtros para la solicitud de datos.
- `querystring`: Parámetros de consulta (por ejemplo, `top` define el límite de resultados).

> **Nota:** En `querystring` se puede usar objetos como en el caso de `detectedStartDateTime` y `detectedEndDateTime`, donde `type` puede ser un formato de `strftime` de Python o la palabra clave `ISO8601`, y `value` acepta intervalos compatibles con `humanize` de la librería `arrow`.

Otra forma más limpia de defirnir los `querystring` podría ser.

```toml
[amazing_organization.trend_vision_one.oat]
# ...
querystring = { top = 200, detectedStartDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "5 minutes ago" }, detectedEndDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "just now" } }

```

El único inconveniente es que debe ser inline, o sea no se admiten saltos de línea.

```toml
# BAD CONFIGURATION
[amazing_organization.trend_vision_one.oat]
querystring = { 
    top = 200,
    detectedStartDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "5 minutes ago" }, detectedEndDateTime = { type = "%Y-%m-%dT%H:%M:%SZ", value = "just now" }
}
```

---

## Ejecución de LR-JSONParser

Para ejecutar el script, asegúrate de tener activado el entorno virtual y que la configuración en `config.toml` esté completa. Ejecuta el siguiente comando:

#### En Linux / macOS

```bash
python ./src/main.py -d --config-file ./config.toml
```

#### En Windows

```powershell
python .\src\main.py -d --config-file .\config.toml
```

Los logs generados te ayudarán a identificar cualquier problema durante la ejecución.

---

## Solución de Problemas

- **Error de Dependencia:** Asegúrate de que estás usando Python 3.10 o superior y que las dependencias están instaladas en el entorno virtual.
- **Problemas de Autenticación:** Verifica que el `api_token` y `authentication` estén configurados correctamente en `config.toml`.
- **Problemas de Conexión:** Revisa la conectividad de red y la disponibilidad de los endpoints configurados en el archivo.

---

## Contribuciones

¡Si deseas agregar nuevas características o mejorar las existentes, siéntete libre de contribuir! Este proyecto está diseñado para facilitar la adición de tipos de APIs y configuraciones adicionales. ¡Tu colaboración es bienvenida!

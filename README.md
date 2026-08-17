# it_nav_system

Microservicio de **navegación domótica** para el asistente virtual **Nova**. Gestiona el grafo de nodos (habitaciones y puntos de paso) de una casa inteligente, permite personalizar nombres y alias de voz desde un panel web, y sincroniza esa configuración con la simulación 3D en Unity y una maqueta física.

Este microservicio expone una API REST (FastAPI + SQLite) consumida por tres clientes distintos: un panel web de administración, el proyecto de Unity (navegación 3D + maqueta física), y el microservicio del asistente de voz (Nova), que resuelve comandos hablados a nodos concretos del grafo.

---

## 📋 Requisitos previos

- Python **3.13**
- Node no es necesario (frontend sin frameworks ni build tools)
- Git instalado
- [SQLite Viewer](https://marketplace.visualstudio.com/items?itemName=qwtel.sqlite-viewer) (extensión de VSCode, opcional, para inspeccionar la base de datos)

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/<usuario>/it_nav_system.git
cd it_nav_system
```

### 2. Crear el entorno virtual

```bash
cd backend

# Windows
python -m venv venv

# Mac/Linux
python3 -m venv venv
```

### 3. Activar el entorno virtual

```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

Verifica que el entorno esté activo: el prompt de tu terminal debe mostrar `(venv)` al inicio.

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar la casa activa

Este prototipo opera con una sola casa activa por instalación. Antes de usar el sistema por primera vez, crea la casa desde el endpoint de desarrollador (ver sección de pruebas más abajo) y confirma que su `id` coincide con `ACTIVE_HOUSE_ID` en `app/config.py`:

```python
ACTIVE_HOUSE_ID: int = 1
```

---

## ▶️ Cómo ejecutar el backend

Desde `backend/`, con el entorno virtual activo:

```bash
uvicorn app.main:app --reload --port 8001
```

Al arrancar correctamente verás:

```
Iniciando la API del Sistema de Navegacion de Inclusive Tech - Asistente: NOVA
Base de datos inicializada correctamente.
INFO:     Uvicorn running on http://0.0.0.0:8001
INFO:     Application startup complete.
```

- **Documentación interactiva:** `http://127.0.0.1:8001/docs`
- **Health check:** `http://127.0.0.1:8001/health`

> ⚠️ **Puerto compartido con otros microservicios:** si el microservicio del asistente de voz corre en el puerto `8000`, cambia el puerto de este backend (ej. `--port 8001`) para evitar conflicto, y actualiza esa misma URL en `frontend/js/api.js` y en el asset `NavigationConfig` de Unity.

---

## 🧪 Cómo probar el backend

### Tests automatizados (recomendado)

Desde `backend/`, con el entorno virtual activo:

```bash
pytest -v
```

Los tests usan una base de datos SQLite temporal y aislada (ver `tests/conftest.py`), por lo que **nunca tocan tus datos reales**. Deberías ver los 12 tests pasando:

```
============================== 12 passed in 1.67s ===============================
```

### Prueba manual rápida

1. Levanta el servidor (ver sección anterior)
2. Ve a `http://127.0.0.1:8001/docs`
3. Ejecuta `POST /dev/houses` para crear la casa activa
4. Ejecuta `POST /dev/nodes` para crear un nodo de prueba
5. Ejecuta `GET /user/nodes` y confirma que el nodo aparece

---

## 🖥️ Cómo ejecutar el panel web (frontend)

El panel web es una versión funcional mínima (HTML/CSS/JS sin frameworks), pensada para validar el flujo completo con el backend. **No requiere instalación**: solo ábrelo directamente en el navegador.

1. Asegúrate de que el backend esté corriendo
2. Verifica que `API_BASE_URL` en `frontend/js/api.js` apunte al puerto correcto de tu backend
3. Abre `frontend/index.html` con doble clic, o arrástralo a una pestaña del navegador

Desde el panel podrás:
- Ver los nodos (habitaciones y waypoints) de la casa activa
- Renombrar una habitación (`display_name`)
- Agregar o eliminar alias de voz (hasta 5 por nodo)

> 📌 Este frontend está pendiente de rediseño por el equipo. Ver la sección de pendientes en `frontend/PENDIENTES.md` (o el board de Notion del proyecto) para el detalle completo de qué puede y qué no debe cambiarse.

---

## 🎮 Integración con Unity

El proyecto de Unity consume este backend en dos momentos:

1. **Registro de nodos (herramienta de desarrollador):** desde el Inspector de cada `NavigationNode`, un botón permite registrarlo contra `POST /dev/nodes`, capturando automáticamente su posición y tipo (`room`/`waypoint`).
2. **Resolución de comandos de voz (runtime):** al iniciar la escena, Unity consulta `GET /user/nodes` y construye una tabla de nombres/alias reconocibles por el asistente Nova. Esta tabla se actualiza periódicamente (polling) para reflejar cambios hechos desde el panel web sin reiniciar la escena.

Configuración necesaria en Unity: crear un asset `NavigationConfig` (`Assets > Create > Inclusive Tech > Navigation Config`) con la URL y puerto del backend, y asignarlo en el componente `RoomNameBootstrap` de la escena.

---

## 📡 Endpoints principales

| Método | Ruta | Descripción | Uso |
|---|---|---|---|
| `GET` | `/health` | Verifica que el servidor está activo | Todos |
| `POST` | `/dev/houses` | Crea una nueva casa | Desarrollador |
| `POST` | `/dev/nodes` | Crea un nodo (habitación o waypoint) | Unity (Editor) |
| `DELETE` | `/dev/nodes/{id}` | Elimina un nodo | Unity (Editor) |
| `PATCH` | `/dev/nodes/{id}/physical-position` | Actualiza posición física en la maqueta | Desarrollador |
| `POST` | `/dev/edges` | Conecta dos nodos del grafo | Unity (Editor) |
| `DELETE` | `/dev/edges/{id}` | Elimina una conexión | Unity (Editor) |
| `GET` | `/user/nodes` | Lista los nodos activos de la casa | Panel web, Unity (runtime) |
| `GET` | `/user/nodes/{id}` | Detalle de un nodo | Panel web |
| `PATCH` | `/user/nodes/{id}/display-name` | Renombra un nodo | Panel web |
| `POST` | `/user/nodes/{id}/aliases` | Agrega un alias de voz | Panel web |
| `DELETE` | `/user/nodes/{id}/aliases/{alias_id}` | Elimina un alias | Panel web |

Documentación completa e interactiva disponible en `/docs` con el servidor corriendo.

---

## 🏗️ Arquitectura

El backend sigue **arquitectura limpia por capas**:

```
presentation/    → Endpoints HTTP (routers), validación con Pydantic
application/     → Lógica de negocio (servicios)
domain/          → Entidades y contratos, independientes de la base de datos
infrastructure/  → Acceso a datos (SQLite), implementación de los repositorios
```

**Patrones de diseño aplicados:** Singleton (conexión a base de datos), Factory Method (construcción validada de entidades), Repository, Dependency Injection, Facade (servicios y cliente HTTP del frontend), DTO (schemas Pydantic).

---

## 📌 Decisiones de arquitectura relevantes

- **Multi-casa a nivel de datos, single-casa en operación:** el modelo soporta múltiples casas (tabla `houses`), pero cada instalación física opera con una única casa activa fija por configuración (`ACTIVE_HOUSE_ID`). Esto permite escalar a un modelo multiusuario en el futuro sin refactorizar el dominio.
- **`internal_name` vs `display_name`:** el nombre técnico de un nodo (`internal_name`) es inmutable y solo lo define el desarrollador desde Unity. El nombre visible (`display_name`) y los alias son editables por el usuario final desde el panel web, y son los únicos que compiten en el reconocimiento de voz.
- **Instalación local, no SaaS:** cada instalación (una maqueta, un backend) tiene su propia base de datos SQLite aislada. No hay una base de datos centralizada compartida entre instalaciones.

---

## 📁 Estructura del proyecto

```
it_nav_system/
├── backend/
│   ├── app/
│   │   ├── domain/            # Entidades y contratos (Node, House, interfaces)
│   │   ├── infrastructure/    # SQLite: conexión, schema, repositorios
│   │   ├── application/       # Servicios (lógica de negocio)
│   │   ├── presentation/      # Routers (dev/user) y schemas Pydantic
│   │   ├── config.py          # Constantes centralizadas del sistema
│   │   └── main.py            # Punto de entrada FastAPI
│   ├── data/                  # Base de datos SQLite (no versionada)
│   ├── tests/                 # Tests de integración (pytest)
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/
│       ├── api.js             # Capa de datos (comunicación con el backend)
│       └── app.js             # Capa de presentación (DOM, eventos)
│
└── unity-tools/                # Scripts de Unity para registro de nodos (Editor)
```

---

## 🌐 Contexto del proyecto

Este módulo forma parte de un sistema mayor de casa domótica inclusiva, compuesto por una simulación 3D en Unity, una maqueta física (LEDs, puertas automáticas, agente móvil) y un asistente de voz (Nova). Su responsabilidad es ser la única fuente de verdad sobre qué nodos existen en la casa, cómo se llaman, y cómo están conectados, información que tanto la navegación en Unity como el reconocimiento de comandos de voz consultan en tiempo real.

---

## 👥 Equipo

Proyecto desarrollado en la **Fundación Universitaria Konrad Lorenz** como parte del proyecto de grado - **INCLUSIVE_TECH**.

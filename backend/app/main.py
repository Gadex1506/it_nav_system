"""
app/main.py

Punto de entrada principal de la API del sistema de navegacion de Inclusive Tech..

Responsabilidad: Crear y configurar la instancia de FastAPI,
registrar los routers y gestionar los eventos del ciclo de vida
de la aplicacion (inicio y cierre).

Principio SOLID aplicado:
    - S (Single Responsibility): Este modulo solo configura y
    arranca la aplicacion, no contiene logica de negocio.
    - O (Open/Closed): Nuevos routers se agregan sin modificar
    la configuracion existente.
"""

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.database import db
from app.config import ASSISTANT_NAME


# # --- Importar Routers ------------------------------------------
from app.presentation.routers.dev_router import router as dev_router
from app.presentation.routers.user_router import router as user_router

# =============================================================
# Ciclo de vida de la aplicacion (Startup y Shutdown)
# =============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestiona el ciclo de vida completo de la aplicacion.
    
    Al iniciar: inicializa la conexion y el schema de la DB.
    Al cerrar: cierra la conexion a la DB de forma ordenada.

    Args:
        app: Instancia de FastAPI. Es requerido por el decorador @app.on_event.
    """

    # ── Inicio del servidor ──
    print(f"Iniciando la API del Sistema de Navegacion de Inclusive Tech - Asistente: {ASSISTANT_NAME}")
    db.initialize_schema()
    print("Base de datos inicializada correctamente.")

    yield # El servidor esta corriendo aqui

    # ── Cierre del servidor ──
    db.close()
    print("Conexion a la base de datos cerrada.")

# =============================================================
# Instancia principal de FastAPI
# =============================================================
app = FastAPI(
    title="API del Sistema de Navegación de Inclusive Tech",
    description=(
        f"API del sistema de navegación domótica con asistente {ASSISTANT_NAME}. "
        "Gestiona nodos, alias de voz y sincronización digital-física para movimiento "
        "del usuario por las diferentes zonas de su hogar."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# =============================================================
# Middleware CORS
# Permite que el frontend (HTML/JS) pueda hacer peticiones al backend
# cuando estan corriendo en puertas diferentes durante desarrollo. 
# Ej: frontend en localhost:3000 y backend en localhost:8000.
# =============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En produccion esto se DEBE restringir a dominios especificos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================
# Registrar Routers
# =============================================================

app.include_router(dev_router)
app.include_router(user_router)

# =============================================================
# Endpoint de salud
# =============================================================

@app.get(
    "/health",
    summary="Endpoint de salud",
    description="Verifica que la API esta corriendo correctamente.",
    tags=["System"]
)
async def health_check():
    """
    Verifica que el servidor esta corriendo correctamente.
    
    Returns:
        Diccionario con el estado del sistema y el nombre del asistente.
    """
    return {
        "status": "ok",
        "assistant": ASSISTANT_NAME,
        "message": "La API del sistema de navegacion esta funcionando correctamente."
    }

# =============================================================
# Punto de entrada
# =============================================================

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )

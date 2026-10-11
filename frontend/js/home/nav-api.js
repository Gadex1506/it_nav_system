/**
    * Capa de datos del panel web: unica responsabilidad es comunicarse
    * con el backend FastAPI por HTTP. No conoce el DOM ni la interfaz,
    * solo expone funciones simples que devuelven datos o lanzan errores.
    *
    * Patron de disenio aplicado:
    *   - Facade: Cada funcion oculta los detalles de fetch() (headers,
    *     metodo HTTP, parseo de respuesta) y expone una operacion simple
    *     y de alto nivel (ej. "renombrar nodo") hacia home.js.
*/

// --- Configuracion base ----------------------------------------------
// Si el backend corre en otra IP/puerto (ej, una Raspberry Pi en
// red local), este es unico valor que hay que cambiar.
const API_BASE_URL = "http://127.0.0.1:8001";


/**
    * Funcion interna que centraliza el manejo de errores de todas
    * las llamadas HTTP del archivo. No se exporta, solo la usan
    * las funciones publicas de aqui abajo.
    *
    * Si la respuesta HTTP no fue exitosa (status fuera del rango
    * 200-299), extrae el mensaje de error que envia FastAPI en el
    * campo "detail" y lo lanza como un Error de JavaScript normal.
    *
    * @param {Response} response - Objeto Response de fetch().
    * @returns {Promise<any>} El cuerpo de la respuesta ya parseado como JSON.
    * @throws {Error} Con el mensaje de "detail" si la respuesta fallo.
*/
async function handleResponse(response) {
    if (!response.ok) {
        
        let errorMessage = `Error inesperado (codigo ${response.status}).`;

        try {
            const errorBody = await response.json();

            if (errorBody.detail) {
                errorMessage = errorBody.detail;
            }
        } catch {
            // Si el cuerpo del error no es un JSON valido, nos quedamos
            // con el mensaje generico definido arriba.
        }

        throw new Error(errorMessage);
    }

    // Algunas respuestas (poco comunes aqui) podrian no traer cuerpo.
    // Nos protegemos de ese caso antes de intentar parsear JSON.
    const contentLength = response.headers.get("content-length");

    if (contentLength === "0") {
        return null;
    }

    return response.json();
}


/**
    * Obtiene todos los nodos activos de la casa configurada.
    *
    * Endpoint: GET /user/nodes
    *
    * @returns {Promise<Array>} Lista de nodos con sus alias.
*/
async function fetchNodes() {
    const response = await fetch(`${API_BASE_URL}/user/nodes`);
    return handleResponse(response);
}


/**
    * Obtiene el detalle completo de un nodo especifico.
    *
    * Endpoint: GET /user/nodes/{node_id}
    *
    * @param {number} nodeId - ID del nodo a consultar.
    * @returns {Promise<Object>} Datos completos del nodo, incluyendo alias.
*/
async function fetchNodeById(nodeId) {
    const response = await fetch(`${API_BASE_URL}/user/nodes/${nodeId}`);
    return handleResponse(response);
}


/**
    * Actualiza el nombre visible (display_name) de un nodo.
    *
    * Endpoint: PATCH /user/nodes/{node_id}/display-name
    *
    * @param {number} nodeId - ID del nodo a renombrar.
    * @param {string} newDisplayName - Nuevo nombre visible.
    * @returns {Promise<Object>} El nodo actualizado.
*/
async function renameNode(nodeId, newDisplayName) {
    const response = await fetch(`${API_BASE_URL}/user/nodes/${nodeId}/display-name`,
        {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ display_name: newDisplayName }),
        }
    );
    return handleResponse(response);
}


/**
    * Agrega un alias de voz a un nodo.
    *
    * Endpoint: POST /user/nodes/{node_id}/aliases
    *
    * @param {number} nodeId - ID del nodo al que se agrega el alias.
    * @param {string} alias - Texto del alias de voz.
    * @returns {Promise<Object>} El alias creado.
*/
async function addAliasToNode(nodeId, alias) {
    const response = await fetch(`${API_BASE_URL}/user/nodes/${nodeId}/aliases`,
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ alias: alias }),
        }
    );
    return handleResponse(response);
}


/**
    * Elimina un alias de voz especifico de un nodo.
    *
    * Endpoint: DELETE /user/nodes/{node_id}/aliases/{alias_id}
    *
    * @param {number} nodeId - ID del nodo propietario del alias.
    * @param {number} aliasId - ID del alias a eliminar.
    * @returns {Promise<Object>} Mensaje de confirmación del backend.
*/
async function deleteAliasFromNode(nodeId, aliasId) {
    const response = await fetch(`${API_BASE_URL}/user/nodes/${nodeId}/aliases/${aliasId}`,
        {
            method: "DELETE"
        }
    );
    return handleResponse(response);
}
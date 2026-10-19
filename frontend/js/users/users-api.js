/**
 * users-api.js
 * -----------------------------------------------------------------------------
 * Capa de datos de la pestana Usuarios: habla con el servicio de
 * reconocimiento facial (servidor HTTP embebido en la app Unity, puerto 8002).
 *
 * Capa: Presentacion -> acceso a datos (igual que nav-api.js).
 * Patrones:
 *   - Facade: 4 funciones simples ocultan fetch, cabeceras y manejo de errores.
 *   - Adapter: traduce el JSON del servicio (nombre, es_administrador,
 *     fecha_registro) al objeto interno en ingles { id, name, isAdmin,
 *     registeredAt }. Si el servicio cambia sus campos, solo se toca aqui.
 * Analogia: el traductor de la embajada; el resto del panel nunca habla el
 * idioma del otro servicio.
 *
 * Seguridad: la clave X-Api-Key NO va escrita en el codigo. La persona la
 * pega una vez en el panel (esta en admin_api_key.txt, junto a la app Unity)
 * y se guarda solo en el navegador de esa maquina.
 *
 * Nota: la creacion de usuarios (POST /users) NO existe y no se implementa.
 */

const USERS_API_BASE_URL = "http://localhost:8002";

/** Tipos de error para que la interfaz decida que mostrar. */
const UsersApiErrorKind = Object.freeze({
	MISSING_KEY: "missing-key",
	CONNECTION: "connection",
	UNAUTHORIZED: "unauthorized",
	FORBIDDEN: "forbidden",
	NOT_FOUND: "not-found",
	BAD_REQUEST: "bad-request",
	UNKNOWN: "unknown",
});

class UsersApiError extends Error {
	/**
	 * @param {string} message texto listo para mostrar
	 * @param {string} kind uno de UsersApiErrorKind
	 * @param {number|null} status codigo HTTP (null si no hubo respuesta)
	 */
	constructor(message, kind, status = null) {
		super(message);
		this.name = "UsersApiError";
		this.kind = kind;
		this.status = status;
	}
}

/** Guarda la clave en el navegador (si el almacenamiento no esta disponible, solo en memoria). */
const UsersApiKeyStore = (() => {
	const STORAGE_KEY = "inclusiveTech.usersApiKey";
	let memoryKey = "";

	function get() {
		try {
			return localStorage.getItem(STORAGE_KEY) || memoryKey;
		} catch (e) {
			return memoryKey;
		}
	}

	function set(value) {
		memoryKey = value;
		try {
			localStorage.setItem(STORAGE_KEY, value);
		} catch (e) { /* sin almacenamiento: queda en memoria */ }
	}

	function clear() {
		memoryKey = "";
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch (e) { /* nada que borrar */ }
	}
	return Object.freeze({get,
		set,
		clear
	});
})();

/**
 * Si la URL trae "#key=LACLAVE" (la abre el boton del menu de Unity), guarda la
 * clave y limpia la URL para que no quede visible ni en el historial.
 * Todo lo que va despues del "#" nunca se envia a ningun servidor.
 */
function consumeKeyFromUrl() {
	const match = window.location.hash.match(/(?:^#|&)key=([^&]+)/);
	if (!match) return;
	try {
		UsersApiKeyStore.set(decodeURIComponent(match[1]));
	} catch (e) { /* clave mal codificada: se ignora */ }
	history.replaceState(null, "", window.location.pathname + window.location.search);
}
consumeKeyFromUrl();

// --- Mensajes para la persona usuaria ------------------------------------------
const USERS_API_MESSAGES = Object.freeze({
	missingKey: "Falta la clave de acceso del sistema de reconocimiento facial.",
	connection: "No se pudo conectar al sistema de reconocimiento facial. Verifica que la app de Unity esté abierta.",
	unauthorized: "La clave de acceso no es correcta.",
	forbidden: "El sistema de reconocimiento rechazó el origen del panel. Abre el panel desde http://localhost (por ejemplo con: python -m http.server 5500 dentro de la carpeta frontend) y no desde un archivo.",
	notFound: "No se encontró el usuario. Quizás ya fue eliminado.",
	generic: "El sistema de reconocimiento respondió con un error.",
});

/** Convierte el JSON del servicio al objeto interno del panel. */
function mapUserFromApi(raw) {
	return {
		id: raw.id,
		name: String(raw.nombre || ""),
		isAdmin: Boolean(raw.es_administrador),
		registeredAt: parseApiDate(raw.fecha_registro),
	};
}

/** El servicio manda 7 decimales ("...57.1963615Z"); se recortan a 3 para que todos los navegadores lo entiendan. */
function parseApiDate(text) {
	if (!text) return null;
	const date = new Date(String(text).replace(/(\.\d{3})\d+/, "$1"));
	return Number.isNaN(date.getTime()) ? null : date;
}

/** Lee el JSON de la respuesta sin romperse si el cuerpo viene vacio o no es JSON. */
async function readJsonSafely(response) {
	try {
		return await response.json();
	} catch (e) {
		return null;
	}
}

/**
 * Peticion generica al servicio. Lanza UsersApiError en cualquier fallo.
 * @returns {Promise<any|null>} JSON de la respuesta, o null en 204
 */
async function usersRequest(path, {
	method = "GET",
	body = null
} = {}) {
	const apiKey = UsersApiKeyStore.get();
	if (!apiKey) throw new UsersApiError(USERS_API_MESSAGES.missingKey, UsersApiErrorKind.MISSING_KEY);

	const headers = {
		"X-Api-Key": apiKey
	};
	if (body !== null) headers["Content-Type"] = "application/json";

	let response;
	try {
		response = await fetch(`${USERS_API_BASE_URL}${path}`, {
			method,
			headers,
			body: body !== null ? JSON.stringify(body) : undefined,
		});
	} catch (networkError) {
		// Conexion rechazada: la app Unity no esta corriendo (no hay "detail").
		throw new UsersApiError(USERS_API_MESSAGES.connection, UsersApiErrorKind.CONNECTION);
	}

	if (response.status === 204) return null;
	const data = await readJsonSafely(response);
	if (response.ok) return data;

	const detail = data && typeof data.detail === "string" ? data.detail : null;
	if (response.status === 401) throw new UsersApiError(USERS_API_MESSAGES.unauthorized, UsersApiErrorKind.UNAUTHORIZED, 401);
	if (response.status === 403) throw new UsersApiError(USERS_API_MESSAGES.forbidden, UsersApiErrorKind.FORBIDDEN, 403);
	if (response.status === 404) throw new UsersApiError(detail || USERS_API_MESSAGES.notFound, UsersApiErrorKind.NOT_FOUND, 404);
	if (response.status === 400) throw new UsersApiError(detail || USERS_API_MESSAGES.generic, UsersApiErrorKind.BAD_REQUEST, 400);
	throw new UsersApiError(detail || USERS_API_MESSAGES.generic, UsersApiErrorKind.UNKNOWN, response.status);
}

// --- API publica (equivale a listarUsuarios, obtenerUsuario, actualizarNombre, eliminarUsuario) ---

/** GET /users -> lista de usuarios. */
async function fetchUsers() {
	const data = await usersRequest("/users");
	return Array.isArray(data) ? data.map(mapUserFromApi) : [];
}

/** GET /users/{id} -> un usuario. */
async function fetchUserById(userId) {
	return mapUserFromApi(await usersRequest(`/users/${encodeURIComponent(userId)}`));
}

/** PATCH /users/{id} -> usuario con el nombre corregido. */
async function updateUserName(userId, name) {
	return mapUserFromApi(await usersRequest(`/users/${encodeURIComponent(userId)}`, {
		method: "PATCH",
		body: {
			nombre: name
		},
	}));
}

/** DELETE /users/{id} -> elimina al usuario y su rostro (definitivo). */
async function deleteUser(userId) {
	await usersRequest(`/users/${encodeURIComponent(userId)}`, {
		method: "DELETE"
	});
}
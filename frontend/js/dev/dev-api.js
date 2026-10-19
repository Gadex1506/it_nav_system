/**
	* Cliente HTTP del panel de desarrollo (endpoints /dev/* del backend de
	* navegacion) y almacenamiento de la clave de desarrollador.
	*
	* Capa: Infraestructura del frontend.
	* Patron: Adapter (traduce fetch/HTTP a funciones y errores del panel).
	* Analogia: el mensajero que lleva la llave en el bolsillo y avisa si la
	* puerta no abre.
*/
const DevApi = (() => {
	"use strict";

	const SERVICE_URL_FALLBACK = "http://localhost:8001";
	const KEY_HEADER = "X-Dev-Key";
	const KEY_STORAGE_NAME = "inclusive_tech_dev_key";
	const HTTP_UNAUTHORIZED = 401;

	// Si el panel lo sirve el propio backend, se usa su mismo origen
	const baseUrl = location.protocol.startsWith("http") ? location.origin : SERVICE_URL_FALLBACK;

	/** Error con tipo para que la pantalla decida que mensaje mostrar. */
	class DevApiError extends Error {
		constructor(kind, message, status = 0) {
			super(message);
			this.kind = kind; // "network" | "unauthorized" | "server"
			this.status = status;
		}
	}

	// ----- Clave (solo en sessionStorage: se borra al cerrar la pestana) -----
	const KeyStore = {
		get() {
			try {
				return sessionStorage.getItem(KEY_STORAGE_NAME) || "";
			} catch (e) {
				return "";
			}
		},
		set(value) {
			try {
				sessionStorage.setItem(KEY_STORAGE_NAME, value);
			} catch (e) { /* sin almacenamiento */ }
		},
		clear() {
			try {
				sessionStorage.removeItem(KEY_STORAGE_NAME);
			} catch (e) { /* sin almacenamiento */ }
		},
	};

	/** Hace la peticion y traduce los fallos a DevApiError. */
	async function request(method, path, {
		body = null,
		key = KeyStore.get()
	} = {}) {
		const headers = {
			[KEY_HEADER]: key
		};
		if (body) headers["Content-Type"] = "application/json";

		let response;
		try {
			response = await fetch(baseUrl + path, {
				method,
				headers,
				body: body ? JSON.stringify(body) : null
			});
		} catch (error) {
			throw new DevApiError("network", "No se pudo conectar con el backend de navegacion (puerto 8001).");
		}

		if (response.status === HTTP_UNAUTHORIZED) {
			throw new DevApiError("unauthorized", "Clave de desarrollador incorrecta.", response.status);
		}
		if (!response.ok) {
			let detail = `Error del servidor (${response.status}).`;
			try {
				const data = await response.json();
				if (typeof data.detail === "string") detail = data.detail;
				else if (Array.isArray(data.detail)) detail = data.detail.map((item) => item.msg).join(" ");
			} catch (e) { /* sin JSON */ }
			throw new DevApiError("server", detail, response.status);
		}
		return response.json();
	}

	return Object.freeze({
		DevApiError,
		KeyStore,
		fetchOverview: (key) => request("GET", "/dev/houses/overview", {
			key
		}),
		createHouse: (name, description) => request("POST", "/dev/houses", {
			body: {
				name,
				description: description || null
			}
		}),
		deleteHouse: (id, confirmName) => request("DELETE", `/dev/houses/${id}?confirm_name=${encodeURIComponent(confirmName)}`),
		// Habitaciones (nodos) de la casa activa: endpoint del panel de usuario
		fetchRooms: () => request("GET", "/user/nodes"),
		fetchDevices: (houseId) => request("GET", `/dev/devices?house_id=${houseId}`),
		createDevice: (payload) => request("POST", "/dev/devices", {
			body: payload
		}),
		renameDevice: (id, displayName) => request("PATCH", `/dev/devices/${id}/display-name`, {
			body: {
				display_name: displayName
			}
		}),
		deleteDevice: (id) => request("DELETE", `/dev/devices/${id}`),
	});
})();
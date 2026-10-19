/**
    * Pestania "Dispositivos" del panel de desarrollo: Registrar, listar, renombrar
    * y eliminar luces y puertas de la casa activa, sin usar Swagger.
    *
    * Capa de Presentacion: Solo habla con el backend a traves de DevApi.
    * Analogia: Es el libro de inventario de la casa; cada habitacion anota sus
    * interruptores y puertas con una etiqueta fija (la clave) que despues usara
    * el ESP32 para reconocerlos.
    *
    * Reglas que respeta:
    *  - La clave (device_key) es fija: solo minusculas, numeros y guion bajo.
    *  - Para no teclear, se sugiere clave y nombre segun habitacion y tipo; si la
    *    persona escribe algo propio, la sugerencia deja de pisarlo.
    *  - Los dispositivos cuelgan de cualquier nodo de la casa activa.
*/
const DevicesTab = (() => {
	"use strict";

	const TYPE_LABELS = Object.freeze({
		light: "Luz",
		door: "Puerta"
	});
	const KEY_MAX_LENGTH = 50;
	const KEY_SUFFIX_RESERVED = 4; // espacio para "_2", "_10", etc.

	const $ = (id) => document.getElementById(id);
	const view = $("devicesView"),
		notice = $("devicesNotice");
	const form = $("devForm"),
		roomSelect = $("devRoom"),
		typeSelect = $("devType");
	const keyInput = $("devKey"),
		nameInput = $("devName");
	const body = $("devicesBody"),
		emptyMessage = $("devicesEmpty"),
		table = $("devicesTable");
	const renameDialog = $("renameDialog"),
		renameForm = $("renameForm");
	const renameMessage = $("renameMessage"),
		renameInput = $("renameInput"),
		renameCancel = $("renameCancel");
	const deleteDialog = $("deviceDeleteDialog"),
		deleteForm = $("deviceDeleteForm");
	const deleteMessage = $("deviceDeleteMessage"),
		deleteCancel = $("deviceDeleteCancel");

	let rooms = []; // nodos de la casa activa
	let devices = []; // dispositivos de la casa activa
	let keyTouched = false; // la persona escribio su propia clave
	let nameTouched = false; // la persona escribio su propio nombre
	let pendingRename = null;
	let pendingDelete = null;

	// ----- Utilidades -----

	/** Convierte un texto en una clave valida sin tildes, minusculas y guion bajo */
	function slugify(text) {
		return text.normalize("NFD").replace(/[̀-ͯ]/g, "")
			.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
	}

	/** Busca un nodo por id (o undefined) */
	function roomById(id) {
		return rooms.find((room) => room.id === Number(id));
	}

	/** Devuelve una clave que no choque con las existentes (agrega _2, _3...) */
	function uniqueKey(baseKey) {
		const base = baseKey.slice(0, KEY_MAX_LENGTH - KEY_SUFFIX_RESERVED);
		let key = base,
			counter = 2;
		while (devices.some((device) => device.device_key === key)) key = `${base}_${counter++}`;
		return key;
	}

	/** Rellena clave y nombre sugeridos, salvo lo que la persona ya escribio */
	function applySuggestions() {
		const room = roomById(roomSelect.value);
		if (!room) return;
		const type = typeSelect.value;
		if (!keyTouched) keyInput.value = uniqueKey(`${type}_${slugify(room.internal_name)}`);
		if (!nameTouched) nameInput.value = `${TYPE_LABELS[type]} de ${room.display_name}`;
	}

	/** Activa o desactiva todo el formulario */
	function setFormEnabled(enabled) {
		Array.from(form.elements).forEach((element) => {
			element.disabled = !enabled;
		});
	}

	/** Muestra un aviso arriba de la pestania (o lo oculta con texto vacio) */
	function setNotice(text) {
		notice.textContent = text;
		notice.hidden = !text;
	}

	/** Traduce un error de la API a un aviso visible */
	function reportError(error) {
		if (error.kind === "unauthorized") {
			DevApi.KeyStore.clear();
			location.reload(); // vuelve a pedir la clave
			return;
		}
		// Errores de formulario (clave repetida, datos invalidos). Es un aviso corto
		if (error.kind === "server") {
			Toast.show(error.message);
			return;
		}
		Banner.show(error.message, load);
	}

	// ----- Dibujo -----

	/** Llena el selector de habitaciones conservando la seleccion si se puede. */
	function renderRooms() {
		const previous = roomSelect.value;
		roomSelect.replaceChildren();
		rooms.forEach((room) => {
			const option = document.createElement("option");
			option.value = String(room.id);
			option.textContent = `${room.display_name} (${room.internal_name})`;
			roomSelect.append(option);
		});
		if (rooms.some((room) => String(room.id) === previous)) roomSelect.value = previous;
	}

	/** Crea una celda de texto simple */
	function textCell(text) {
		const cell = document.createElement("td");
		cell.textContent = text;
		return cell;
	}

	/** Crea un boton pequenio de accion de fila */
	function actionButton(label, extraClass, onClick) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = `dev-btn dev-btn--small ${extraClass}`.trim();
		button.textContent = label;
		button.addEventListener("click", onClick);
		return button;
	}

	/** Dibuja la tabla de dispositivos ordenada por habitacion y tipo */
	function renderDevices() {
		body.replaceChildren();
		emptyMessage.hidden = devices.length > 0;
		table.hidden = devices.length === 0;

		const roomName = (device) => (roomById(device.node_id) || {}).display_name || `Nodo #${device.node_id}`;
		const sorted = [...devices].sort((a, b) =>
			roomName(a).localeCompare(roomName(b), "es") || a.device_type.localeCompare(b.device_type));

		sorted.forEach((device) => {
			const row = document.createElement("tr");
			row.append(textCell(roomName(device)), textCell(TYPE_LABELS[device.device_type] || device.device_type));

			const keyCell = document.createElement("td");
			const code = document.createElement("code");
			code.textContent = device.device_key;
			keyCell.append(code);

			const actions = document.createElement("td");
			const group = document.createElement("div");
			group.className = "dev-row";
			group.append(
				actionButton("Renombrar", "dev-btn--ghost", () => openRename(device)),
				actionButton("Eliminar", "dev-btn--danger", () => openDelete(device)),
			);
			actions.append(group);

			row.append(keyCell, textCell(device.display_name), actions);
			body.append(row);
		});
	}

	// ----- Carga de datos -----

	/** Carga casa activa, habitaciones y dispositivos, y dibuja todo */
	async function load() {
		try {
			Banner.hide();
			const overview = await DevApi.fetchOverview();

			if (overview.active_house_id === null) {
				rooms = [];
				devices = [];
				renderRooms();
				renderDevices();
				setFormEnabled(false);
				setNotice("No hay ninguna casa registrada. Crea una en la pestaña Casas.");
				return;
			}

			[rooms, devices] = await Promise.all([DevApi.fetchRooms(), DevApi.fetchDevices(overview.active_house_id)]);
			renderRooms();
			renderDevices();

			if (rooms.length === 0) {
				setFormEnabled(false);
				setNotice("La casa activa aún no tiene nodos. Registra las habitaciones desde Unity y vuelve aquí.");
				return;
			}

			setNotice("");
			setFormEnabled(true);
			applySuggestions();
		} catch (error) {
			reportError(error);
		}
	}

	// ----- Acciones -----
	function openRename(device) {
		pendingRename = device;
		renameMessage.textContent = `Clave: ${device.device_key} (no cambia).`;
		renameInput.value = device.display_name;
		renameDialog.showModal();
		renameInput.select();
	}

	function openDelete(device) {
		pendingDelete = device;
		deleteMessage.textContent =
			`Se eliminará "${device.display_name}" (${device.device_key}). Si ya está cargado en un ESP32, dejará de responder al sistema.`;
		deleteDialog.showModal();
	}

	// ----- Eventos -----
	roomSelect.addEventListener("change", applySuggestions);
	typeSelect.addEventListener("change", applySuggestions);
	keyInput.addEventListener("input", () => {
		keyTouched = true;
	});
	nameInput.addEventListener("input", () => {
		nameTouched = true;
	});

	form.addEventListener("submit", async(event) => {
		event.preventDefault();
		try {
			await DevApi.createDevice({
				node_id: Number(roomSelect.value),
				device_type: typeSelect.value,
				device_key: keyInput.value.trim(),
				display_name: nameInput.value.trim(),
			});
			keyTouched = false;
			nameTouched = false;
			Toast.show("Dispositivo registrado.");
			await load();
		} catch (error) {
			reportError(error);
		}
	});

	renameCancel.addEventListener("click", () => renameDialog.close());
	renameForm.addEventListener("submit", async(event) => {
		event.preventDefault();
		if (!pendingRename) return;
		try {
			await DevApi.renameDevice(pendingRename.id, renameInput.value.trim());
			renameDialog.close();
			Toast.show("Nombre actualizado.");
			await load();
		} catch (error) {
			renameDialog.close();
			reportError(error);
		}
	});

	deleteCancel.addEventListener("click", () => deleteDialog.close());
	deleteForm.addEventListener("submit", async(event) => {
		event.preventDefault();
		if (!pendingDelete) return;
		try {
			await DevApi.deleteDevice(pendingDelete.id);
			deleteDialog.close();
			Toast.show("Dispositivo eliminado.");
			await load();
		} catch (error) {
			deleteDialog.close();
			reportError(error);
		}
	});

	/** Se llama cada vez que se abre la pestania */
	function onShow() {
		if (DevApi.KeyStore.get()) load();
	}

	return Object.freeze({
		onShow
	});
})();
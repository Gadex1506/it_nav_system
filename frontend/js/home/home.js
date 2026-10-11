/**
	* Controlador de la pestana "Hogar". Conecta tres elementos:
	*   - nav-api.js      -> se comunica con el backend (capa de datos, fachada)
	*   - PlanRenderer    -> dibuja el plano (vista)
	*   - Viewport/Connector -> camara y conector decorativo
	*
	* Capa: Presentacion (controlador / mediador). Gestiona el estado de la interfaz de usuario
	* y es el unico archivo que conoce tanto el backend como la vista.
	*  
	* Analogia: El que maneja la escena - Le dice a los actores (renderer) que mostrar y
	* recurre al almacen (nav-api.js) cuando es necesario guardar algo. 
	*
	* Vinculacion zona <-> nodo: Cada zona del plano enumera los nombres tecnicos que acepta
	* (PlanData.ZONES[].internalNames). El primer nodo de tipo ROOM del backend cuyo
	* "internal_name" normalizado coincida se vincula a la zona. Las zonas sin nodo
	* asociado se muestran como "SIN REGISTRAR" y son de solo lectura. 
	*
	* Las luces no se gestionan aqui deliberadamente: el backend no dispone de
	* endpoints para luces.
*/
(() => {
	"use strict";

	// --- Constantes -------------------------------------------
	const MAX_ALIASES = 5; // Debe coincidir con la regla del backend
	const MAX_NAME_LENGTH = 40;
	const SAVED_MESSAGE_MS = 2400;
	const NOTE_MS = 7000;
	const MAX_SUGGESTIONS = 5;
	const SUGGESTION_BLUR_DELAY_MS = 150;
	const SMALL_SCREEN_QUERY = "(max-width: 1100px)";
	const NODE_TYPE_ROOM = "room";

	const $ = (id) => document.getElementById(id);

	// --- Estados -----------------------------------------------------------------------
	/** zoneId -> { definition, node|null, isRenaming } */
	const zones = new Map();
	let selectedId = null;
	let allNodes = [];

	// --- Referencias DOM -----------------------------------------------------------
	const dom = {
		stage: $("stage"),
		area: $("area"),
		view: $("view"),
		plan: $("plan"),
		ficha: $("ficha"),
		fichaAnchor: $("fichaAnchor"),
		fichaNumber: $("fichaNumber"),
		fichaEditable: $("fichaEditable"),
		fichaMissing: $("fichaMissing"),
		nameInput: $("nameInput"),
		nameError: $("nameError"),
		chips: $("chips"),
		aliasCount: $("aliasCount"),
		aliasError: $("aliasError"),
		techName: $("techName"),
		missingText: $("missingText"),
		missingCode: $("missingCode"),
	};

	// ============================================================================
	// Pequenias utilidades de normalizacion y busqueda
	// ============================================================================

	/** "Baño " -> "BANO": Eliminar acentos, quitar caracteres no alfanumericos, convertir a mayusculas */
	function normalizeTechnicalName(value) {
		return String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "")
			.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
	}

	/** Texto en minusculas y sin acentos para busquedas. */
	function normalizeSearch(value) {
		return String(value || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
			.replace(/[“”"']/g, "").trim();
	}

	const errorText = (error) => (error && error.message) ? error.message : "Error desconocido";
	const zoneList = () => PlanData.ZONES.map((d) => zones.get(d.id));
	const isRegistered = (zone) => zone.node !== null;
	const displayNameOf = (zone) => (zone.node ? zone.node.display_name : zone.definition.defaultName);
	const aliasesOf = (zone) => (zone.node ? zone.node.aliases : []);

	// ============================================================================
	// Widgets de comentarios: sello de guardado, notificacion emergente (toast), banner de modo sin conexion
	// ============================================================================

	const SaveIndicator = (() => {
		const stamp = $("stamp");
		const text = $("stampText");
		const icon = $("stampIcon");
		let timer = null;

		function pop() {
			stamp.classList.remove("is-pop");
			void stamp.offsetWidth;
			stamp.classList.add("is-pop");
		}

		function set(state, message, glyph) {
			clearTimeout(timer);
			stamp.classList.toggle("is-saving", state === "saving");
			stamp.classList.toggle("is-failed", state === "failed");
			text.textContent = message;
			icon.textContent = glyph;
			if (state !== "saving") pop();
		}
		return {
			saving() {
				set("saving", "Guardando…", "…");
			},
			saved() {
				set("saved", "Cambios guardados", "✓");
				timer = setTimeout(() => set("idle", "Sin cambios pendientes", "✓"), SAVED_MESSAGE_MS);
			},
			failed() {
				set("failed", "No se pudo guardar", "!");
			},
		};
	})();

	// ============================================================================
	// Datos: carga y vinculacion de nodos de backend a zonas de planificacion.
	// ============================================================================

	/** Asocia el primer nodo de sala coincidente a cada zona (cada nodo se utiliza una sola vez) */
	function assignNodesToZones(nodes) {
		const used = new Set();
		zones.forEach((zone) => {
			const match = nodes.find((n) =>
				n.node_type === NODE_TYPE_ROOM && !used.has(n.id) &&
				zone.definition.internalNames.includes(normalizeTechnicalName(n.internal_name)));
			zone.node = match || null;
			if (match) used.add(match.id);
		});
	}

	/** Redibuja la etiqueta de una zona a partir de su estado actual */
	function renderZone(zone) {
		PlanRenderer.updateZone(zone.definition.id, {
			name: displayNameOf(zone),
			alias: aliasesOf(zone)[0] ? aliasesOf(zone)[0].alias : "",
			registered: isRegistered(zone),
			active: selectedId === zone.definition.id,
		});
	}

	const renderAllZones = () => zoneList().forEach(renderZone);

	async function loadNodes() {
		try {
			allNodes = await fetchNodes();
			assignNodesToZones(allNodes);
			Banner.hide();
		} catch (error) {
			Banner.show(`No se pudo conectar con el servicio de navegación. ${errorText(error)}`, loadNodes);
		}
		renderAllZones();
		if (selectedId) renderFicha();
	}

	/** Vuelve a leer un nodo del backend (la fuente de verdad tras un cambio) */
	async function refreshNode(zone) {
		zone.node = await fetchNodeById(zone.node.id);
		renderZone(zone);
	}

	// ============================================================================
	// Seleccion + ficha
	// ============================================================================

	function stageAnchorPoint() {
		if (!selectedId || window.matchMedia(SMALL_SCREEN_QUERY).matches) return null;
		const def = zones.get(selectedId).definition;
		return Viewport.toStagePoint(def.connectorAnchor, dom.stage);
	}

	function ficheEndPoint() {
		const s = dom.stage.getBoundingClientRect();
		const f = dom.fichaAnchor.getBoundingClientRect();
		return {
			x: f.left + f.width / 2 - s.left,
			y: f.top + f.height / 2 - s.top
		};
	}

	function selectZone(id) {
		selectedId = id;
		dom.stage.classList.toggle("has-picked", Boolean(id));
		PlanRenderer.setSelection(id);
		renderAllZones();
		if (id) {
			renderFicha();
			dom.ficha.classList.remove("is-visible");
			void dom.ficha.offsetWidth;
			dom.ficha.classList.add("is-visible");
		} else {
			dom.ficha.classList.remove("is-visible");
		}
		Connector.update();
		Connector.replay();
		Connector.follow();
		if (id && window.matchMedia(SMALL_SCREEN_QUERY).matches) {
			dom.ficha.scrollIntoView({
				behavior: "smooth",
				block: "nearest"
			}); // disenio apilado: mostrar la tarjeta
		}
	}

	function renderFicha() {
		const zone = zones.get(selectedId);
		if (!zone) return;
		const index = PlanData.ZONES.indexOf(zone.definition);
		dom.fichaNumber.textContent = PlanData.formatZoneNumber(index);
		const registered = isRegistered(zone);
		dom.fichaEditable.hidden = !registered;
		dom.fichaMissing.hidden = registered;
		clearErrors();
		if (registered) {
			dom.nameInput.value = zone.node.display_name;
			dom.techName.textContent = zone.node.internal_name;
			renderChips();
		} else {
			dom.missingText.textContent = `La zona “${zone.definition.defaultName}” aún no existe en el backend, por eso no se puede editar.`;
			dom.missingCode.textContent = zone.definition.internalNames[0];
		}
	}

	function clearErrors() {
		dom.nameError.hidden = true;
		dom.aliasError.hidden = true;
	}

	function showError(target, message) {
		target.textContent = message;
		target.hidden = false;
	}

	// ============================================================================
	// Renombrar zona
	// ============================================================================

	async function commitRename() {
		const zone = zones.get(selectedId);
		if (!zone || !isRegistered(zone) || zone.isRenaming) return;
		const value = dom.nameInput.value.trim();
		if (value === zone.node.display_name) {
			dom.nameError.hidden = true;
			return;
		}
		if (!value) {
			showError(dom.nameError, "El nombre no puede estar vacío.");
			dom.nameInput.value = zone.node.display_name;
			return;
		}
		zone.isRenaming = true;
		SaveIndicator.saving();
		try {
			await renameNode(zone.node.id, value);
			await refreshNode(zone);
			dom.nameError.hidden = true;
			SaveIndicator.saved();
		} catch (error) {
			SaveIndicator.failed();
			showError(dom.nameError, errorText(error));
			dom.nameInput.value = zone.node.display_name;
		} finally {
			zone.isRenaming = false;
			if (zones.get(selectedId) === zone) dom.nameInput.value = zone.node.display_name;
		}
	}

	// ============================================================================
	// Alias de nodos (habitaciones de una casa)
	// ============================================================================

	function makeButton(text, label, className, onClick) {
		const b = document.createElement("button");
		b.type = "button";
		b.textContent = text;
		b.setAttribute("aria-label", label);
		if (className) b.className = className;
		b.addEventListener("click", onClick);
		return b;
	}

	function renderChips(focusAddButton) {
		const zone = zones.get(selectedId);
		dom.chips.innerHTML = "";
		const aliases = aliasesOf(zone);
		aliases.forEach((alias) => {
			const li = document.createElement("li");
			li.className = "chip";
			const label = document.createElement("span");
			label.textContent = `“${alias.alias}”`;
			li.append(label, makeButton("×", `Eliminar alias ${alias.alias}`, "", () => removeAlias(zone, alias)));
			dom.chips.append(li);
		});
		dom.aliasCount.textContent = `${aliases.length}/${MAX_ALIASES}`;
		if (aliases.length < MAX_ALIASES) {
			const li = document.createElement("li");
			const add = makeButton("+", "Agregar alias de voz", "add-chip", () => startAddAlias(zone));
			li.append(add);
			dom.chips.append(li);
			if (focusAddButton) add.focus();
		}
	}

	function startAddAlias(zone) {
		const addItem = dom.chips.lastChild;
		const li = document.createElement("li");
		li.className = "chip";
		const input = document.createElement("input");
		input.placeholder = "nuevo alias";
		input.maxLength = MAX_NAME_LENGTH;
		input.setAttribute("aria-label", "Nuevo alias de voz");
		li.append(input);
		dom.chips.insertBefore(li, addItem);
		addItem.remove();
		input.focus();

		let finished = false;
		const finish = (commit) => {
			if (finished) return;
			finished = true;
			const value = input.value.trim();
			if (commit && value) addAlias(zone, value);
			else if (zones.get(selectedId) === zone) renderChips(true);
		};
		input.addEventListener("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				finish(true);
			}
			if (e.key === "Escape") {
				e.stopPropagation();
				finish(false);
			}
		});
		input.addEventListener("blur", () => finish(true));
	}

	async function addAlias(zone, value) {
		SaveIndicator.saving();
		try {
			await addAliasToNode(zone.node.id, value);
			await refreshNode(zone);
			dom.aliasError.hidden = true;
			SaveIndicator.saved();
		} catch (error) {
			SaveIndicator.failed();
			showError(dom.aliasError, errorText(error));
		}
		if (zones.get(selectedId) === zone) renderChips(true);
	}

	async function removeAlias(zone, alias) {
		SaveIndicator.saving();
		try {
			await deleteAliasFromNode(zone.node.id, alias.id);
			await refreshNode(zone);
			dom.aliasError.hidden = true;
			SaveIndicator.saved();
		} catch (error) {
			SaveIndicator.failed();
			showError(dom.aliasError, errorText(error));
		}
		if (zones.get(selectedId) === zone) renderChips(true);
	}

	// ============================================================================
	// Buscar por nombre visible, nombre predeterminado o alias
	// ============================================================================

	const search = (() => {
		const form = $("searchForm");
		const input = $("searchInput");
		const list = $("suggestions");
		const note = $("searchNote");
		let noteTimer = null;

		function find(text) {
			const query = normalizeSearch(text);
			if (!query) return [];
			const hits = [];
			zoneList().forEach((zone) => {
				const candidates = [{
						text: displayNameOf(zone),
						isAlias: false
					},
					...aliasesOf(zone).map((a) => ({
						text: a.alias,
						isAlias: true
					}))
				];
				let best = null;
				candidates.forEach((c) => {
					const n = normalizeSearch(c.text);
					const score = n === query ? 3 :
						(n.startsWith(query) || n.split(/[\s/]+/).some((w) => w.startsWith(query))) ? 2 :
						n.includes(query) ? 1 : 0;
					if (score && (!best || score > best.score)) best = {
						zone,
						text: c.text,
						isAlias: c.isAlias,
						score
					};
				});
				if (best) hits.push(best);
			});
			return hits.sort((a, b) => b.score - a.score);
		}

		function showNote(message) {
			note.textContent = message;
			note.hidden = false;
			clearTimeout(noteTimer);
			noteTimer = setTimeout(() => {
				note.hidden = true;
			}, NOTE_MS);
		}

		function pick(hit, all) {
			const zone = hit.zone;
			const id = zone.definition.id;
			selectZone(id);
			PlanRenderer.ping(id);
			if (Viewport.isZoomed()) Viewport.focusOn(PlanRenderer.getZoneCenter(id));
			const others = all.filter((h) => h.zone !== zone).map((h) => displayNameOf(h.zone));
			let message = hit.isAlias && normalizeSearch(hit.text) !== normalizeSearch(displayNameOf(zone)) ?
				`El alias “${hit.text}” es la zona ${displayNameOf(zone)}` : `Zona encontrada: ${displayNameOf(zone)}`;
			if (others.length) message += ` · también coincide: ${others.join(", ")}`;
			showNote(message);
		}

		form.addEventListener("submit", (e) => {
			e.preventDefault();
			list.hidden = true;
			const text = input.value.trim();
			if (!text) return;
			const hits = find(text);
			if (hits.length) pick(hits[0], hits);
			else showNote(`No encontré una zona con “${text}”. Prueba con un nombre o un alias.`);
		});

		input.addEventListener("input", () => {
			note.hidden = true;
			const hits = find(input.value).slice(0, MAX_SUGGESTIONS);
			list.innerHTML = "";
			hits.forEach((hit) => {
				const li = document.createElement("li");
				const b = document.createElement("button");
				b.type = "button";
				b.textContent = displayNameOf(hit.zone) +
					(hit.isAlias && normalizeSearch(hit.text) !== normalizeSearch(displayNameOf(hit.zone)) ? ` · alias “${hit.text}”` : "");
				b.addEventListener("mousedown", (e) => e.preventDefault());
				b.addEventListener("click", () => {
					list.hidden = true;
					input.value = hit.text;
					pick(hit, hits);
				});
				li.append(b);
				list.append(li);
			});
			list.hidden = hits.length === 0;
		});
		input.addEventListener("blur", () => setTimeout(() => {
			list.hidden = true;
		}, SUGGESTION_BLUR_DELAY_MS));
	})();

	// ============================================================================
	// Enlaces e inicio
	// ============================================================================

	function wireEvents() {
		dom.nameInput.addEventListener("blur", commitRename);
		dom.nameInput.addEventListener("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				dom.nameInput.blur();
			}
			if (e.key === "Escape") {
				e.stopPropagation();
				const zone = zones.get(selectedId);
				if (zone && zone.node) dom.nameInput.value = zone.node.display_name;
				dom.nameInput.blur();
			}
		});
		$("fichaClose").addEventListener("click", () => selectZone(null));
		document.addEventListener("keydown", (e) => {
			if (e.key === "Escape" && selectedId && e.target.tagName !== "INPUT") selectZone(null);
		});

		$("zoomIn").addEventListener("click", Viewport.zoomIn);
		$("zoomOut").addEventListener("click", Viewport.zoomOut);
		$("zoomReset").addEventListener("click", Viewport.reset);
		$("toggleNames").addEventListener("click", (e) => {
			e.currentTarget.textContent = PlanRenderer.toggleNames() ? "Mostrar nombres" : "Ocultar nombres";
		});

	}

	function init() {
		PlanData.ZONES.forEach((def) => zones.set(def.id, {
			definition: def,
			node: null,
			isRenaming: false
		}));
		PlanRenderer.init({
			svg: dom.plan,
			onSelect: selectZone
		});
		Connector.init({
			overlay: $("overlay"),
			line: $("connectorLine"),
			mask: $("connectorMaskPath"),
			pinStart: $("pinStart"),
			pinEnd: $("pinEnd"),
			resolveStart: stageAnchorPoint,
			resolveEnd: () => (selectedId && !window.matchMedia(SMALL_SCREEN_QUERY).matches ? ficheEndPoint() : null),
			isInside: (p) => {
				const a = dom.area.getBoundingClientRect();
				const s = dom.stage.getBoundingClientRect();
				return p.x > a.left - s.left && p.x < a.right - s.left && p.y > a.top - s.top && p.y < a.bottom - s.top;
			},
		});
		Viewport.init({
			area: dom.area,
			view: dom.view,
			svg: dom.plan,
			zoomLabel: $("zoomLabel"),
			controls: $("bottom"),
			onChange: Connector.update,
			onBackgroundClick: () => {
				if (selectedId) selectZone(null);
			},
		});
		renderAllZones();
		wireEvents();
	}

	/** Lo llama Tabs cada vez que la pestana Hogar pasa a ser visible. */
	function onShow() {
		Viewport.layout(); // el area medida en 0 mientras estaba oculta
		loadNodes(); // refresca datos del backend
		if (selectedId) Connector.follow();
	}

	init();
	window.HomeTab = Object.freeze({
		onShow
	});
})();
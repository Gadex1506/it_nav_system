/**
	* Dibuja el plano de planta en el SVG y actualiza las etiquetas de las zonas y el estado de seleccion.
	*
	* Capa Presentacion (Vista): No sabe NADA sobre el backend. recibe
	* modelos de vista sin formato ({ nombre, alias, registrado, activo, numero }).
	* 
	* Patron Facade: Sobre la manipulacion del DOM de SVG.
	* 
	* Analogia: El delineante. Dibuja lo que le indican, nunca decide que es lo correcto.
*/
const PlanRenderer = (() => {
	"use strict";

	const SVG_NS = "http://www.w3.org/2000/svg";
	const LABEL_LINE_HEIGHT = 38;
	const LABEL_ALIAS_GAP = 6;
	const LABEL_SPLIT_MIN_LENGTH = 11;
	const NAME_MAX_CHARS_PER_LINE = 14;
	const ALIAS_MAX_CHARS = 14;
	const FILL_OFFSET = "translate(5 -4)";
	const OUTLINE_OFFSET = "translate(-5 5)";
	const INK_STAGGER_SECONDS = 0.05;
	const PING_DURATION_MS = 2600;
	const DOOR_BADGE_DEFAULT_WIDTH = 144;
	const PAPER_COLOR = "#f3ead8";
	const INK_COLOR = "#1b2a41";

	const DOOR_GLYPH = '<rect x="-10" y="-16" width="20" height="32" rx="3"/><circle cx="4" cy="1" r="2" fill="#f3ead8"/>';
	const WINDOW_GLYPH = '<rect x="-13" y="-13" width="26" height="26" rx="2"/><path d="M0-13V13M-13 0H13"/>';

	let svg = null;
	let layers = {};
	let zoneById = {};
	let order = [];

	/** Crea un elemento SVG con atributos (texto mediante textContent. Seguro frente a XSS) */
	function el(tag, attrs, parent, text) {
		const node = document.createElementNS(SVG_NS, tag);
		Object.keys(attrs || {}).forEach((k) => node.setAttribute(k, attrs[k]));
		if (text != null) node.textContent = text;
		if (parent) parent.appendChild(node);
		return node;
	}

	/** Indica que todas las figuras que se encuentren dentro de "group" se dibujen con tinta al cargarse la pagina */
	function inkIn(group, delay) {
		Array.from(group.querySelectorAll("*")).forEach((shape, i) => {
			shape.classList.add("ink");
			shape.setAttribute("pathLength", 1);
			shape.style.setProperty("--d", `${delay + i * INK_STAGGER_SECONDS}s`);
		});
	}

	function byZone(cls, id) {
		return svg.querySelector(`.${cls}[data-zone="${id}"]`);
	}

	function truncate(text, max) {
		return text.length > max ? `${text.slice(0, max - 1)}…` : text;
	}

	/** Divide un nombre largo en dos lineas por el espacio que hay aproximadamente en el centro */
	function splitName(name) {
		if (name.length <= LABEL_SPLIT_MIN_LENGTH || !name.includes(" ")) return [name];
		let best = 0;
		let bestDistance = Infinity;
		Array.from(name).forEach((ch, i) => {
			const distance = Math.abs(i - name.length / 2);
			if (ch === " " && distance < bestDistance) {
				best = i;
				bestDistance = distance;
			}
		});
		return [name.slice(0, best), name.slice(best + 1)];
	}

	// --- Dibujo estatico de las puertas y ventanas ---------------------------------------------------------

	function drawWalls() {
		PlanData.WALLS.forEach((wall, i) => {
			const p = el("path", {
				d: wall.d,
				"stroke-width": wall.width
			}, layers.walls);
			p.classList.add("ink");
			p.setAttribute("pathLength", 1);
			p.style.setProperty("--d", `${i * 0.4}s`);
		});
		// Las aberturas se borran de las paredes con un trazo del color del papel…
		[...PlanData.DOORS, ...PlanData.WINDOWS].forEach(([gap]) => {
			el("path", {
				d: gap,
				stroke: PAPER_COLOR,
				"stroke-width": PlanData.OPENING_MASK_WIDTH,
				"stroke-linecap": "butt",
			}, layers.walls);
		});
		// …y luego se dibujan los vidrios de las ventanas encima (las puertas solo conservan su icono).
		const doorGroup = el("g", {
			"stroke-width": PlanData.WINDOW_LINE_WIDTH
		}, layers.walls);
		PlanData.WINDOWS.forEach(([, panes]) => el("path", {
			d: panes
		}, doorGroup));
		inkIn(doorGroup, 1.2);

		el("path", {
			d: PlanData.KITCHEN_DINING_DIVIDER,
			class: "divider",
			fill: "none",
			"stroke-width": 4,
			"stroke-dasharray": "16 12",
			"stroke-linecap": "round",
			opacity: 0.5,
		}, layers.walls);
	}

	function drawBadges() {
		PlanData.DOOR_BADGES.forEach((b) => {
			const g = el("g", {
				transform: `translate(${b.x} ${b.y})`
			}, layers.doors);
			if (b.label) {
				const w = b.width || DOOR_BADGE_DEFAULT_WIDTH;
				el("rect", {
					x: -w / 2,
					y: -23,
					width: w,
					height: 46,
					rx: 23,
					fill: INK_COLOR,
					stroke: PAPER_COLOR,
					"stroke-width": 3
				}, g);
				const icon = el("g", {
					transform: `translate(${24 - w / 2} 0) scale(.8)`,
					fill: "none",
					stroke: PAPER_COLOR,
					"stroke-width": 3
				}, g);
				icon.innerHTML = DOOR_GLYPH; // codigo fijo, sin datos de usuario
				el("text", {
					class: "door-text",
					x: 48 - w / 2,
					y: 10
				}, g, b.label);
			} else {
				el("circle", {
					r: 27,
					fill: INK_COLOR,
					stroke: PAPER_COLOR,
					"stroke-width": 3
				}, g);
				const icon = el("g", {
					fill: "none",
					stroke: PAPER_COLOR,
					"stroke-width": 2.6
				}, g);
				icon.innerHTML = DOOR_GLYPH;
			}
		});
		PlanData.WINDOW_BADGES.forEach((b) => {
			const g = el("g", {
				transform: `translate(${b.x} ${b.y})`
			}, layers.doors);
			el("rect", {
				x: -24,
				y: -24,
				width: 48,
				height: 48,
				rx: 11,
				fill: INK_COLOR,
				stroke: PAPER_COLOR,
				"stroke-width": 3
			}, g);
			const icon = el("g", {
				transform: "scale(.82)",
				fill: "none",
				stroke: PAPER_COLOR,
				"stroke-width": 2.8
			}, g);
			icon.innerHTML = WINDOW_GLYPH;
		});
	}

	function drawZone(zone, index, onSelect) {
		const attrs = {
			"data-zone": zone.id
		};
		el("path", {...attrs,
			class: "zone-fill",
			d: zone.outline,
			transform: FILL_OFFSET,
			fill: zone.color
		}, layers.fill);
		el("path", {
			...attrs,
			class: "zone-outline",
			d: zone.outline,
			transform: OUTLINE_OFFSET,
			fill: "none",
			stroke: "rgba(27,42,65,.4)",
			"stroke-width": 2.6,
		}, layers.fill);
		el("path", {...attrs,
			class: "zone-hatch",
			d: zone.outline,
			fill: "url(#hatch)"
		}, layers.fill);

		const icon = PlanData.ICONS[zone.icon];
		const furniture = el("g", {
			...attrs,
			class: "zone-furniture",
			fill: "none",
			stroke: INK_COLOR,
			transform: `translate(${zone.iconAt.x} ${zone.iconAt.y}) scale(${icon.scale})`,
			"stroke-width": 3 / icon.scale,
			"stroke-linecap": "round",
			"stroke-linejoin": "round",
		}, layers.furniture);
		furniture.innerHTML = icon.markup; // codigo de marcado constante de plan-data.js
		inkIn(furniture, 0.9 + index * 0.12);

		el("path", {...attrs,
			class: "zone-select",
			d: zone.outline
		}, layers.selection);

		const hit = el("path", {
			...attrs,
			class: "zone-hit",
			d: zone.outline,
			fill: "none",
			tabindex: 0,
			role: "button",
		}, layers.hit);
		const hover = (on) => byZone("zone-select", zone.id).classList.toggle("is-hover", on);
		hit.addEventListener("click", () => onSelect(zone.id));
		hit.addEventListener("mouseenter", () => hover(true));
		hit.addEventListener("mouseleave", () => hover(false));
		hit.addEventListener("focus", () => hover(true));
		hit.addEventListener("blur", () => hover(false));
		hit.addEventListener("keydown", (e) => {
			if (e.key === "Enter" || e.key === " ") {
				e.preventDefault();
				onSelect(zone.id);
			}
		});

		el("g", {...attrs,
			class: "zone-label"
		}, layers.labels);
	}

	// --- API Publica ---------------------------------------------------------------

	/**
		* Crea el plano completo. La funcion "onSelect(zoneId)"" se activa al hacer clic, al pulsar la tecla Intro o la barra espaciadora.
		* @param {{svg: SVGElement, onSelect: function(string): void}} options
	*/
	function init({
		svg: svgElement,
		onSelect
	}) {
		svg = svgElement;
		layers = {
			fill: svg.querySelector("#layer-fill"),
			furniture: svg.querySelector("#layer-furniture"),
			walls: svg.querySelector("#layer-walls"),
			selection: svg.querySelector("#layer-selection"),
			hit: svg.querySelector("#layer-hit"),
			labels: svg.querySelector("#layer-labels"),
			doors: svg.querySelector("#layer-doors"),
		};
		order = PlanData.ZONES.map((z) => z.id);
		zoneById = {};
		PlanData.ZONES.forEach((z) => {
			zoneById[z.id] = z;
		});
		drawWalls();
		drawBadges();
		PlanData.ZONES.forEach((zone, i) => drawZone(zone, i, onSelect));
	}

	/**
		* Vuelve a dibujar la etiqueta y el texto de accesibilidad de una zona
		* @param {string} zoneId
		* @param {{name: string, alias: string, registered: boolean, active: boolean}} model
	*/
	function updateZone(zoneId, model) {
		const zone = zoneById[zoneId];
		const index = order.indexOf(zoneId);
		const g = byZone("zone-label", zoneId);
		g.innerHTML = "";
		g.setAttribute("class", `zone-label${model.active ? " is-active" : ""}${model.registered ? "" : " is-unregistered"}`);
		g.setAttribute("data-zone", zoneId);

		const marker = zone.markerAt || {
			x: zone.origin.x + 22,
			y: zone.origin.y + 38
		};
		const tag = PlanData.formatZoneNumber(index) +
			(model.active ? " · ACTIVA" : "") + (model.registered ? "" : " · SIN REGISTRAR");
		el("text", {
			class: "label-marker",
			x: marker.x,
			y: marker.y
		}, g, tag);

		const lines = splitName((model.name || "").trim() || "Sin nombre")
			.map((line) => truncate(line, NAME_MAX_CHARS_PER_LINE));
		lines.forEach((line, i) => {
			el("text", {
				class: "label-name",
				x: zone.labelAt.x,
				y: zone.labelAt.y + i * LABEL_LINE_HEIGHT,
				"text-anchor": "middle",
			}, g, line);
		});
		if (model.alias) {
			el("text", {
				class: "label-alias",
				x: zone.labelAt.x,
				y: zone.labelAt.y + lines.length * LABEL_LINE_HEIGHT + LABEL_ALIAS_GAP,
				"text-anchor": "middle",
			}, g, `“${truncate(model.alias, ALIAS_MAX_CHARS)}”`);
		}

		const hit = byZone("zone-hit", zoneId);
		hit.setAttribute("aria-label",
			`${model.name}, zona ${index + 1}${model.registered ? "" : ", sin registrar"}${model.active ? ", seleccionada" : ""}`);
	}

	/** Marca una zona como seleccionada o desmarca la seleccion si el valor es nulo */
	function setSelection(zoneId) {
		svg.classList.toggle("has-selection", Boolean(zoneId));
		svg.querySelectorAll("[data-zone]").forEach((node) => {
			if (node.classList.contains("zone-label")) return; // etiquetas gestionadas por updateZone
			node.classList.toggle("is-picked", node.dataset.zone === zoneId);
		});
		svg.querySelectorAll(".zone-hatch").forEach((n) => n.classList.toggle("is-picked", n.dataset.zone === zoneId));
	}

	/** Hace parpadear el contorno de la seleccion (usado por la funcion de busqueda) */
	function ping(zoneId) {
		const outline = byZone("zone-select", zoneId);
		outline.classList.remove("is-ping");
		void outline.getBoundingClientRect(); // restart the CSS animation
		outline.classList.add("is-ping");
		setTimeout(() => outline.classList.remove("is-ping"), PING_DURATION_MS);
	}

	/** Activa o desactiva la visualizacion de los nombres de las zonas. Devuelve true cuando los nombres estan ocultos */
	function toggleNames() {
		return svg.classList.toggle("names-hidden");
	}

	/** Centro de una zona en coordenadas de viewBox */
	function getZoneCenter(zoneId) {
		const box = byZone("zone-select", zoneId).getBBox();
		return {
			x: box.x + box.width / 2,
			y: box.y + box.height / 2
		};
	}

	return Object.freeze({
		init,
		updateZone,
		setSelection,
		ping,
		toggleNames,
		getZoneCenter
	});
})();
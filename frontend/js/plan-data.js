/**
	* -----------------------------------------------------------------------------
	* Descripcion estatica del plano de planta (solo geometria; SIN datos del backend).
	*
	* Capa: Presentacion / Datos (datos puros + elementos geometricos minimos).
	* 
	* Analogia: Este archivo es el plano del arquitecto. Indica donde se dibujan las paredes y
	* las estancias; nunca especifica como se llaman dichas estancias actualmente; eso
	* proviene del backend.
	*
	* Vinculo entre zona y backend:
	*   Cada zona enumera "internalNames": Los nombres tecnicos (normalizados en mayusculas,
	*   sin acentos, sin espacios ni simbolos) que puede tener un nodo de Unity. El primer nodo
	*   del backend cuyo "internal_name" normalizado figure en dicha lista se vincula a la zona.
*/
const PlanData = (() => {
	"use strict";

	// --- Constantes de dibujo del plano --------------
	const VIEW_BOX = Object.freeze({
		x: 30,
		y: 100,
		width: 1430,
		height: 850
	});
	const WALL_WIDTH_OUTER = 16;
	const WALL_WIDTH_INNER = 11;
	const OPENING_MASK_WIDTH = 22;
	const WINDOW_PANE_OFFSET = 5;
	const WINDOW_LINE_WIDTH = 3.2;

	// --- Funciones auxiliares minimas para formas SVG (usadas unicamente para generar el marcado del icono) --------
	const rect = (x, y, w, h, r = 0) =>
		`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}"/>`;
	const path = (d) => `<path d="${d}"/>`;
	const circle = (x, y, r) => `<circle cx="${x}" cy="${y}" r="${r}"/>`;

	/** Iconos de las habitaciones minimalistas, dibujados en torno al punto (0,0) y posteriormente escalados. */
	const ICONS = Object.freeze({
		doubleBed: {
			scale: 1.5,
			markup: rect(-50, -34, 100, 68, 5) + rect(-42, -26, 38, 22, 8) +
				rect(4, -26, 38, 22, 8) + path("M-50 6H50"),
		},
		singleBed: {
			scale: 1.5,
			markup: rect(-30, -36, 60, 72, 5) + rect(-22, -28, 44, 20, 8) +
				path("M-30 4H30") + rect(40, -30, 22, 22, 3) + circle(51, -19, 5),
		},
		bathtub: {
			scale: 1.3,
			markup: rect(-52, -8, 104, 38, 16) + path("M-46 2H46") +
				rect(-42, 30, 12, 6, 2) + rect(30, 30, 12, 6, 2) +
				path("M-36 -8V-36Q-36 -44 -28 -44H-10") + path("M-22 -50H0L-6 -38H-16Z") +
				path("M-18 -30v6M-10 -30v8M-2 -30v6") + circle(22, -20, 5) + circle(36, -30, 3.5),
		},
		stove: {
			scale: 1.8,
			markup: rect(-36, -36, 72, 72, 6) +
				circle(-17, -17, 10) + circle(17, -17, 10) + circle(-17, 17, 10) + circle(17, 17, 10) +
				circle(-17, -17, 4) + circle(17, -17, 4) + circle(-17, 17, 4) + circle(17, 17, 4),
		},
		diningTable: {
			scale: 1.6,
			markup: circle(0, 0, 22) + circle(0, 0, 12) + rect(-12, -46, 24, 12, 5) +
				rect(-12, 34, 24, 12, 5) + rect(-46, -12, 12, 24, 5) + rect(34, -12, 12, 24, 5),
		},
		sofa: {
			scale: 1.7,
			markup: rect(-56, -34, 112, 40, 10) + path("M-20 -26V6M20 -26V6") + rect(-30, 16, 60, 24, 5),
		},
	});

	/**
		* Las seis zonas. Los "internalNames" son los nombres tecnicos aceptados. 
		* Las coordenadas estan en el espacio del "viewBox" de SVG.	
	*/
	const ZONES = Object.freeze([{
		id: "main-bedroom",
		defaultName: "Cuarto Principal",
		color: "#d9825b",
		internalNames: ["CUARTOPRINCIPAL", "HABITACIONPRINCIPAL", "DORMITORIOPRINCIPAL"],
		outline: "M60 130H490V442H375V538H60Z",
		origin: {
			x: 60,
			y: 130
		},
		icon: "doubleBed",
		iconAt: {
			x: 275,
			y: 255
		},
		labelAt: {
			x: 275,
			y: 340
		},
		connectorAnchor: {
			x: 455,
			y: 190
		},
	}, {
		id: "kitchen",
		defaultName: "Cocina",
		color: "#e3b23c",
		internalNames: ["COCINA"],
		outline: "M490 130H800V442H490Z",
		origin: {
			x: 490,
			y: 130
		},
		icon: "stove",
		iconAt: {
			x: 645,
			y: 255
		},
		labelAt: {
			x: 645,
			y: 362
		},
		connectorAnchor: {
			x: 772,
			y: 320
		},
	}, {
		id: "dining-room",
		defaultName: "Comedor",
		color: "#9bb08a",
		internalNames: ["COMEDOR"],
		outline: "M800 130H1110V442H800Z",
		origin: {
			x: 800,
			y: 130
		},
		icon: "diningTable",
		iconAt: {
			x: 955,
			y: 255
		},
		labelAt: {
			x: 955,
			y: 362
		},
		connectorAnchor: {
			x: 1075,
			y: 250
		},
	}, {
		id: "living-room",
		defaultName: "Sala",
		color: "#7fa3bd",
		internalNames: ["SALA", "SALADEESTAR"],
		outline: "M375 442H1070V917H375Z",
		origin: {
			x: 375,
			y: 442
		},
		markerAt: {
			x: 470,
			y: 480
		},
		icon: "sofa",
		iconAt: {
			x: 722,
			y: 635
		},
		labelAt: {
			x: 722,
			y: 765
		},
		connectorAnchor: {
			x: 1020,
			y: 650
		},
	}, {
		id: "bathroom",
		defaultName: "Baño",
		color: "#9bb08a",
		internalNames: ["BANO", "BANIO"],
		outline: "M60 538H375V917H60Z",
		origin: {
			x: 60,
			y: 538
		},
		icon: "bathtub",
		iconAt: {
			x: 217,
			y: 690
		},
		labelAt: {
			x: 217,
			y: 795
		},
		connectorAnchor: {
			x: 335,
			y: 700
		},
	}, {
		id: "second-bedroom",
		defaultName: "Cuarto Secundario",
		color: "#d99a8f",
		internalNames: ["CUARTOSECUNDARIO", "HABITACIONSECUNDARIA", "OFICINA"],
		outline: "M1070 520H1432V917H1070Z",
		origin: {
			x: 1070,
			y: 520
		},
		icon: "singleBed",
		iconAt: {
			x: 1251,
			y: 650
		},
		labelAt: {
			x: 1251,
			y: 748
		},
		connectorAnchor: {
			x: 1395,
			y: 700
		},
	}, ]);

	// --- Aberturas: puertas (espacio) y ventanas (espacio + paneles) -----------
	/** Puerta: orientacion, punto de inicio, longitud, sentido de apertura. Devuelve [espacio, sentido de apertura]. */
	const door = (o, x, y, l, s) =>
		o === "h" ?
		[`M${x} ${y}H${x + l}`, `M${x} ${y}V${y + s * l}A${l} ${l} 0 0 ${s < 0 ? 1 : 0} ${x + l} ${y}`] :
		[`M${x} ${y}V${y + l}`, `M${x} ${y}H${x + s * l}A${l} ${l} 0 0 ${s > 0 ? 1 : 0} ${x} ${y + l}`];

	/** Ventana: orientacion, punto de inicio, longitud. Devuelve [espacio, paneles]. */
	const windowShape = (o, x, y, l) =>
		o === "h" ?
		[`M${x} ${y}H${x + l}`, `M${x} ${y - WINDOW_PANE_OFFSET}H${x + l}M${x} ${y + WINDOW_PANE_OFFSET}H${x + l}`] :
		[`M${x} ${y}V${y + l}`, `M${x - WINDOW_PANE_OFFSET} ${y}V${y + l}M${x + WINDOW_PANE_OFFSET} ${y}V${y + l}`];

	const DOORS = Object.freeze([
		door("h", 386, 442, 84, -1),
		door("v", 375, 555, 77, -1),
		door("v", 1070, 757, 70, 1),
		door("v", 1070, 468, 54, -1), ["M638 917H770", "M638 917V851A66 66 0 0 1 704 917M770 917V851A66 66 0 0 0 704 917"],
	]);

	const WINDOWS = Object.freeze([
		windowShape("h", 150, 130, 172), windowShape("h", 768, 130, 175),
		windowShape("h", 203, 917, 97), windowShape("h", 462, 917, 98),
		windowShape("h", 855, 917, 105), windowShape("h", 1118, 917, 92),
	]);

	const WALLS = Object.freeze([{
		d: "M60 917V130H1110V442H836",
		width: WALL_WIDTH_OUTER
	}, {
		d: "M60 917H1432V520H1070",
		width: WALL_WIDTH_OUTER
	}, {
		d: "M490 130V442M375 442H386M470 442H590M375 442V555M375 632V917M60 538H375" +
			"M1070 442V468M1070 522V757M1070 827V917",
		width: WALL_WIDTH_INNER,
	}, ]);

	/** Linea discontinua que separa visualmente la cocina y el comedor (sin pared). */
	const KITCHEN_DINING_DIVIDER = "M800 146V426";

	const DOOR_BADGES = Object.freeze([{
		x: 428,
		y: 442
	}, {
		x: 375,
		y: 593
	}, {
		x: 1070,
		y: 792
	}, {
		x: 704,
		y: 917,
		label: "Entrada",
		width: 172
	}, {
		x: 1070,
		y: 490,
		label: "Patio",
		width: 140
	}, ]);

	const WINDOW_BADGES = Object.freeze([{
		x: 236,
		y: 130
	}, {
		x: 856,
		y: 130
	}, {
		x: 252,
		y: 917
	}, {
		x: 511,
		y: 917
	}, {
		x: 908,
		y: 917
	}, {
		x: 1164,
		y: 917
	}, ]);

	/** "1" -> "01" Número de zona que aparece en el plano y en la ficha. */
	const formatZoneNumber = (index) => String(index + 1).padStart(2, "0");

	return Object.freeze({
		VIEW_BOX,
		OPENING_MASK_WIDTH,
		WINDOW_LINE_WIDTH,
		ICONS,
		ZONES,
		DOORS,
		WINDOWS,
		WALLS,
		KITCHEN_DINING_DIVIDER,
		DOOR_BADGES,
		WINDOW_BADGES,
		formatZoneNumber,
	});
})();
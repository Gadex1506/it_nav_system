/**
    * -----------------------------------------------------------------------------
    * Linea punteada que une la zona seleccionada en el plano con su ficha. 
    *
    * Capa: Presentacion (superposicion decorativa). Recibe dos
    * puntos (en pixeles) y traza una curva entre ellos.
    *  
    * Analogia: Un trozo de hilo rojo sujeto entre el mapa y la nota.
*/
const Connector = (() => {
	"use strict";

	const CURVE_LIFT_START = 70;
	const CURVE_LIFT_END = 60;
	const CURVE_START_RATIO = 0.45;
	const CURVE_END_RATIO = 0.3;
	const END_OFFSET_PX = 3;
	const FOLLOW_FRAME_LIMIT_MS = 700;

	let overlay;
	let line;
	let mask;
	let pinStart;
	let pinEnd;
	let resolveStart = () => null;
	let resolveEnd = () => null;
	let isInside = () => true;

	function update() {
		const start = resolveStart();
		const end = resolveEnd();
		if (!start || !end) {
			overlay.style.display = "none";
			return;
		}
		overlay.style.display = "block";
		const px = end.x + END_OFFSET_PX;
		const py = end.y + END_OFFSET_PX;
		const d = `M${start.x} ${start.y}C${start.x + (px - start.x) * CURVE_START_RATIO} ${start.y - CURVE_LIFT_START},` +
			`${px - (px - start.x) * CURVE_END_RATIO} ${py + CURVE_LIFT_END},${px} ${py}`;
		line.setAttribute("d", d);
		mask.setAttribute("d", d);
		pinStart.setAttribute("transform", `translate(${start.x} ${start.y})`);
		pinStart.style.display = isInside(start) ? "" : "none";
		pinEnd.setAttribute("cx", px);
		pinEnd.setAttribute("cy", py);
	}

	/** Redibuja cada fotograma durante "ms". Se utiliza mientras los paneles o el zoom se estan animando */
	function follow(ms = FOLLOW_FRAME_LIMIT_MS) {
		const t0 = performance.now();
		(function frame() {
			update();
			if (performance.now() - t0 < ms) requestAnimationFrame(frame);
		})();
	}

	/** Reproduce de nuevo la animacion de "dibujo" de la linea */
	function replay() {
		overlay.classList.remove("is-drawing");
		void overlay.getBoundingClientRect();
		overlay.classList.add("is-drawing");
	}

	/**
	    * @param {{overlay, line, mask, pinStart, pinEnd,
	    *          resolveStart: function, resolveEnd: function, isInside: function}} o
	    * resolve* devuelve {x, y} en pixeles de escenario, o null para ocultar el conector
	*/
	function init(o) {
		({
			overlay,
			line,
			mask,
			pinStart,
			pinEnd,
			resolveStart,
			resolveEnd,
			isInside
		} = o);
	}

	return Object.freeze({
		init,
		update,
		follow,
		replay
	});
})();
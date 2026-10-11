/**
    * Avisos compartidos por todas las pestanas: Toast (mensaje corto temporal)
    * y Banner (franja de error con boton "Reintentar").
    *
    * Capa: Presentacion (componentes reutilizables).
    * Analogia: El timbre y el letrero de la casa. Cualquier habitacion los usa
    * pero ninguna es duena de ellos.
    *
    * Requiere en el HTML: #toast, #banner, #bannerText, #bannerRetry.
*/
const Toast = (() => {
	"use strict";

	const DURATION_MS = 3500;
	const node = document.getElementById("toast");
	let timer = null;

	/** Muestra un mensaje que desaparece solo */
	function show(message) {
		node.textContent = message;
		node.hidden = false;
		clearTimeout(timer);
		timer = setTimeout(() => {
			node.hidden = true;
		}, DURATION_MS);
	}

	return Object.freeze({
		show
	});
})();

const Banner = (() => {
	"use strict";

	const node = document.getElementById("banner");
	const text = document.getElementById("bannerText");
	const retryButton = document.getElementById("bannerRetry");
	let retryHandler = null;

	retryButton.addEventListener("click", () => {
		if (retryHandler) retryHandler();
	});

	/**
		* Muestra la franja de error.
		* @param {string} message texto para la persona usuaria
		* @param {function|null} onRetry accion del boton "Reintentar" (null lo oculta)
	*/
	function show(message, onRetry = null) {
		text.textContent = message;
		retryHandler = onRetry;
		retryButton.hidden = !onRetry;
		node.hidden = false;
	}

	function hide() {
		node.hidden = true;
		retryHandler = null;
	}

	return Object.freeze({
		show,
		hide
	});
})();
/**
    * Navegacion entre pestanas del panel (una sola pagina, varias "vistas").
    *
    * Capa: Presentacion (navegador de vistas).
    * Patron: Registro (cada pestana se registra con su vista y su accion onShow).
    * Analogia: el vigilante del edificio. Sabe que piso esta abierto y avisa al
    * piso que se abre para que se prepare (cargue datos, reajuste medidas).
    *
    * En el HTML: Cada vista es un elemento con data-view="nombre" y cada enlace
    * del menu es <a data-tab="nombre">.
*/
const Tabs = (() => {
	"use strict";

	// Pestanas que aun no existen: solo muestran un aviso
	const COMING_SOON = Object.freeze({
		settings: "Configuración",
		help: "Ayuda"
	});

	/** nombre -> { element, onShow } */
	const registry = new Map();
	let current = null;

	/** Registra una pestana con su elemento de vista y su callback onShow */
	function register(name, {
		element,
		onShow
	}) {
		registry.set(name, {
			element,
			onShow
		});
	}

	/** Muestra la pestana indicada y oculta las demas */
	function show(name) {
		if (!registry.has(name)) return;
		Banner.hide(); // el aviso de una pestana no debe quedarse en otra
		registry.forEach((tab, tabName) => {
			tab.element.hidden = tabName !== name;
		});
		document.querySelectorAll("nav a[data-tab]").forEach((link) => {
			if (link.dataset.tab === name) link.setAttribute("aria-current", "page");
			else link.removeAttribute("aria-current");
		});
		current = name;
		registry.get(name).onShow();
	}

	/** Conecta los enlaces del menu */
	function init() {
		document.querySelectorAll("nav a[data-tab]").forEach((link) => {
			link.addEventListener("click", (event) => {
				event.preventDefault();
				const name = link.dataset.tab;
				if (COMING_SOON[name]) {
					Toast.show(`${COMING_SOON[name]} · próximamente`);
					return;
				}
				if (name !== current) show(name);
			});
		});
	}

	return Object.freeze({
		register,
		show,
		init
	});
})();
/**
    * Arranque del panel de desarrollo: Registra las pestanias (Casas y
    * Dispositivos) en el navegador de vistas compartido.
    *
    * Capa de Presentacion (composicion): Es el equivalente de main.js del panel de
    * usuario. No tiene logica propia, solo conecta las piezas.
*/
(() => {
	"use strict";

	Tabs.register("houses", {
		element: document.getElementById("housesView"),
		onShow: () => {}
	});
	Tabs.register("devices", {
		element: document.getElementById("devicesView"),
		onShow: DevicesTab.onShow
	});
	Tabs.init();
	Tabs.show("houses");
})();
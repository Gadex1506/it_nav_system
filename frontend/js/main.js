/**
    * Punto de entrada del panel: Registra las pestanas y abre la primera.
    * Debe cargarse al final, despues de todos los demas scripts.
*/
(() => {
	"use strict";

	Tabs.register("home", {
		element: document.getElementById("stage"),
		onShow: HomeTab.onShow
	});
	Tabs.register("users", {
		element: document.getElementById("usersView"),
		onShow: UsersTab.onShow
	});
	Tabs.init();
	Tabs.show("home");
})();
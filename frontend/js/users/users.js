/**
	* Controlador de la pestana "Usuarios": lista las personas registradas en el
	* reconocimiento facial, muestra su ficha, permite corregir el nombre y
	* eliminar al usuario. NO permite crear usuarios (eso solo ocurre en la casa).
	*
	* Capa: Presentacion (controlador). Usa users-api.js para los datos y
	* Toast / Banner para los avisos compartidos.
	* 
	* Analogia: La recepcionista del registro de residentes. Atiende los pedidos
	* y consulta el archivo (users-api.js) sin saber como esta guardado.
	*
	* Seguridad de la interfaz: Todo texto de usuario entra con textContent
	* (nunca innerHTML) para evitar inyeccion de codigo.
*/
(() => {
	"use strict";

	// --- Constantes ---------------------------------------
	const MAX_NAME_LENGTH = 40;
	const AVATAR_COLORS = ["var(--mustard)", "var(--sage)", "var(--blue)", "var(--rose)"];
	const ROLE_ADMIN = "Administrador";
	const ROLE_RESIDENT = "Residente";
	const DATE_LOCALE = "es-CO";

	const $ = (id) => document.getElementById(id);

	// --- Estado ---------------------------------------------------------------------
	let users = [];
	let selectedId = null;
	let isBusy = false; // evita acciones dobles mientras hay una peticion en curso
	let isLoading = false;

	const dom = {
		view: $("usersView"),
		state: $("usersState"),
		list: $("usersList"),
		keyCard: $("usersKey"),
		keyForm: $("usersKeyForm"),
		keyInput: $("usersKeyInput"),
		keyError: $("usersKeyError"),
		refresh: $("usersRefresh"),
		changeKey: $("usersChangeKey"),
		hint: $("usersSideHint"),
		detail: $("userDetail"),
		detailId: $("userDetailId"),
		detailClose: $("userDetailClose"),
		nameInput: $("userNameInput"),
		nameError: $("userNameError"),
		role: $("userRole"),
		date: $("userDate"),
		deleteButton: $("userDeleteButton"),
		deleteConfirm: $("userDeleteConfirm"),
		deleteYes: $("userDeleteYes"),
		deleteNo: $("userDeleteNo"),
		deleteError: $("userDeleteError"),
	};

	// ============================================================================
	// Ayudas pequenas
	// ============================================================================

	const roleOf = (user) => (user.isAdmin ? ROLE_ADMIN : ROLE_RESIDENT);
	const errorText = (error) => (error && error.message) ? error.message : "Error desconocido";
	const findUser = (id) => users.find((u) => u.id === id) || null;

	function formatDate(date) {
		if (!date) return "Fecha desconocida";
		try {
			return new Intl.DateTimeFormat(DATE_LOCALE, {
				dateStyle: "long",
				timeStyle: "short"
			}).format(date);
		} catch (e) {
			return date.toLocaleString();
		}
	}

	function firstLetter(name) {
		const first = Array.from(name.trim())[0];
		return first ? first.toUpperCase() : "?";
	}

	function setState(message) {
		dom.state.textContent = message;
		dom.state.hidden = !message;
	}

	// ============================================================================
	// Clave de acceso
	// ============================================================================

	function showKeyForm(errorMessage) {
		dom.keyCard.hidden = false;
		dom.keyError.textContent = errorMessage || "";
		dom.keyError.hidden = !errorMessage;
		dom.keyInput.value = "";
		dom.keyInput.focus();
	}

	function hideKeyForm() {
		dom.keyCard.hidden = true;
		dom.keyError.hidden = true;
	}

	function onKeySubmit(event) {
		event.preventDefault();
		const value = dom.keyInput.value.trim();
		if (!value) {
			showKeyForm("Pega la clave que aparece en admin_api_key.txt.");
			return;
		}
		UsersApiKeyStore.set(value);
		hideKeyForm();
		loadUsers();
	}

	// ============================================================================
	// Carga y lista
	// ============================================================================

	/** Decide que mostrar segun el tipo de error del servicio */
	function handleLoadError(error) {
		users = [];
		renderList();
		closeDetail();
		if (error.kind === UsersApiErrorKind.UNAUTHORIZED || error.kind === UsersApiErrorKind.MISSING_KEY) {
			UsersApiKeyStore.clear();
			setState("");
			showKeyForm(error.kind === UsersApiErrorKind.UNAUTHORIZED ? error.message : "");
			return;
		}
		setState("No se pudo cargar la lista de usuarios.");
		Banner.show(errorText(error), loadUsers);
	}

	async function loadUsers() {
		if (isLoading) return;
		if (!UsersApiKeyStore.get()) {
			setState("");
			showKeyForm();
			return;
		}
		isLoading = true;
		Banner.hide();
		hideKeyForm();
		setState("Cargando usuarios…");
		try {
			users = await fetchUsers();
			setState(users.length ? "" : "Todavía no hay usuarios registrados. Se crean desde la casa, con el reconocimiento facial.");
			renderList();
			if (selectedId !== null && !findUser(selectedId)) closeDetail();
			else if (selectedId !== null) renderDetail();
		} catch (error) {
			handleLoadError(error);
		} finally {
			isLoading = false;
		}
	}

	function renderList() {
		dom.list.innerHTML = "";
		users.forEach((user) => {
			const item = document.createElement("li");
			const card = document.createElement("button");
			card.type = "button";
			card.className = `user-card${user.id === selectedId ? " is-selected" : ""}`;
			card.dataset.id = String(user.id);

			const avatar = document.createElement("span");
			avatar.className = "user-avatar";
			avatar.style.background = AVATAR_COLORS[Math.abs(Number(user.id) || 0) % AVATAR_COLORS.length];
			avatar.textContent = firstLetter(user.name);

			const info = document.createElement("span");
			info.className = "user-info";
			const name = document.createElement("span");
			name.className = "user-name";
			name.textContent = user.name;
			const role = document.createElement("span");
			role.className = `user-role${user.isAdmin ? " is-admin" : ""}`;
			role.textContent = roleOf(user);
			info.append(name, role);

			card.append(avatar, info);
			card.addEventListener("click", () => selectUser(user.id));
			item.append(card);
			dom.list.append(item);
		});
	}

	// ============================================================================
	// Ficha del usuario
	// ============================================================================

	function selectUser(id) {
		selectedId = id;
		resetDeleteConfirm();
		renderList();
		renderDetail();
	}

	function closeDetail() {
		selectedId = null;
		dom.detail.classList.remove("is-visible");
		dom.detail.hidden = true;
		dom.hint.hidden = false;
		resetDeleteConfirm();
		renderList();
	}

	function renderDetail() {
		const user = findUser(selectedId);
		if (!user) {
			closeDetail();
			return;
		}
		dom.hint.hidden = true;
		dom.detail.hidden = false;
		dom.detailId.textContent = String(user.id);
		dom.nameInput.value = user.name;
		dom.nameError.hidden = true;
		dom.role.textContent = roleOf(user);
		dom.role.classList.toggle("is-admin", user.isAdmin);
		dom.date.textContent = formatDate(user.registeredAt);
		dom.detail.classList.remove("is-visible");
		void dom.detail.offsetWidth;
		dom.detail.classList.add("is-visible");
		if (window.matchMedia("(max-width: 1100px)").matches) {
			dom.detail.scrollIntoView({
				behavior: "smooth",
				block: "nearest"
			}); // en pantallas angostas la ficha queda debajo de la lista
		}
	}

	// --- Renombrar ---------------------------------------------------------------------

	async function commitRename() {
		const user = findUser(selectedId);
		if (!user || isBusy) return;
		const value = dom.nameInput.value.trim();
		if (value === user.name) {
			dom.nameError.hidden = true;
			return;
		}
		if (!value) {
			showFieldError(dom.nameError, "El nombre no puede estar vacío.");
			dom.nameInput.value = user.name;
			return;
		}
		isBusy = true;
		try {
			const updated = await updateUserName(user.id, value);
			users = users.map((u) => (u.id === updated.id ? updated : u));
			renderList();
			dom.nameError.hidden = true;
			Toast.show("Nombre actualizado");
		} catch (error) {
			showFieldError(dom.nameError, errorText(error));
			dom.nameInput.value = user.name;
		} finally {
			isBusy = false;
			const current = findUser(selectedId);
			if (current) dom.nameInput.value = current.name;
		}
	}

	function showFieldError(target, message) {
		target.textContent = message;
		target.hidden = false;
	}

	// --- Eliminar (dos pasos, definitivo) -------------------------------------------

	function resetDeleteConfirm() {
		dom.deleteConfirm.hidden = true;
		dom.deleteButton.hidden = false;
		dom.deleteError.hidden = true;
	}

	function askDeleteConfirmation() {
		dom.deleteButton.hidden = true;
		dom.deleteConfirm.hidden = false;
		dom.deleteNo.focus();
	}

	async function confirmDelete() {
		const user = findUser(selectedId);
		if (!user || isBusy) return;
		isBusy = true;
		dom.deleteConfirm.classList.add("is-busy");
		try {
			await deleteUser(user.id);
			users = users.filter((u) => u.id !== user.id);
			closeDetail();
			setState(users.length ? "" : "Todavía no hay usuarios registrados. Se crean desde la casa, con el reconocimiento facial.");
			Toast.show(`Usuario "${user.name}" eliminado`);
		} catch (error) {
			showFieldError(dom.deleteError, errorText(error));
			if (error.kind === UsersApiErrorKind.NOT_FOUND) loadUsers(); // ya no existe: se refresca la lista
		} finally {
			isBusy = false;
			dom.deleteConfirm.classList.remove("is-busy");
		}
	}

	// ============================================================================
	// Conexion de eventos y arranque
	// ============================================================================

	function wireEvents() {
		dom.keyForm.addEventListener("submit", onKeySubmit);
		dom.refresh.addEventListener("click", loadUsers);
		dom.changeKey.addEventListener("click", () => showKeyForm());
		dom.detailClose.addEventListener("click", closeDetail);

		dom.nameInput.maxLength = MAX_NAME_LENGTH;
		dom.nameInput.addEventListener("blur", commitRename);
		dom.nameInput.addEventListener("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				dom.nameInput.blur();
			}
			if (e.key === "Escape") {
				e.stopPropagation();
				const user = findUser(selectedId);
				if (user) dom.nameInput.value = user.name;
				dom.nameInput.blur();
			}
		});

		dom.deleteButton.addEventListener("click", askDeleteConfirmation);
		dom.deleteNo.addEventListener("click", resetDeleteConfirm);
		dom.deleteYes.addEventListener("click", confirmDelete);

		document.addEventListener("keydown", (e) => {
			if (e.key === "Escape" && !dom.view.hidden && selectedId !== null && e.target.tagName !== "INPUT") closeDetail();
		});
	}

	/** Lo llama Tabs cada vez que la pestana Usuarios se hace visible */
	function onShow() {
		loadUsers(); // los usuarios pueden cambiar en la casa: se refresca siempre
	}

	wireEvents();
	window.UsersTab = Object.freeze({
		onShow
	});
})();
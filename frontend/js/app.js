/**
    * app.js
    *
    * Capa de presentacion del panel web: conecta los datos que trae
    * api.js con el HTML de index.html, y maneja las interacciones
    * del usuario (clics, formularios).
    *
    * Responsabilidad: Renderizar la interfaz y reaccionar a eventos.
    * NO contiene logica de comunicacion HTTP, eso vive en api.js.
    *
    * Nota para el equipo:
    *   Este archivo SI esta pensado para ser reescrito por completo
    *   al migrar a un framework si asi lo requieren. La logica de "que hacer" se mantiene,
    *   pero el "como" (manipulación directa del DOM) cambia totalmente
    *   en React, Angular o Vue.
*/


// ------ Bloque 1 - Estado, utilidades de mensajes, y carga inicial de nodos --------------

// Estado minimo en memoria
// Guarda el ID del nodo que el usuario esta editando actualmente.
// Es null cuando no hay ningun nodo seleccionado
// Usando React por ejemplo, esto cambiaria a un useState
let currentNodeId = null;

// Referencias a elementos del DOM (se buscan una sola vez)
const nodesListEl = document.getElementById("nodes-list");
const editSectionEl = document.getElementById("edit-section");
const messageAreaEl = document.getElementById("message-area");
const detailInternalNameEl = document.getElementById("detail-internal-name");
const detailNodeTypeEl = document.getElementById("detail-node-type");
const displayNameInputEl = document.getElementById("display-name-input");
const aliasesListEl = document.getElementById("aliases-list");
const renameFormEl = document.getElementById("rename-form");
const addAliasFormEl = document.getElementById("add-alias-form");
const aliasInputEl = document.getElementById("alias-input");
const closeEditBtnEl = document.getElementById("close-edit-btn");

/**
    * Muestra un mensaje al usuario en el area de mensajes,
    * ya sea de exito o de error, y lo oculta automaticamente
    * despues de unos segundos.
    *
    * @param {string} text - Texto del mensaje a mostrar.
    * @param {"success"|"error"} type - Tipo de mensaje, define el color.
*/
function showMessage(text, type) {
    messageAreaEl.textContent = text;
    messageAreaEl.className = `message-area ${type}`; // quita "hidden", agrega el tipo

    // Oculta el mensaje automaticamente despues de 4 segundos
    setTimeout(() => {
        messageAreaEl.classList.add("hidden");
    }, 4000);
}

/**
    * Carga todos los nodos desde el backend y los renderiza
    * en la lista principal. Se llama al iniciar la pagina y
    * despues de cualquier cambio que afecte la lista (por ejemplo renombrar).
*/
async function loadNodes() {
    try {
        const nodes = await fetchNodes();
        renderNodesList(nodes);
    } catch (error) {
        nodesListEl.innerHTML = "";
        showMessage(`No se pudieron cargar los nodos: ${error.message}`, "error");
    }
}

/**
    * Pinta la lista de nodos en el HTML a partir de los datos
    * recibidos del backend.
    *
    * @param {Array} nodes - Lista de nodos con sus alias.
*/
function renderNodesList(nodes) {
    if (nodes.length == 0) {
        nodesListEl.innerHTML = "<p class='loading-text'>No hay nodos registrados todavía.</p>";
        return;
    }

    // Construimos el HTML de cada tarjeta de nodo y lo unimos en un string.
    // Usamos data-node-id para saber, al hacer clic, que nodo estamos ajustando.
    nodesListEl.innerHTML = nodes.map(node => `
        <div class="node-card" data-node-id="${node.id}">
            <span class="node-name">${node.display_name}</span>
            <span class="node-type-tag">${node.node_type}</span>
        </div>
        `).join("");

    // Agregamos el evento de click a cada tarjeta recien creada
    document.querySelectorAll(".node-card").forEach(card => {
        card.addEventListener("click", () => {
            const nodeId = parseInt(card.dataset.nodeId, 10);
            openEditPanel(nodeId);
        });
    });
}

// ------ Bloque 2 - Abrir panel de edicion y renderizar alias --------------

/**
    * Abre el panel de edicion para un nodo especifico: consulta su
    * detalle completo en el backend y lo muestra en la interfaz.
    *
    * @param {number} nodeId - ID del nodo a editar.
*/
async function openEditPanel(nodeId) {
    try {
        const node = await fetchNodeById(nodeId);

        // Guardamos el ID en el estado para que los formularios
        // de renombrar y agregar alias sepan sobre que nodo actuar.
        currentNodeId = node.id;

        detailInternalNameEl.textContent = node.internal_name;
        detailNodeTypeEl.textContent = node.node_type;
        displayNameInputEl.value = node.display_name;

        renderAliasesList(node.aliases);

        editSectionEl.classList.remove("hidden");

        // Desplaza la vista hacia el panel de edicion, util si la
        // lista de nodos es larga y el panel queda fuera de vista.
        editSectionEl.scrollIntoView({ behavior: "smooth" });

    } catch (error) {
        showMessage(`No se pudo abrir el nodo: ${error.message}`, "error");
    }
}


/**
    * Pinta la lista de alias de un nodo como "pildoras" con boton
    * de eliminar, dentro del panel de edicion.
    *
    * @param {Array} aliases - Lista de alias del nodo actualmente abierto.
*/
function renderAliasesList(aliases) {
    if (aliases.length == 0) {
        aliasesListEl.innerHTML = "<li style='background:none; border:none; color:#888;'>Sin alias todavía</li>";
        return;
    }

    // Cada <li> lleva el ID del alias en data-alias-id, igual que
    // hicimos con data-node-id en la lista principal de nodos.
    aliasesListEl.innerHTML = aliases.map(alias => `
        <li data-alias-id="${alias.id}">
            ${alias.alias}
            <button class="remove-alias-btn" title="Eliminar alias">X</button>
        </li>
        `).join("");

    // Conectamos el boton de eliminar de cada pildora recien creada.
    document.querySelectorAll(".remove-alias-btn").forEach(button => {
        button.addEventListener("click", async (event) => {
            const listItem = event.target.closest("li");
            const aliasId = parseInt(listItem.dataset.aliasId, 10);
            await handleDeleteAlias(aliasId);
        });
    });
}

/**
    * Cierra el panel de edicion y limpia el estado actual.
    * Se llama al presionar el boton "Cerrar edicion".
*/
function closeEditPanel() {
    currentNodeId = null;
    editSectionEl.classList.add("hidden");
}

// ------ Bloque 3 - Manejadores de formularios e inicializacion --------------


/**
    * Maneja el envio del formulario de renombrar un nodo.
    * Llama al backend, actualiza la interfaz y refresca la lista
    * de nodos para reflejar el nuevo nombre.
    *
    * @param {Event} event - Evento de submit del formulario.
*/
async function handleRenameSubmit(event) {
    event.preventDefault(); // Evita que el formulario recargue la pagina

    const newName = displayNameInputEl.value.trim();

    try {
        await renameNode(currentNodeId, newName);
        showMessage("Nombre actualizado correctamente.", "success");

        // Refrescamos la lista principal para que el nuevo nombre
        // se vea reflejado tambien ahi, no solo en el panel de edicion
        await loadNodes();

    } catch (error) {
        showMessage(`No se pudo renombrar: ${error.message}`, "error");
    }
}

/**
    * Maneja el envio del formulario de agregar un nuevo alias.
    * Si el backend rechaza el alias (ej. limite de 5 alcanzado),
    * el mensaje de error exacto del backend se muestra al usuario.
    *
    * @param {Event} event - Evento de submit del formulario.
*/
async function handleAddAliasSubmit(event) {
    event.preventDefault();

    const newAlias = aliasInputEl.value.trim();

    if (!newAlias) {
        return; // No enviamos alias vacios
    }

    try {
        await addAliasToNode(currentNodeId, newAlias);
        showMessage("Alias agregado correctamente.", "success");

        aliasInputEl.value = ""; // Limpia el campo de texto

        // Volvemos a pedir el nodo completo  para refrescar su lista
        // de alias actualizada (incluyendo el que acabamos de agregar).
        const updateNode = await fetchNodeById(currentNodeId);
        renderAliasesList(updateNode.aliases);

    } catch (error) {
        showMessage(`No se pudo agregar el alias: ${error.message}`, "error");
    }
}

/**
    * Elimina un alias especifico y refresca la lista de alias
    * del panel de edicion abierto actualmente.
    *
    * @param {number} aliasId - ID del alias a eliminar.
*/
async function handleDeleteAlias(aliasId) {
    try {
        await deleteAliasFromNode(currentNodeId, aliasId);
        showMessage("Alias eliminado.", "success");

        const updateNode = await fetchNodeById(currentNodeId);
        renderAliasesList(updateNode.aliases);

    } catch (error) {
        showMessage(`No se pudo eliminar el alias: ${error.message}`, "error");
    }
}

// Registro de eventos principales
renameFormEl.addEventListener("submit", handleRenameSubmit);
addAliasFormEl.addEventListener("submit", handleAddAliasSubmit);
closeEditBtnEl.addEventListener("click", closeEditPanel);

// Inicializacion. Se ejecuta apenas el HTML termina de cargar
document.addEventListener("DOMContentLoaded", () => {
    loadNodes();
});
/**
    * Acercar/alejar (rueda / botones) y desplazar (arrastrar) el plano.
    *
    * Capa: Presentacion (comportamiento de interaccion). Responsabilidad unica: Mueve
    * y escala un contenedor. No sabe nada sobre las zonas ni el backend.
    * 
    * Analogia: Es quien maneja la camara. Decide que parte de la mesa se ve.
*/
const Viewport = (() => {
	"use strict";

	const MIN_ZOOM = 0.6;
	const MAX_ZOOM = 4;
	const BUTTON_ZOOM_FACTOR = 1.3;
	const WHEEL_SENSITIVITY = 0.0018;
	const WHEEL_SENSITIVITY_PINCH = 0.01;
	const WHEEL_DELTA_LIMIT = 120;
	const DRAG_THRESHOLD_PX = 5;
	const KEEP_VISIBLE_PX = 140;
	const MIN_PLAN_WIDTH = 480;
	const MAX_PLAN_WIDTH = 980;
	const SIDE_MARGIN_PX = 60;
	const BOTTOM_RESERVED_PX = 150;
	//const VERTICAL_NUDGE_PX = 30;
	const ANIMATION_MS = 480;
    const CONTROLS_GAP_PX = 4;
    const MIN_TOP_PX = 56;
    const STACKED_QUERY = "(max-width: 1100px)";
    const STACKED_MARGIN_PX = 12;
    const STACKED_MIN_WIDTH = 300;
    const STACKED_PADDING_PX = 12;

	let area;
	let view;
	let svg;
	let zoomLabel;
    let controls;
	let onChange;
	let onBackgroundClick;
	let zoom = 1;
	let tx = 0;
	let ty = 0;
	let planWidth = 900;
	let planHeight = 535;
	let animTimer = null;
	let drag = null;

	const vb = () => PlanData.VIEW_BOX;

	function apply() {
		view.style.transform = `translate(${tx}px,${ty}px) scale(${zoom})`;
		zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
		onChange();
	}

	function clamp() {
		const w = planWidth * zoom;
		const h = planHeight * zoom;
		tx = Math.min(area.clientWidth - KEEP_VISIBLE_PX, Math.max(KEEP_VISIBLE_PX - w, tx));
		ty = Math.min(area.clientHeight - KEEP_VISIBLE_PX, Math.max(KEEP_VISIBLE_PX - h, ty));
	}

	/** Ajusta el plano a la zona y lo vuelve a centrar (zoom al 100 %). */
	function layout() {
        const stacked = window.matchMedia(STACKED_QUERY).matches;
        const aw = area.clientWidth;
        zoom = 1;
        if (stacked) {
   		    planWidth = Math.max(STACKED_MIN_WIDTH, Math.min(MAX_PLAN_WIDTH, aw - 2 * STACKED_MARGIN_PX));
   		    planHeight = (planWidth * vb().height) / vb().width;
   		    area.style.height = `${planHeight + 2 * STACKED_PADDING_PX}px`;
            controls.style.top = "";
            controls.style.bottom = "";
            tx = (aw - planWidth) / 2;
            ty = STACKED_PADDING_PX;
        } else {
            area.style.height = "";
            const ah = area.clientHeight;
            const controlsHeight = controls.offsetHeight;
            planWidth = Math.max(MIN_PLAN_WIDTH, Math.min(MAX_PLAN_WIDTH, aw - SIDE_MARGIN_PX,
   			    ((ah - BOTTOM_RESERVED_PX) * vb().width) / vb().height));
   		    planHeight = (planWidth * vb().height) / vb().width;
            const groupHeight = planHeight + CONTROLS_GAP_PX + controlsHeight;
            tx = (aw - planWidth) / 2;
            ty = Math.max(MIN_TOP_PX, (ah - groupHeight) / 2);
            controls.style.bottom = "auto";
            controls.style.top = `${Math.min(ty + planHeight + CONTROLS_GAP_PX, ah - controlsHeight - 12)}px`;
        }
        svg.style.width = `${planWidth}px`;
        apply();
    }

	/** Aplica un cambio en la vista mediante una transicion CSS y, a continuacion, elimina la transicion. */
	function animated(change) {
		view.classList.add("is-animated");
		change();
		apply();
		clearTimeout(animTimer);
		animTimer = setTimeout(() => view.classList.remove("is-animated"), ANIMATION_MS);
	}

	function zoomAt(cx, cy, factor) {
		const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, zoom * factor));
		const f = next / zoom;
		tx = cx - (cx - tx) * f;
		ty = cy - (cy - ty) * f;
		zoom = next;
		clamp();
		apply();
	}

	const center = () => [area.clientWidth / 2, area.clientHeight / 2];

	// --- Acciones publicas -----------------------------------------------------------
	const zoomIn = () => animated(() => zoomAt(...center(), BUTTON_ZOOM_FACTOR));
	const zoomOut = () => animated(() => zoomAt(...center(), 1 / BUTTON_ZOOM_FACTOR));
	const reset = () => animated(layout);
	const isZoomed = () => zoom > 1.05;

	/** Centra la vista en un punto dado en coordenadas de viewBox. */
	function focusOn(point) {
		animated(() => {
			const k = planWidth / vb().width;
			tx = area.clientWidth / 2 - (point.x - vb().x) * k * zoom;
			ty = area.clientHeight / 2 - (point.y - vb().y) * k * zoom;
			clamp();
		});
	}

	/** Convierte un punto de viewBox a coordenadas de pixel relativas al escenario. */
	function toStagePoint(point, stage) {
		const box = svg.getBoundingClientRect();
		const s = stage.getBoundingClientRect();
		const k = box.width / vb().width;
		return {
			x: box.left + (point.x - vb().x) * k - s.left,
			y: box.top + (point.y - vb().y) * k - s.top,
		};
	}

	// --- Manejo de eventos de puntero ---------------------------------------------------------
	function onWheel(e) {
		e.preventDefault();
		const rect = area.getBoundingClientRect();
		const delta = Math.max(-WHEEL_DELTA_LIMIT, Math.min(WHEEL_DELTA_LIMIT, e.deltaY));
		const sensitivity = e.ctrlKey ? WHEEL_SENSITIVITY_PINCH : WHEEL_SENSITIVITY;
		zoomAt(e.clientX - rect.left, e.clientY - rect.top, Math.exp(-delta * sensitivity));
	}

	function onPointerDown(e) {
		const onZone = e.target.closest(".zone-hit");
		const isMiddle = e.button === 1;
		if (isMiddle || (e.button === 0 && !onZone)) {
			drag = {
				x: e.clientX,
				y: e.clientY,
				tx,
				ty,
				moved: false,
				middle: isMiddle
			};
			area.setPointerCapture(e.pointerId);
			area.classList.add("is-panning");
		}
	}

	function onPointerMove(e) {
		if (!drag) return;
		const dx = e.clientX - drag.x;
		const dy = e.clientY - drag.y;
		if (Math.hypot(dx, dy) > DRAG_THRESHOLD_PX) drag.moved = true;
		if (drag.moved) {
			tx = drag.tx + dx;
			ty = drag.ty + dy;
			clamp();
			apply();
		}
	}

	function onPointerUp() {
		if (!drag) return;
		area.classList.remove("is-panning");
		if (!drag.moved && !drag.middle) onBackgroundClick(); // plain click on empty space
		drag = null;
	}

	/**
	    * @param {{area, view, svg, zoomLabel, onChange: function, onBackgroundClick: function}} o
	*/
	function init(o) {
		({
			area,
			view,
			svg,
			zoomLabel,
            controls,
			onChange,
			onBackgroundClick
		} = o);
		area.addEventListener("wheel", onWheel, {
			passive: false
		});
		area.addEventListener("mousedown", (e) => {
			if (e.button === 1) e.preventDefault();
		});
		area.addEventListener("pointerdown", onPointerDown);
		area.addEventListener("pointermove", onPointerMove);
		area.addEventListener("pointerup", onPointerUp);
		area.addEventListener("pointercancel", () => {
			drag = null;
			area.classList.remove("is-panning");
		});
		window.addEventListener("resize", layout);
		layout();
	}

	return Object.freeze({
		init,
		layout,
		zoomIn,
		zoomOut,
		reset,
		isZoomed,
		focusOn,
		toStagePoint
	});
})();
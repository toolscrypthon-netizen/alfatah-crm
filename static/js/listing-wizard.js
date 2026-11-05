/* Step-by-step "Add a listing" screen. Photos are shrunk on the phone before upload so it works on mobile data. */
(function () {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const root = $("#wz");
  if (!root) return;

  const form = $("#wzForm");
  const steps = $$(".wz-step", form);
  const editing = root.dataset.editing === "1";
  const maxPhotos = +root.dataset.maxPhotos - +root.dataset.existingPhotos;
  const areasByCity = JSON.parse($("#wzAreas").textContent);
  let current = 0;

  const val = name => (form.querySelector(`[name="${name}"]:checked`) || {}).value;
  const typeLabel = () => {
    const t = val("property_type");
    return t ? $(`label[for="type-${t}"] span:last-child`).textContent.replace("Flat / Apartment", "Apartment") : "Property";
  };

  /* ---------- Money in lakh / crore ---------- */
  function pkr(n) {
    if (!n) return "";
    const fmt = x => (+x.toFixed(2)).toString();
    if (n >= 1e7) return fmt(n / 1e7) + " Crore";
    if (n >= 1e5) return fmt(n / 1e5) + " Lakh";
    return n.toLocaleString("en-PK");
  }

  /* ---------- Steps ---------- */
  function show(i) {
    current = Math.max(0, Math.min(steps.length - 1, i));
    steps.forEach((s, n) => (s.hidden = n !== current));
    $("#wzBar").style.width = ((current + 1) / steps.length) * 100 + "%";
    $("#wzStepNo").textContent = `Step ${current + 1} of ${steps.length}`;
    $("#wzStepName").textContent = steps[current].dataset.name;
    $("#wzBack").style.visibility = current === 0 ? "hidden" : "visible";
    const last = current === steps.length - 1;
    $("#wzNext").hidden = last;
    $("#wzSave").hidden = !last;
    if (last) refreshSummary();
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
  }
  $("#wzNext").addEventListener("click", () => {
    if (current === 0 && !val("property_type")) return flash("Pick the type of property.");
    show(current + 1);
  });
  $("#wzBack").addEventListener("click", () => show(current - 1));
  // Picking a property type moves straight on: one tap instead of two.
  // "click" also fires when tapping the type that is already selected.
  $$("[data-advance]").forEach(r => r.addEventListener("click", () => setTimeout(() => show(current + 1), 180)));
  // Enter in a text box goes to the next step instead of submitting half a form.
  form.addEventListener("keydown", e => {
    if (e.key === "Enter" && e.target.tagName === "INPUT" && e.target.id !== "wzFeatureNew") {
      e.preventDefault();
      if (current < steps.length - 1) show(current + 1);
    }
  });

  function flash(msg) {
    const box = $("#wzErrors");
    box.textContent = msg;
    box.hidden = false;
    setTimeout(() => (box.hidden = true), 3500);
  }

  /* ---------- Type-dependent bits ---------- */
  function onTypeChange() {
    const t = val("property_type");
    const plotLike = t === "plot";
    $("#wzRooms").hidden = plotLike;
    const quick = $("#wzSizeQuick");
    const sizes = t === "flat"
      ? [["800", "sqft"], ["1000", "sqft"], ["1200", "sqft"], ["1500", "sqft"], ["2000", "sqft"]]
      : [["3", "marla"], ["5", "marla"], ["7", "marla"], ["10", "marla"], ["1", "kanal"], ["2", "kanal"]];
    quick.innerHTML = sizes.map(([n, u]) =>
      `<button type="button" class="chip" data-size="${n}" data-unit="${u}">${n} ${u === "sqft" ? "sq ft" : u[0].toUpperCase() + u.slice(1)}</button>`).join("");
    if (t === "flat" && !$("#wzSize").value) $("#unit-sqft").checked = true;
  }
  $$('[name="property_type"]').forEach(r => r.addEventListener("change", onTypeChange));
  $("#wzSizeQuick").addEventListener("click", e => {
    const b = e.target.closest("[data-size]");
    if (!b) return;
    $("#wzSize").value = b.dataset.size;
    $(`#unit-${b.dataset.unit}`).checked = true;
    $$("#wzSizeQuick .chip").forEach(c => c.classList.toggle("on", c === b));
  });

  /* ---------- Purpose: sale vs rent ---------- */
  function onPurposeChange() {
    const rent = val("purpose") === "rent";
    $("#wzPriceQ").textContent = rent ? "What's the monthly rent?" : "What's the asking price?";
    if (!$("#wzPriceAmount").value) $(rent ? "#pu-thousand" : "#pu-lakh").checked = true;
    updatePrice();
  }
  $$('[name="purpose"]').forEach(r => r.addEventListener("change", onPurposeChange));

  /* ---------- Area picker ---------- */
  const areaInput = $("#wzArea");
  function renderAreas() {
    const names = areasByCity[$("#wzCity").value] || [];
    const q = areaInput.value.trim().toLowerCase();
    const matches = q ? names.filter(n => n.toLowerCase().includes(q)) : names;
    const exact = names.some(n => n.toLowerCase() === q);
    $("#wzAreaList").innerHTML = (exact ? [] : matches.slice(0, q ? 10 : 14)).map(n =>
      `<button type="button" class="chip" data-area="${n.replace(/"/g, "&quot;")}">${n.replace(/</g, "&lt;")}</button>`).join("");
  }
  areaInput.addEventListener("input", renderAreas);
  $("#wzCity").addEventListener("change", renderAreas);
  $("#wzAreaList").addEventListener("click", e => {
    const b = e.target.closest("[data-area]");
    if (!b) return;
    areaInput.value = b.dataset.area;
    renderAreas();
    setTimeout(() => show(current + 1), 150);
  });

  /* ---------- Steppers ---------- */
  $$(".stepper").forEach(st => st.addEventListener("click", e => {
    const b = e.target.closest("[data-d]");
    if (!b) return;
    const input = $("#" + st.dataset.target);
    input.value = Math.max(0, Math.min(20, (+input.value || 0) + +b.dataset.d)) || "";
  }));

  /* ---------- Price ---------- */
  const amount = $("#wzPriceAmount"), hidden = $("#wzPrice");
  function unit() { return +((form.querySelector('[name="_price_unit"]:checked') || {}).value || 1); }
  function updatePrice() {
    const n = parseFloat(amount.value.replace(/,/g, ""));
    const rupees = isFinite(n) && n > 0 ? Math.round(n * unit()) : "";
    hidden.value = rupees;
    const rent = val("purpose") === "rent";
    $("#wzPriceRead").innerHTML = rupees
      ? `Rs <strong>${pkr(rupees)}</strong>${rent ? " / month" : ""} <span class="text-muted">(${rupees.toLocaleString("en-PK")})</span>`
      : "&nbsp;";
  }
  amount.addEventListener("input", updatePrice);
  $$('[name="_price_unit"]').forEach(r => r.addEventListener("change", updatePrice));
  (function initPrice() {
    const p = +hidden.value;
    if (!p) return;
    const u = p >= 1e7 ? 1e7 : p >= 1e5 ? 1e5 : 1e3;
    $(`[name="_price_unit"][value="${u}"]`).checked = true;
    amount.value = +(p / u).toFixed(3);
  })();

  /* ---------- Photos ---------- */
  const photos = []; // {blob, url}
  const MAX_EDGE = 1600;

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }
  async function shrink(file) {
    try {
      const img = await loadImage(file);
      const scale = Math.min(1, MAX_EDGE / Math.max(img.naturalWidth, img.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.naturalWidth * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(img.src);
      const blob = await new Promise(r => canvas.toBlob(r, "image/jpeg", 0.85));
      return blob || file;
    } catch (e) {
      return file; // The server shrinks it instead.
    }
  }
  async function addFiles(files) {
    for (const file of files) {
      if (photos.length >= maxPhotos) { flash(`Up to ${maxPhotos} photos.`); break; }
      if (!file.type.startsWith("image/")) continue;
      const slot = { blob: null, url: "", busy: true };
      photos.push(slot);
      renderPhotos();
      slot.blob = await shrink(file);
      slot.url = URL.createObjectURL(slot.blob);
      slot.busy = false;
      renderPhotos();
    }
  }
  function renderPhotos() {
    $("#wzPhotos").innerHTML = photos.map((p, i) => `
      <div class="photo ${i === 0 ? "cover" : ""}" data-i="${i}">
        ${p.busy ? '<div class="photo-busy">…</div>' : `<img src="${p.url}" alt="Photo ${i + 1}">`}
        ${i === 0 && !editing ? '<span class="photo-tag">Cover</span>' : ""}
        <button type="button" class="photo-x" data-remove="${i}" aria-label="Remove photo">×</button>
      </div>`).join("");
    $("#wzPhotoCount").textContent = photos.length ? `${photos.length} photo(s) ready` : "";
  }
  ["#wzCamera", "#wzGallery"].forEach(sel => $(sel).addEventListener("change", e => {
    addFiles([...e.target.files]);
    e.target.value = "";
  }));
  $("#wzPhotos").addEventListener("click", e => {
    const rm = e.target.closest("[data-remove]");
    if (rm) {
      const [gone] = photos.splice(+rm.dataset.remove, 1);
      if (gone && gone.url) URL.revokeObjectURL(gone.url);
      return renderPhotos();
    }
    const tile = e.target.closest(".photo");
    if (tile && +tile.dataset.i > 0) {
      photos.unshift(...photos.splice(+tile.dataset.i, 1));
      renderPhotos();
    }
  });

  /* ---------- Features ---------- */
  let extra = 0;
  function addFeature() {
    const input = $("#wzFeatureNew");
    const text = input.value.trim();
    if (!text) return;
    const id = "feat-new" + ++extra;
    $("#wzFeatures").insertAdjacentHTML("beforeend",
      `<input type="checkbox" class="btn-check" name="feature" id="${id}" checked><label class="chip" for="${id}"></label>`);
    $("#" + id).value = text;
    $(`label[for="${id}"]`).textContent = text;
    input.value = "";
  }
  $("#wzFeatureAdd").addEventListener("click", addFeature);
  $("#wzFeatureNew").addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); addFeature(); } });

  /* ---------- Summary + auto title ---------- */
  function autoTitle() {
    const t = val("property_type"), size = $("#wzSize").value, u = val("size_unit");
    const unitName = { marla: "Marla", kanal: "Kanal", sqft: "Sq. ft" }[u] || "";
    let name = typeLabel();
    if (t === "plot") name = "Residential Plot";
    const beds = $("#wzBeds").value;
    const lead = t === "flat" && beds ? `${beds} Bed` : size ? `${size} ${unitName}` : "";
    return [lead, name].filter(Boolean).join(" ") + (val("purpose") === "rent" ? " for Rent" : "");
  }
  function refreshSummary() {
    const title = $("#wzTitle").value.trim() || autoTitle();
    $("#wzAutoTitle").textContent = `"${autoTitle()}"`;
    $("#wzSumTitle").textContent = title;
    const city = $("#wzCity").selectedOptions[0];
    $("#wzSumLoc").textContent = [$("#wzBlock").value, areaInput.value, city && city.textContent].filter(Boolean).join(", ");
    const p = +hidden.value;
    $("#wzSumPrice").textContent = p ? `Rs ${pkr(p)}${val("purpose") === "rent" ? " / month" : ""}` : "Price on request";
    const cover = photos.find(x => x.url);
    $("#wzSumImg").style.backgroundImage = cover ? `url(${cover.url})` : "";
    $("#wzSumImg").classList.toggle("empty", !cover);
  }
  $("#wzTitle").addEventListener("input", refreshSummary);

  /* ---------- Save ---------- */
  // The web server accepts about 10 MB per request, so photos go up in batches of at most ~7 MB.
  const BATCH_BYTES = 7 * 1024 * 1024;
  function batches(list) {
    const out = [[]];
    let size = 0;
    for (const p of list) {
      if (size + p.blob.size > BATCH_BYTES && out[out.length - 1].length) { out.push([]); size = 0; }
      out[out.length - 1].push(p);
      size += p.blob.size;
    }
    return out;
  }
  const totalBytes = photos_ => photos_.reduce((n, p) => n + p.blob.size, 0) || 1;

  function post(url, data, onProgress) {
    return new Promise(resolve => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url);
      xhr.setRequestHeader("X-Requested-With", "fetch");
      xhr.upload.onprogress = ev => { if (ev.lengthComputable) onProgress(ev.loaded); };
      xhr.onload = () => {
        let res = {};
        try { res = JSON.parse(xhr.responseText); } catch (err) { /* not JSON */ }
        resolve({ status: xhr.status, res });
      };
      xhr.onerror = () => resolve({ status: 0, res: {} });
      xhr.send(data);
    });
  }

  function showErrors(errors) {
    const msgs = [];
    let firstStep = null;
    for (const [field, errs] of Object.entries(errors)) {
      errs.forEach(er => msgs.push(er.message));
      const idx = steps.findIndex(s => (s.dataset.fields || "").split(" ").includes(field));
      if (idx >= 0 && (firstStep === null || idx < firstStep)) firstStep = idx;
    }
    $("#wzErrors").innerHTML = msgs.map(m => `<div>${m.replace(/</g, "&lt;")}</div>`).join("");
    $("#wzErrors").hidden = false;
    if (firstStep !== null) show(firstStep);
  }

  let saving = false;
  form.addEventListener("submit", async e => {
    e.preventDefault();
    if (saving) return;
    if (!val("property_type")) { show(0); return flash("Pick the type of property."); }
    if (photos.some(p => p.busy)) return flash("Photos are still being prepared, one moment.");
    saving = true;
    const groups = batches(photos);
    const all = totalBytes(photos);
    let sent = 0;
    const bar = loaded => { $("#wzUpBar").style.width = Math.max(5, Math.min(100, ((sent + loaded) / all) * 100)) + "%"; };

    const overlay = $("#wzUploading");
    overlay.hidden = false;
    $("#wzUpText").textContent = photos.length ? `Uploading ${photos.length} photo(s)…` : "Saving…";
    bar(0);

    const data = new FormData(form);
    data.delete("_price_unit");
    groups[0].forEach((p, i) => data.append("photos", p.blob, `photo-${i + 1}.jpg`));
    const first = await post(form.action, data, bar);
    if (!(first.status === 200 && first.res.ok)) {
      overlay.hidden = true;
      saving = false;
      if (first.res.errors) return showErrors(first.res.errors);
      if (first.status === 413) return flash("The photos are too big to send. Remove a few and add them after saving.");
      if (first.status === 0) return flash("No connection. Your listing is still here: tap Save again when you have signal.");
      return flash("Couldn't save. Tap Save again. Nothing is lost.");
    }
    sent += groups[0].reduce((n, p) => n + p.blob.size, 0);

    // The listing exists now; the rest of the photos are added to it.
    let failed = 0;
    for (const group of groups.slice(1)) {
      const more = new FormData();
      more.append("csrfmiddlewaretoken", form.querySelector("[name=csrfmiddlewaretoken]").value);
      group.forEach((p, i) => more.append("photos", p.blob, `photo-${i + 1}.jpg`));
      const r = await post(first.res.url + "photos/", more, bar);
      if (r.status !== 200) failed += group.length;
      sent += group.reduce((n, p) => n + p.blob.size, 0);
    }
    window.location = first.res.url + (failed ? `?photos_failed=${failed}` : "");
  });

  onTypeChange();
  if (!editing && !$("#wzPriceAmount").value) onPurposeChange(); else updatePrice();
  renderAreas();
  // When editing, or when the type is already known (e.g. from a lead), start on the next step.
  show(!editing && val("property_type") && $("#wzForm [name=lead]") ? 1 : 0);
})();

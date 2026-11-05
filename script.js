const WA_ICON = '<svg viewBox="0 0 24 24" width="18" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .2-3.3-.7-2.8-1.1-4.5-3.9-4.7-4.1-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.3 0 .5l-.4.6c-.2.2-.3.4-.1.7.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.4 2.4 1.5.3.1.5.1.7-.1l.9-1.1c.2-.3.4-.2.7-.1l2 .9c.3.1.5.2.5.3.1.2.1.7-.1 1.3z"/></svg>';
(() => {
  const S = window.SITE || {};
  const $ = (q, el = document) => el.querySelector(q);
  const $$ = (q, el = document) => [...el.querySelectorAll(q)];
  /* Pakistani formats: 2.45 Crore, 85 Lakh, Rs 1,25,000; and Marla / Kanal sizes */
  const trim = n => (+n.toFixed(2)).toString();
  const money = n => n >= 1e7 ? `PKR ${trim(n / 1e7)} Crore` : n >= 1e5 ? `PKR ${trim(n / 1e5)} Lakh` : rupees(n);
  const rupees = n => "Rs " + Math.round(n).toLocaleString("en-IN");
  const size = p => p.sqft ? `<b>${p.sqft.toLocaleString()}</b> sq ft`
    : !p.marla ? "" : p.marla >= 20 ? `<b>${trim(p.marla / 20)}</b> Kanal` : `<b>${p.marla}</b> Marla`;
  const specs = p => {
    const parts = [];
    if (p.beds) parts.push(`<b>${p.beds}</b> Beds`);
    if (p.baths) parts.push(`<b>${p.baths}</b> Baths`);
    if (size(p)) parts.push(size(p));
    if (!p.beds && p.type === "plot") parts.push("Residential plot");
    if (!p.beds && p.type === "commercial") parts.push("Commercial");
    return parts.map(x => `<span>${x}</span>`).join("");
  };
  // Price with "on request" and monthly rent handled (listings from the CRM can be rentals).
  const price = p => !p.price ? "Price on request" : money(p.price) + (p.purpose === "rent" ? " /month" : "");
  const waLink = text => `https://wa.me/${S.whatsapp}?text=${encodeURIComponent(text || S.whatsappGreeting || "")}`;

  /* ---------- Fill business details from config.js ---------- */
  $$("[data-site]").forEach(el => {
    const key = el.dataset.site;
    if (key === "phone") { el.textContent = S.phoneDisplay; if (el.tagName === "A") el.href = `tel:+${S.phoneIntl}`; }
    else if (key === "phone-link") el.href = `tel:+${S.phoneIntl}`;
    else if (key === "email") { el.textContent = S.email; el.href = `mailto:${S.email}`; }
    else if (key === "email-link") el.href = `mailto:${S.email}`;
    else if (key === "address") el.innerHTML = S.addressLines.join("<br>");
    else if (key === "address-inline") el.textContent = S.addressLines.join(", ");
    else if (key === "whatsapp") el.href = waLink(el.dataset.waText);
    else if (key === "map") el.src = `https://maps.google.com/maps?q=${encodeURIComponent(S.mapQuery)}&z=15&output=embed`;
    else if (key === "directions") el.href = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(S.mapQuery)}`;
    else if (key === "hours") el.innerHTML = S.hours.map(([d, h]) => `<li><span>${d}</span><b>${h}</b></li>`).join("");
    else if (key === "name-text") el.textContent = S.name;
    else if (key === "google") el.href = S.googleProfile;
    else if (key === "google-review") el.href = S.googleReview || S.googleProfile;
    else if (key === "facebook" && S.facebook) el.href = S.facebook;
    else if (key === "instagram" && S.instagram) el.href = S.instagram;
    else if (key === "messenger" && (S.messenger || S.facebook)) el.href = S.messenger || S.facebook;
    else if (key === "year") el.textContent = new Date().getFullYear();
  });

  /* ---------- Header + mobile menu ---------- */
  const header = $("#header");
  const onScroll = () => header && header.classList.toggle("scrolled", scrollY > 20);
  addEventListener("scroll", onScroll, { passive: true }); onScroll();
  const toggle = $("#menuToggle"), links = $("#navLinks");
  toggle?.addEventListener("click", () => { toggle.classList.toggle("open"); links.classList.toggle("open"); });
  $$("#navLinks a").forEach(a => a.addEventListener("click", () => { toggle?.classList.remove("open"); links?.classList.remove("open"); }));

  /* ---------- Scroll reveal ---------- */
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.remove("pending"); io.unobserve(e.target); }
  }), { threshold: 0.12 });
  $$(".reveal").forEach((el, i) => {
    if (el.getBoundingClientRect().top < innerHeight) return;
    el.classList.add("pending"); el.style.transitionDelay = `${(i % 4) * 80}ms`; io.observe(el);
  });

  /* ---------- Animated counters ---------- */
  const countIO = new IntersectionObserver(entries => entries.forEach(e => {
    if (!e.isIntersecting) return;
    const el = e.target, end = +el.dataset.count, pre = el.dataset.prefix || "", suf = el.dataset.suffix || "";
    const t0 = performance.now();
    const step = t => {
      const p = Math.min((t - t0) / 1600, 1), v = Math.round(end * (1 - Math.pow(1 - p, 3)));
      el.textContent = pre + v.toLocaleString() + suf;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step); countIO.unobserve(el);
  }), { threshold: 0.5 });
  $$("[data-count]").forEach(el => {
    el.textContent = (el.dataset.prefix || "") + (+el.dataset.count).toLocaleString() + (el.dataset.suffix || "");
    countIO.observe(el);
  });

  /* ---------- 3D tilt on hero card ---------- */
  const card = $("#heroCard");
  if (card && matchMedia("(hover: hover)").matches) {
    const wrap = card.parentElement;
    wrap.addEventListener("mousemove", e => {
      const r = wrap.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
      card.style.transform = `rotateY(${x * 10}deg) rotateX(${-y * 10}deg)`;
    });
    wrap.addEventListener("mouseleave", () => card.style.transform = "");
  }

  /* ---------- Listings ---------- */
  const grid = $("#listingGrid");
  const state = { type: "all", maxPrice: 0, location: "" };
  const favs = new Set(JSON.parse((() => { try { return localStorage.getItem("hk-favs"); } catch { return null; } })() || "[]"));
  const pin = '<svg viewBox="0 0 24 24"><path d="M12 22s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/></svg>';
  const heart = '<svg viewBox="0 0 24 24"><path d="M12 21s-8-5.2-8-11.2A4.8 4.8 0 0 1 12 7a4.8 4.8 0 0 1 8 2.8C20 15.8 12 21 12 21z"/></svg>';

  function renderListings() {
    if (!grid) return;
    const items = (window.LISTINGS || []).filter(p =>
      (state.type === "all" || p.type === state.type) &&
      (!state.maxPrice || p.price <= state.maxPrice) &&
      (!state.location || (p.location + " " + p.title).toLowerCase().includes(state.location)));
    grid.innerHTML = items.map((p, i) => `
      <article class="listing" data-id="${p.id}" style="animation-delay:${i * 70}ms">
        <div class="listing-img">
          <div class="img" style="--img:url('${p.img}')"></div>
          <span class="badge ${p.hot ? "hot" : ""}">${p.badge || p.type}</span>
          <button class="fav ${favs.has(p.id) ? "on" : ""}" data-fav="${p.id}" aria-label="Save">${heart}</button>
          <span class="price-tag">${price(p)}</span>
        </div>
        <div class="listing-body">
          <h3>${p.title}</h3>
          <p class="loc">${pin}${p.location}</p>
          <div class="specs">
            ${specs(p)}
          </div>
        </div>
      </article>`).join("");
    $("#emptyMsg").hidden = items.length > 0;
  }
  renderListings();

  grid?.addEventListener("click", e => {
    const fav = e.target.closest("[data-fav]");
    if (fav) {
      e.stopPropagation();
      const id = fav.dataset.fav;
      favs.has(id) ? favs.delete(id) : favs.add(id);
      fav.classList.toggle("on");
      try { localStorage.setItem("hk-favs", JSON.stringify([...favs])); } catch {}
      return;
    }
    const card = e.target.closest(".listing");
    if (card) openModal(card.dataset.id);
  });

  $$("#filters .chip").forEach(chip => chip.addEventListener("click", () => {
    $$("#filters .chip").forEach(c => c.classList.remove("active"));
    chip.classList.add("active");
    state.type = chip.dataset.filter;
    renderListings();
  }));

  /* Hero search: Buy mode filters listings, Sell mode jumps to valuation */
  let mode = "buy";
  $$("#modeSeg button").forEach(b => b.addEventListener("click", () => {
    $$("#modeSeg button").forEach(x => x.classList.remove("active"));
    b.classList.add("active"); mode = b.dataset.mode;
    $("#searchForm .search-btn span").textContent = mode === "buy" ? "Search" : "Value my home";
  }));
  $("#searchForm")?.addEventListener("submit", e => {
    e.preventDefault();
    if (mode === "sell") {
      const addr = $("#sLocation").value;
      if (addr) $('#valuationForm [name="address"]').value = addr;
      $("#sell").scrollIntoView(); return;
    }
    state.location = $("#sLocation").value.trim().toLowerCase();
    state.type = $("#sType").value;
    state.maxPrice = +$("#sPrice").value;
    $$("#filters .chip").forEach(c => c.classList.toggle("active", c.dataset.filter === state.type));
    renderListings();
    $("#listings").scrollIntoView();
  });

  /* ---------- Property modal ---------- */
  const modal = $("#modal");
  function openModal(id) {
    const p = window.LISTINGS.find(x => x.id === id);
    if (!p) return;
    const waText = `Hi! I'm interested in "${p.title}" (${p.id}) in ${p.location}, listed at ${price(p)}. Is it still available?`;
    $("#modalBody").innerHTML = `
      ${(p.imgs && p.imgs.length > 1)
        ? `<div class="modal-gallery">${p.imgs.map(u => `<div class="modal-img img" style="--img:url('${u}')"></div>`).join("")}</div>`
        : `<div class="modal-img img" style="--img:url('${p.img}')"></div>`}
      <div class="modal-content">
        <div class="modal-top">
          <div><p class="mono muted">LISTING #${p.id}</p><h3 style="font-size:1.6rem;margin:.3rem 0">${p.title}</h3><p class="loc">${pin}${p.location}</p></div>
          <p class="hc-price grad">${price(p)}</p>
        </div>
        <div class="specs">
          ${specs(p)}
        </div>
        <p class="desc">${p.desc || ""}</p>
        <div class="feature-list">${(p.features || []).map(f => `<span>${f}</span>`).join("")}</div>
        <div class="modal-actions">
          <a class="btn btn-whatsapp" target="_blank" rel="noopener" href="${waLink(waText)}">${WA_ICON} Ask on WhatsApp</a>
          <a class="btn btn-primary" href="contact.html?property=${encodeURIComponent(p.id + " – " + p.title)}">Book a viewing</a>
          <a class="btn btn-ghost" href="tel:+${S.phoneIntl}">Call ${S.phoneDisplay}</a>
        </div>
      </div>`;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
  }
  const closeModal = () => { if (modal) { modal.hidden = true; document.body.style.overflow = ""; } };
  $("#modalClose")?.addEventListener("click", closeModal);
  modal?.addEventListener("click", e => { if (e.target === modal) closeModal(); });
  addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

  /* ---------- Tabs (process) ---------- */
  $$("#processSeg button").forEach(b => b.addEventListener("click", () => {
    $$("#processSeg button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    $$("[data-panel]").forEach(p => { p.hidden = p.dataset.panel !== b.dataset.tab; p.querySelectorAll(".reveal").forEach(r => r.classList.remove("pending")); });
  }));

  /* ---------- Range sliders fill ---------- */
  const fill = r => r.style.setProperty("--fill", ((r.value - r.min) / (r.max - r.min)) * 100 + "%");

  /* ---------- Mortgage calculator ---------- */
  const m = id => $("#" + id);
  function calcMortgage() {
    if (!m("mPrice")) return;
    const price = +m("mPrice").value, down = +m("mDown").value, rate = +m("mRate").value, years = +m("mTerm").value;
    const loan = price * (1 - down / 100), r = rate / 100 / 12, n = years * 12;
    const pay = r ? loan * r / (1 - Math.pow(1 + r, -n)) : loan / n;
    m("oPrice").textContent = money(price);
    m("oDown").textContent = `${down}% · ${money(price * down / 100)}`;
    m("oRate").textContent = rate.toFixed(2) + "%";
    m("oTerm").textContent = years + " yrs";
    m("mResult").textContent = rupees(pay) + "/mo";
    ["mPrice", "mDown", "mRate", "mTerm"].forEach(id => fill(m(id)));
  }
  ["mPrice", "mDown", "mRate", "mTerm"].forEach(id => m(id)?.addEventListener("input", calcMortgage));
  calcMortgage();

  /* ---------- Instant estimate (ballpark rates per marla live in config.js) ---------- */
  const eArea = m("eArea");
  if (eArea && S.estimateAreas) {
    eArea.innerHTML = S.estimateAreas.map(([name, rate], i) => `<option value="${rate}"${i === 0 ? " selected" : ""}>${name}</option>`).join("");
  }
  function calcEstimate() {
    if (!eArea) return;
    const marla = Math.max(+m("eSize").value || 0, 0) * +m("eUnit").value;
    const v = marla * +eArea.value * +m("eType").value * +m("ePos").value;
    const lo = money(v * 0.9), hi = money(v * 1.1), unit = lo.split(" ").pop();
    m("eResult").textContent = !marla ? "-" : unit === hi.split(" ").pop()
      ? `${lo.replace(" " + unit, "")} – ${hi.replace("PKR ", "")}` : `${lo} – ${hi.replace("PKR ", "")}`;
  }
  ["eSize", "eUnit", "eArea", "eType", "ePos"].forEach(id => m(id)?.addEventListener("input", calcEstimate));
  calcEstimate();

  /* ---------- Forms ---------- */
  $$("form[data-form]").forEach(form => form.addEventListener("submit", async e => {
    e.preventDefault();
    const btn = form.querySelector("button[type=submit]"), ok = form.querySelector(".form-success");
    const data = new FormData(form);
    data.append("form_type", form.dataset.form === "valuation" ? "Valuation request" : "Contact message");
    data.append("_subject", form.dataset.form === "valuation" ? "New valuation request from website" : "New message from website");
    btn.disabled = true; btn.style.opacity = .6;
    try {
      if (S.formEndpoint) {
        const res = await fetch(S.formEndpoint, { method: "POST", body: data, headers: { Accept: "application/json" } });
        if (!res.ok) throw new Error();
      }
      form.reset(); ok.hidden = false; ok.textContent = ok.dataset.ok || ok.textContent;
    } catch {
      ok.hidden = false; ok.style.color = "#f87171";
      ok.textContent = `Sorry, something went wrong. Please call ${S.phoneDisplay} or message us on WhatsApp.`;
    } finally { btn.disabled = false; btn.style.opacity = ""; }
  }));

  /* Contact form: "Send via WhatsApp" composes the message from the form fields */
  const waBtn = $("#sendWhatsApp"), cf = $("#contactForm");
  const syncWa = () => {
    const get = n => (cf.elements[n]?.value || "").trim();
    const lines = [`Hi ${S.name}!`, get("message") || "I'd like some help with a property.", "",
      get("name") && `Name: ${get("name")}`, get("interest") && `Interest: ${get("interest")}`,
      get("property") && `Property: ${get("property")}`].filter(Boolean);
    waBtn.href = waLink(lines.join("\n"));
  };
  if (waBtn && cf) { cf.addEventListener("input", syncWa); cf.addEventListener("change", syncWa); syncWa(); }

  /* Pre-fill property on contact page (from "Book a viewing") */
  const prop = new URLSearchParams(location.search).get("property");
  if (prop && $("#contactForm")) {
    const f = $("#contactForm");
    if (f.elements.property) f.elements.property.value = prop;
    if (f.elements.message) f.elements.message.value = `I'd like to book a viewing for ${prop}.`;
    if (waBtn) syncWa();
  }
})();

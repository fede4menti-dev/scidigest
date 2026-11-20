/* SciDigest website: settings, accounts and sync, topics, saved papers, reading history,
   sharing, citations and offline support. No AI is used here: changing settings only
   re-sorts papers that were already published, so it never costs anything. */
(function () {
  "use strict";
  var C = window.SCIDIGEST || {};
  var ROOT = C.root || "";
  var TOPICS = C.topics || {};
  var STATE_KEY = "scidigest-v1", ACCOUNT_KEY = "scidigest-account", FLASH_KEY = "scidigest-flash";
  var LIMITS = { read: 500, saved: 300, ideas: 25 };
  function qkey(q) { return String(q || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim(); }

  // ------------------------------------------------------------- storage
  function load(key) { try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (e) { return null; } }
  function save(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {} }
  function forget(key) { try { localStorage.removeItem(key); } catch (e) {} }

  function defaults() {
    return { topics: [], theme: "", size: "m", saver: false, motion: false, dimread: true,
             ideaUrl: "", ideaToken: "", saved: {}, read: {}, ideas: [], updated: 0 };
  }

  var S = load(STATE_KEY);
  if (!S) {                         // first visit, or migrate settings from the previous version
    S = defaults();
    var legacy = function (k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
    if (legacy("scidigest-topics")) S.topics = legacy("scidigest-topics").split(",").filter(Boolean);
    S.theme = legacy("scidigest-theme");
    S.ideaUrl = legacy("scidigest-idea-url");
    S.ideaToken = legacy("scidigest-idea-token");
    save(STATE_KEY, S);
  }
  S = Object.assign(defaults(), S);
  S.topics = (S.topics || []).filter(function (t) { return TOPICS[t]; });

  var account = load(ACCOUNT_KEY);   // {token, email, lastSync}

  function trim() {
    var keys = Object.keys(S.read).sort(function (a, b) { return S.read[b] - S.read[a]; });
    keys.slice(LIMITS.read).forEach(function (k) { delete S.read[k]; });
    var sk = Object.keys(S.saved).sort(function (a, b) { return (S.saved[b].at || 0) - (S.saved[a].at || 0); });
    sk.slice(LIMITS.saved).forEach(function (k) { delete S.saved[k]; });
    S.ideas = (S.ideas || []).slice(0, LIMITS.ideas);
  }

  function commit(opts) {
    trim();
    S.updated = Date.now();
    save(STATE_KEY, S);
    if (!(opts && opts.noSync)) scheduleSync();
  }

  function server() { return (S.ideaUrl || C.ideaUrl || "").replace(/\/+$/, ""); }

  // ------------------------------------------------------------- appearance
  function applyLook() {
    var h = document.documentElement;
    if (S.theme) h.dataset.theme = S.theme; else delete h.dataset.theme;
    if (S.size && S.size !== "m") h.dataset.size = S.size; else delete h.dataset.size;
    if (S.motion) h.dataset.motion = "reduce"; else delete h.dataset.motion;
    if (S.saver) h.dataset.saver = "1"; else delete h.dataset.saver;
    if (S.dimread) h.dataset.dimread = "1"; else delete h.dataset.dimread;
  }
  applyLook();

  // ------------------------------------------------------------- helpers
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return [].slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  // App-style pop-up instead of the browser's alert/confirm. Tapping outside or Esc closes it.
  function modal(title, message, okLabel, cancelLabel, danger) {
    return new Promise(function (resolve) {
      var d = el("dialog", "mini"), body = el("div", "mb"), foot = el("div", "mf");
      body.appendChild(el("h2", null, title)); if (message) body.appendChild(el("p", null, message));
      if (cancelLabel) { var c = el("button", "secondary", cancelLabel); c.type = "button"; c.onclick = function () { done(false); }; foot.appendChild(c); }
      var ok = el("button", "primary" + (danger ? " danger" : ""), okLabel || "OK"); ok.type = "button"; ok.onclick = function () { done(true); }; foot.appendChild(ok);
      d.appendChild(body); d.appendChild(foot); document.body.appendChild(d);
      function done(v) { if (d.open) d.close(); d.parentNode && d.parentNode.removeChild(d); resolve(v); }
      d.addEventListener("cancel", function (e) { e.preventDefault(); done(false); });
      d.addEventListener("click", function (e) { if (e.target === d) done(false); });
      d.showModal(); ok.focus();
    });
  }
  function ask(title, message, okLabel, danger) { return modal(title, message, okLabel, "Cancel", danger); }
  function tell(title, message) { return modal(title, message, "OK"); }

  function toast(msg) {
    var old = $(".toast"); if (old) old.remove();
    var t = el("div", "toast", msg); t.setAttribute("role", "status");
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 3200);
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    var ta = el("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
    return Promise.resolve();
  }

  function api(path, method, body) {
    var url = server();
    if (!url) return Promise.reject(new Error("Add your SciDigest server address under “Server for Idea Check and accounts” first."));
    var headers = { "Content-Type": "application/json" };
    if (account && account.token) headers.Authorization = "Bearer " + account.token;
    return fetch(url + path, { method: method || "GET", headers: headers, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) { var e = new Error(d.error || ("Server error " + r.status)); e.status = r.status; throw e; }
          return d;
        });
      }, function () { throw new Error("Couldn't reach the server. Check your connection and the server address."); });
  }

  // ------------------------------------------------------------- sync
  function syncable() {
    return { topics: S.topics, theme: S.theme, size: S.size, saver: S.saver, motion: S.motion, dimread: S.dimread,
             saved: S.saved, read: S.read, ideas: S.ideas, updated: S.updated };
  }

  var syncTimer;
  function scheduleSync() {
    if (!account) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(pushNow, 1500);       // batch quick changes into one request
  }

  function pushNow() {
    if (!account) return Promise.resolve();
    return api("/me/data", "PUT", { data: syncable() }).then(function () {
      account.lastSync = Date.now(); save(ACCOUNT_KEY, account); renderAccount();
    }, function (e) {
      if (e.status === 401) { account = null; forget(ACCOUNT_KEY); renderAccount(); toast("Please sign in again to keep syncing."); }
    });
  }

  function merge(remote) {
    remote = remote || {};
    var newer = (remote.updated || 0) > (S.updated || 0);
    if (newer) ["topics", "theme", "size", "saver", "motion", "dimread"].forEach(function (k) { if (k in remote) S[k] = remote[k]; });
    S.saved = Object.assign({}, remote.saved || {}, S.saved);
    S.read = Object.assign({}, remote.read || {}, S.read);
    var seen = {}, ideas = [];
    (S.ideas || []).concat(remote.ideas || []).sort(function (a, b) { return (b.at || 0) - (a.at || 0); })
      .forEach(function (i) { var k = qkey(i.q); if (!seen[k]) { seen[k] = 1; ideas.push(i); } });
    S.ideas = ideas;
    S.topics = (S.topics || []).filter(function (t) { return TOPICS[t]; });
  }

  function signedIn(result, message) {
    account = { token: result.token, email: result.account.email, lastSync: Date.now() };
    save(ACCOUNT_KEY, account);
    merge(result.account.data);
    commit({ noSync: true });
    return pushNow().then(function () {
      try { sessionStorage.setItem(FLASH_KEY, message); } catch (e) {}
      location.reload();
    });
  }

  // On load: quietly pull changes made on other devices (at most every 10 minutes).
  function pullIfStale() {
    if (!account || !server()) return;
    if (Date.now() - (account.lastSync || 0) < 600000) return;
    api("/me").then(function (me) {
      var before = JSON.stringify(syncable());
      merge(me.data); commit({ noSync: true });
      account.lastSync = Date.now(); save(ACCOUNT_KEY, account);
      if (JSON.stringify(syncable()) !== before) { applyLook(); pushNow(); }
    }, function (e) { if (e.status === 401) { account = null; forget(ACCOUNT_KEY); } });
  }

  // ------------------------------------------------------------- account UI
  var acctMode = "signin";
  function renderAccount() {
    var box = $("#account-box"); if (!box) return;
    box.innerHTML = "";
    var wrap = el("div", "acct"); box.appendChild(wrap);

    if (account) {
      var who = el("div", "who"), av = el("div", "av", (account.email || "?")[0].toUpperCase()), t = el("div");
      t.appendChild(el("div", "em", account.email));
      t.appendChild(el("div", "st", account.lastSync ? "Synced " + new Date(account.lastSync).toLocaleString() : "Signed in"));
      who.appendChild(av); who.appendChild(t); wrap.appendChild(who);
      wrap.appendChild(el("p", "help", "Your topics, settings, saved papers, reading history and idea checks are saved to your account and sync to every device where you sign in."));
      var row = el("div", "btnlist");
      var syncBtn = el("button", "listbtn", "Sync now"); syncBtn.type = "button";
      syncBtn.onclick = function () { syncBtn.disabled = true; pushNow().then(function () { syncBtn.disabled = false; toast("Synced"); }); };
      var out = el("button", "listbtn", "Sign out"); out.type = "button";
      out.onclick = function () { account = null; forget(ACCOUNT_KEY); renderAccount(); toast("Signed out. Your settings stay on this device."); };
      var del = el("button", "listbtn danger", "Delete account"); del.type = "button";
      del.onclick = function () { acctMode = "delete"; renderDelete(wrap); };
      row.appendChild(syncBtn); row.appendChild(out); row.appendChild(del); wrap.appendChild(row);
      return;
    }

    if (!server()) {
      wrap.appendChild(el("p", "help", "Create an account to save your topics, saved papers and idea checks and use them on all your devices. Accounts need the SciDigest server: add its address below under “Server for Idea Check and accounts”. Until then, everything is saved in this browser."));
      return;
    }

    var tabs = el("div", "seg"), modes = [["signin", "Sign in"], ["signup", "Create account"]];
    modes.forEach(function (m) {
      var l = el("label"), i = el("input"); i.type = "radio"; i.name = "acctmode"; i.checked = acctMode === m[0];
      i.onchange = function () { acctMode = m[0]; renderAccount(); };
      l.appendChild(i); l.appendChild(document.createTextNode(m[1])); tabs.appendChild(l);
    });
    if (acctMode === "signin" || acctMode === "signup") wrap.appendChild(tabs);

    var form = el("form", "acct"); form.noValidate = true; wrap.appendChild(form);
    function field(label, type, name, auto) {
      var f = el("label", "field"); f.appendChild(el("span", null, label));
      var i = el("input"); i.type = type; i.name = name; i.autocomplete = auto; i.required = true; f.appendChild(i); form.appendChild(f); return i;
    }
    var msg = el("div", "msg hidden");
    function show(text, ok) { msg.textContent = text; msg.className = "msg " + (ok ? "ok" : "err"); }

    if (acctMode === "reset") {
      var em = field("Email", "email", "email", "email"), code = field("Recovery code", "text", "code", "one-time-code"),
          pw = field("New password (8+ characters)", "password", "new", "new-password");
      form.appendChild(msg);
      var go = el("button", "primary", "Reset password"); go.type = "submit"; form.appendChild(go);
      var back = el("button", "linkbtn", "Back to sign in"); back.type = "button"; back.onclick = function () { acctMode = "signin"; renderAccount(); };
      form.appendChild(back);
      form.onsubmit = function (ev) {
        ev.preventDefault(); go.disabled = true;
        api("/auth/reset", "POST", { email: em.value, recovery_code: code.value, new_password: pw.value })
          .then(function (r) { showCode(wrap, r, "Password changed. You're signed in."); }, function (e) { show(e.message); go.disabled = false; });
      };
      return;
    }

    var email = field("Email", "email", "email", "email");
    var pass = field(acctMode === "signup" ? "Password (8+ characters)" : "Password", "password", "password",
                     acctMode === "signup" ? "new-password" : "current-password");
    form.appendChild(msg);
    var submit = el("button", "primary", acctMode === "signup" ? "Create account" : "Sign in"); submit.type = "submit";
    form.appendChild(submit);
    if (acctMode === "signin") {
      var forgot = el("button", "linkbtn", "Forgot password?"); forgot.type = "button";
      forgot.onclick = function () { acctMode = "reset"; renderAccount(); }; form.appendChild(forgot);
    } else {
      form.appendChild(el("p", "help", "Your settings, saved papers and idea checks on this device will be copied to the new account. Your password is stored only as a secure hash."));
    }
    form.onsubmit = function (ev) {
      ev.preventDefault();
      if (!email.value || !pass.value) { show("Enter your email and password."); return; }
      submit.disabled = true;
      if (acctMode === "signup") {
        api("/auth/signup", "POST", { email: email.value, password: pass.value, data: syncable() })
          .then(function (r) { showCode(wrap, r, "Account created. You're signed in."); }, function (e) { show(e.message); submit.disabled = false; });
      } else {
        api("/auth/login", "POST", { email: email.value, password: pass.value })
          .then(function (r) { return signedIn(r, "Signed in. Your settings are synced."); }, function (e) { show(e.message); submit.disabled = false; });
      }
    };
  }

  function showCode(wrap, result, message) {
    wrap.innerHTML = "";
    wrap.appendChild(el("p", "msg ok", message));
    wrap.appendChild(el("p", "help", "Save this recovery code somewhere safe. It's the only way to reset your password if you forget it, and it won't be shown again."));
    var code = el("div", "code", result.recovery_code); wrap.appendChild(code);
    var row = el("div", "btnlist");
    var c = el("button", "listbtn", "Copy recovery code"); c.type = "button";
    c.onclick = function () { copy(result.recovery_code).then(function () { toast("Recovery code copied"); }); };
    var done = el("button", "primary", "I've saved it"); done.type = "button";
    done.onclick = function () { signedIn(result, message); };
    row.appendChild(c); row.appendChild(done); wrap.appendChild(row);
  }

  function renderDelete(wrap) {
    wrap.innerHTML = "";
    wrap.appendChild(el("p", "help", "Deleting your account permanently removes it and everything synced to it from the server. Your settings on this device stay. Enter your password to confirm."));
    var f = el("label", "field"); f.appendChild(el("span", null, "Password"));
    var pw = el("input"); pw.type = "password"; pw.autocomplete = "current-password"; f.appendChild(pw); wrap.appendChild(f);
    var msg = el("div", "msg hidden"); wrap.appendChild(msg);
    var row = el("div", "btnlist");
    var go = el("button", "listbtn danger", "Delete my account permanently"); go.type = "button";
    var cancel = el("button", "listbtn", "Cancel"); cancel.type = "button";
    cancel.onclick = function () { acctMode = "signin"; renderAccount(); };
    go.onclick = function () {
      go.disabled = true;
      api("/me/delete", "POST", { password: pw.value }).then(function () {
        account = null; forget(ACCOUNT_KEY); renderAccount(); toast("Your account was deleted.");
      }, function (e) { msg.textContent = e.message; msg.className = "msg err"; go.disabled = false; });
    };
    row.appendChild(go); row.appendChild(cancel); wrap.appendChild(row);
  }

  // ------------------------------------------------------------- settings sheet
  var dlg = $("#settings");
  if (dlg) {
    var boxes = $$("input[name=topic]", dlg), all = $("#all-topics");
    var syncAll = function () {
      all.checked = !boxes.some(function (b) { return b.checked; });
      $$(".selgroup", dlg).forEach(function (btn) {
        var g = boxes.filter(function (b) { return b.dataset.group === btn.dataset.group; });
        btn.textContent = g.every(function (b) { return b.checked; }) ? "Clear" : "Select all";
      });
    };
    var open = function () {
      boxes.forEach(function (b) { b.checked = S.topics.indexOf(b.value) >= 0; });
      $$("input[name=theme]", dlg).forEach(function (r) { r.checked = r.value === (S.theme || ""); });
      $$("input[name=size]", dlg).forEach(function (r) { r.checked = r.value === (S.size || "m"); });
      $("#opt-saver").checked = !!S.saver; $("#opt-motion").checked = !!S.motion; $("#opt-dimread").checked = !!S.dimread;
      $("#idea-url").value = S.ideaUrl || ""; $("#idea-token").value = S.ideaToken || "";
      syncAll(); acctMode = "signin"; renderAccount();
      dlg.showModal();
      var c = $(".content", dlg); if (c) c.scrollTop = 0;
    };
    boxes.forEach(function (b) { b.addEventListener("change", syncAll); });
    all.addEventListener("change", function () { if (all.checked) boxes.forEach(function (b) { b.checked = false; }); syncAll(); });
    $$(".selgroup", dlg).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var g = boxes.filter(function (b) { return b.dataset.group === btn.dataset.group; }), on = !g.every(function (b) { return b.checked; });
        g.forEach(function (b) { b.checked = on; }); syncAll();
      });
    });
    // Appearance and reading options preview instantly.
    $$("input[name=theme], input[name=size], #opt-saver, #opt-motion, #opt-dimread", dlg).forEach(function (i) {
      i.addEventListener("change", function () {
        var prev = { theme: S.theme, size: S.size, saver: S.saver, motion: S.motion, dimread: S.dimread };
        readLook(); applyLook(); Object.assign(S, prev);   // preview only; Save keeps it
      });
    });
    function readLook() {
      var th = $("input[name=theme]:checked", dlg), sz = $("input[name=size]:checked", dlg);
      S.theme = th ? th.value : ""; S.size = sz ? sz.value : "m";
      S.saver = $("#opt-saver").checked; S.motion = $("#opt-motion").checked; S.dimread = $("#opt-dimread").checked;
    }
    $$("[data-close]", dlg).forEach(function (b) { b.addEventListener("click", function () { dlg.close(); applyLook(); }); });
    dlg.addEventListener("cancel", function () { applyLook(); });
    dlg.addEventListener("click", function (ev) { if (ev.target === dlg) { dlg.close(); applyLook(); } });

    $("#save-settings").addEventListener("click", function () {
      var before = S.topics.join(",");
      S.topics = boxes.filter(function (b) { return b.checked; }).map(function (b) { return b.value; });
      readLook();
      S.ideaUrl = $("#idea-url").value.trim(); S.ideaToken = $("#idea-token").value.trim();
      commit();
      var msg = S.topics.join(",") !== before
        ? (S.topics.length ? "Saved. Every day and review now shows your topics first." : "Saved. Showing all topics.")
        : "Settings saved.";
      try { sessionStorage.setItem(FLASH_KEY, msg); } catch (e) {}
      // Let a pending sync go out before reloading.
      (account ? pushNow() : Promise.resolve()).then(function () { location.reload(); });
    });

    $("#export-data").addEventListener("click", function () {
      var blob = new Blob([JSON.stringify({ exported: new Date().toISOString(), account: account ? account.email : null, data: syncable() }, null, 2)],
                          { type: "application/json" });
      var a = el("a"); a.href = URL.createObjectURL(blob); a.download = "scidigest-my-data.json";
      document.body.appendChild(a); a.click(); a.remove();
    });
    $("#clear-history").addEventListener("click", function () {
      ask("Clear history?", "Remove your saved papers, reading history and idea checks?" + (account ? " This also clears them from your account." : ""), "Clear", true)
        .then(function (yes) { if (!yes) return; S.saved = {}; S.read = {}; S.ideas = []; commit(); markCards(); toast("Cleared."); });
    });
    $("#reset-all").addEventListener("click", function () {
      ask("Reset this device?", "This resets all settings on this device and signs you out. Your account, if you have one, is not deleted.", "Reset", true)
        .then(function (yes) {
          if (!yes) return;
          forget(STATE_KEY); forget(ACCOUNT_KEY);
          try { sessionStorage.setItem(FLASH_KEY, "Everything on this device was reset."); } catch (e) {}
          location.reload();
        });
    });
    $("#install-help").addEventListener("click", function () {
      tell("Add to your home screen", "iPhone or iPad: open this site in Safari, tap the Share button, then \u201cAdd to Home Screen\u201d.\n\nAndroid: open the browser menu (\u22ee), then \u201cInstall app\u201d or \u201cAdd to Home screen\u201d.\n\nComputer (Chrome or Edge): click the install icon at the right of the address bar.");
    });

    $$("[data-open-settings]").forEach(function (b) { b.addEventListener("click", open); });
  }

  // ------------------------------------------------------------- "your topics" bar
  function topicSummary() {
    if (!S.topics.length) return "All topics";
    var n = S.topics.map(function (t) { return TOPICS[t]; });
    return n.length <= 2 ? n.join(", ") : n[0] + ", " + n[1] + " +" + (n.length - 2);
  }
  $$(".mytopics").forEach(function (b) {
    $(".t", b).textContent = S.topics.length ? "Your topics" : "Showing all topics";
    $(".s", b).textContent = topicSummary();
    $(".act", b).textContent = S.topics.length ? "Edit" : "Choose topics";
  });

  // ------------------------------------------------------------- report pages
  var main = $("main[data-report]");
  if (main && S.topics.length) {
    var cards = $$("details.card", main);
    var mine = cards.filter(function (c) { return S.topics.indexOf(c.dataset.topic) >= 0; });
    mine.sort(function (a, b) {
      var ea = a.dataset.editors === "1", eb = b.dataset.editors === "1";
      if (ea !== eb) return ea ? -1 : 1;
      return ea ? (+a.dataset.rank - +b.dataset.rank) : (+b.dataset.score - +a.dataset.score);
    });
    var sec = el("section"), grid = el("div", "grid");
    sec.appendChild(el("h2", null, "For you"));
    if (mine.length) { mine.forEach(function (c) { grid.appendChild(c); }); sec.appendChild(grid); }
    else sec.appendChild(el("p", "sub", "Nothing new in your topics in this report. Here are the other highlights instead."));
    main.insertBefore(sec, main.firstChild);
    var eh = $("h2.editors", main), eg = $(".editors-grid", main);
    if (eh) { if (eg && eg.children.length) eh.textContent = "Also worth reading"; else { eh.classList.add("hidden"); if (eg) eg.classList.add("hidden"); } }
    $$(".topic-section", main).forEach(function (s) { if (!$("details.card", s)) s.classList.add("hidden"); });
    var bt = $("h2.by-topic", main); if (bt && !$(".topic-section:not(.hidden)", main)) bt.classList.add("hidden");
    var chips = $(".chips"); if (chips) chips.classList.add("hidden");
  }

  function cardInfo(c) {
    return { h: c.dataset.headline, u: c.dataset.url, c: c.dataset.cite, t: c.dataset.topicname, j: c.dataset.journal,
             d: c.dataset.date, r: c.dataset.report, i: c.dataset.image, at: Date.now() };
  }
  function markCards() {
    $$("details.card").forEach(function (c) {
      c.classList.toggle("is-saved", !!S.saved[c.dataset.key]);
      c.classList.toggle("is-read", !!S.read[c.dataset.key]);
      var b = $(".act[data-act=save] span", c); if (b) b.textContent = S.saved[c.dataset.key] ? "Saved" : "Save";
    });
  }
  markCards();
  $$("details.card").forEach(function (c) {
    c.addEventListener("toggle", function () {
      if (c.open && !S.read[c.dataset.key]) { S.read[c.dataset.key] = Date.now(); commit(); c.classList.add("is-read"); }
    });
  });
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest && ev.target.closest(".act[data-act]"); if (!btn) return;
    var c = btn.closest("details.card"); if (!c) return;
    var k = c.dataset.key, act = btn.dataset.act;
    if (act === "save") {
      if (S.saved[k]) { delete S.saved[k]; toast("Removed from Saved"); } else { S.saved[k] = cardInfo(c); toast("Saved. Find it in the Saved tab."); }
      commit(); markCards();
    } else if (act === "cite") {
      copy(c.dataset.cite).then(function () { toast("Citation copied (APA)"); });
    } else if (act === "share") {
      var link = new URL(ROOT + c.dataset.report, location.href).href;
      if (navigator.share) navigator.share({ title: c.dataset.headline, text: c.dataset.headline, url: link }).catch(function () {});
      else copy(link).then(function () { toast("Link copied"); });
    }
  });
  // Tapping outside an expanded card (or pressing Esc) closes it, like a pop-up.
  function closeCards(except) {
    $$("details.card[open]").forEach(function (c) { if (c !== except) { c.open = false; c.classList.toggle("open", false); } });
  }
  document.addEventListener("click", function (ev) {
    if (!$("details.card[open]")) return;
    var t = ev.target;
    var inCard = t.closest && t.closest("details.card");
    if (inCard) { if (t.closest("summary")) closeCards(inCard); return; }   // opening one card closes the others
    if (t.closest && (t.closest("dialog") || t.closest(".tabbar") || t.closest(".topbar"))) return;
    closeCards();
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !$("dialog[open]")) closeCards();
  });

  // Open the card a shared link points to.
  if (location.hash && /^#p\d+$/.test(location.hash)) {
    var target = $(location.hash);
    if (target && target.tagName === "DETAILS") { target.open = true; target.classList.add("open"); setTimeout(function () { target.scrollIntoView({ block: "start" }); }, 50); }
  }

  // ------------------------------------------------------------- shared API for other pages
  window.SciDigestApp = {
    state: S, commit: commit, server: server, token: function () { return S.ideaToken; },
    toast: toast, copy: copy, el: el, ask: ask, tell: tell,
    addIdea: function (entry) {
      S.ideas = [entry].concat((S.ideas || []).filter(function (i) { return qkey(i.q) !== qkey(entry.q); }));
      commit();
    },
  };
  document.dispatchEvent(new Event("scidigest:ready"));

  // ------------------------------------------------------------- flash + sync + offline
  var flash = ""; try { flash = sessionStorage.getItem(FLASH_KEY) || ""; sessionStorage.removeItem(FLASH_KEY); } catch (e) {}
  if (flash) toast(flash);
  pullIfStale();
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register(ROOT + "sw.js").catch(function () {});
  }
})();

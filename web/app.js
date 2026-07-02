"use strict";

const S = { alarmes: [], page: "home", logs: [] };
let jarvis = null;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");

let _toastTimer = null;
function toast(msg, dur = 2200) {
  const t = $("toast");
  t.textContent = msg; t.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => t.classList.remove("show"), dur);
}

document.addEventListener("DOMContentLoaded", () => {
  if (typeof QWebChannel === "undefined") return inicializarUI(null);
  new QWebChannel(qt.webChannelTransport, (ch) => {
    jarvis = ch.objects.bridge;
    if (jarvis.dados_para_ui) jarvis.dados_para_ui.connect((raw) => receberDoBackend(raw));
    inicializarUI(jarvis);
  });
  document.querySelectorAll(".dia-btn").forEach(b => {
    b.addEventListener("click", () => b.classList.toggle("sel"));
  });
});

function inicializarUI(jv) {
  if (jv?.obter_configuracoes_atuais) {
    jv.obter_configuracoes_atuais((raw) => {
      try {
        const c = JSON.parse(raw);
        val("cfg-nome", c.nome_mestre || "");
        val("cfg-cidade", c.cidade_padrao || "");
        val("cfg-gemini", c.gemini || "");
        val("cfg-qwen", c.qwen || "");
        val("cfg-voz", c.voz || "");
        val("cfg-owm", c.openweather_api_key || "");
        val("cfg-sp-id", c.spotify_id || "");
        val("cfg-sp-sec", c.spotify_sec || "");
        val("cfg-st", c.smartthings || "");
        val("cfg-tg", c.telegram_token || "");
        val("cfg-tg-auth", c.telegram_auth_token || "");
        val("cfg-dg", c.deepgram_api_key || "");
        val("cfg-news", c.news_ativo !== false ? "true" : "false");
        val("cfg-briefing", c.briefing_auto !== false ? "true" : "false");
        val("cfg-pomodoro", c.pomodoro_padrao || "25");
        val("cfg-email-ativo", c.email_ativo !== false ? "true" : "false");
        val("cfg-email-host", c.email_imap_host || "");
        val("cfg-email-user", c.email_user || "");
        val("cfg-email-pass", c.email_pass || "");
        val("cfg-cal-ativo", c.calendar_ativo !== false ? "true" : "false");
        val("cfg-cal-ics", c.calendar_ics_path || "");
        val("mail-host", c.email_imap_host || "");
        val("mail-user", c.email_user || "");
        val("mail-pass", c.email_pass || "");
        setWhisper(c.whisper_model);
        setSelect("cfg-whisper-device", c.whisper_device);
        setSelect("cfg-whisper-compute", c.whisper_compute);
        atualizarStatusIA(c);
      } catch (e) {}
    });
  }
  carregarAlarmes();
  adicionarLog("sistema", "Painel JARVIS inicializado.");
  adicionarLog("info", "Aguardando conexão com LM Studio...");
}

function val(id, v) { const el = $(id); if (el) el.value = v; }
function setWhisper(m) {
  const s = $("cfg-whisper");
  if (!s || !m) return;
  [...s.options].forEach(o => { o.selected = o.value === m; });
}
function setSelect(id, v) {
  const s = $(id);
  if (!s || !v) return;
  [...s.options].forEach(o => { o.selected = o.value === v; });
}

window.receberDoJarvis = function (raw) { receberDoBackend(raw); };


function adicionarLog(tipo, msg) {
  const agora = new Date();
  const h = String(agora.getHours()).padStart(2,"0");
  const m = String(agora.getMinutes()).padStart(2,"0");
  const s = String(agora.getSeconds()).padStart(2,"0");
  const hora = `${h}:${m}:${s}`;
  S.logs.push({ tipo, msg, hora });
  if (S.logs.length > 200) S.logs.splice(0, S.logs.length - 200);
  if (S.page === "home") renderLog();
}

function renderLog() {
  const wrap = $("hm-log");
  if (!wrap) return;
  const ultimos = S.logs.slice(-80);
  wrap.innerHTML = ultimos.map(e =>
    `<div class="log-entry type-${e.tipo}"><span class="log-time">[${e.hora}]</span><span class="log-icon">▸</span><span class="log-msg">${esc(e.msg)}</span></div>`
  ).join("");
  wrap.scrollTop = wrap.scrollHeight;
}


function receberDoBackend(raw) {
  let d;
  try { d = typeof raw === "string" ? JSON.parse(raw) : raw; } catch (e) { return; }

  if (d.bateria_ausente === true) {
    const card = $("hm-card-bat");
    if (card) card.style.display = "none";
  }
  if (d.cpu !== undefined) atualizarHomeMetrics(d);
  if (d.bateria !== undefined) {
    const card = $("hm-card-bat");
    if (card) card.style.display = "";
    setText("hm-bat", Math.round(d.bateria));
    setBar("hm-bar-bat", d.bateria);
    setText("hm-pct-bat", Math.round(d.bateria) + "%");
  }
  if (d.gpu !== undefined) {
    setText("hm-gpu", Math.round(d.gpu));
    setBar("hm-bar-gpu", d.gpu);
    setText("hm-pct-gpu", Math.round(d.gpu) + "%");
  }
  if (d.disco !== undefined) {
    setText("hm-disk", Math.round(d.disco));
    setBar("hm-bar-disk", d.disco);
    setText("hm-pct-disk", Math.round(d.disco) + "%");
  }
  if (d.resposta) {
    adicionarMsg("ai", d.resposta);
    adicionarLog("comando", "Resposta: " + d.resposta.slice(0, 80));
  }
  if (d.alarmes !== undefined) {
    try { S.alarmes = Array.isArray(d.alarmes) ? d.alarmes : JSON.parse(d.alarmes); } catch (e) {}
    if (S.page === "alarms") renderAlarmes();
  }
  if (d.clima_dados !== undefined) renderClima(d.clima_dados, d.cidade_buscada);
  if (d.ia_status) atualizarStatusIA(d.ia_status);
  if (d.eventos !== undefined) {
    try { S.eventos = Array.isArray(d.eventos) ? d.eventos : JSON.parse(d.eventos); } catch (e) {}
    if (S.page === "calendar") renderEventos();
  }
  if (d.emails !== undefined) {
    try { S.emails = Array.isArray(d.emails) ? d.emails : JSON.parse(d.emails); } catch (e) {}
    if (S.page === "email") renderEmails();
  }
  if (d.resposta && d.resposta.toLowerCase().includes("evento")) {
    if (S.page === "calendar") setTimeout(carregarEventos, 500);
  }
  if (d.lm_status !== undefined) atualizarLMStatus(d.lm_status);
  if (d.uptime !== undefined) setText("hm-uptime", "⏱ ATIVO: " + (d.uptime || "--"));
  if (d.internet !== undefined) {
    const el = $("hm-internet");
    if (el) {
      el.textContent = "🌐 REDE: " + (d.internet ? "ONLINE" : "OFFLINE");
      el.classList.toggle("online", !!d.internet);
    }
  }
  if (d.logs && Array.isArray(d.logs)) {
    d.logs.forEach(l => adicionarLog(l.tipo || "info", l.msg));
  }
  if (d.voz_speaking !== undefined) {
    const w = $("wave"), body = document.body;
    if (d.voz_speaking) {
      w && w.classList.remove("hidden");
      body.classList.add("speaking");
      document.querySelector("#orb")?.classList.add("active");
      document.querySelector("#radar-scan")?.classList.add("active");
    } else {
      w && w.classList.add("hidden");
      body.classList.remove("speaking");
      document.querySelector("#orb")?.classList.remove("active");
      document.querySelector("#radar-scan")?.classList.remove("active");
    }
  }
  if (d.sentinela) atualizarSentinela(d.sentinela);
}

function atualizarHomeMetrics(d) {
  const metricas = [
    { val: "hm-cpu", bar: "hm-bar-cpu", pct: "hm-pct-cpu", v: d.cpu, suf: "%" },
    { val: "hm-ram", bar: "hm-bar-ram", pct: "hm-pct-ram", v: d.ram, suf: "%" },
  ];
  metricas.forEach(m => {
    if (m.v !== undefined) {
      const r = Math.round(m.v);
      setText(m.val, r); setBar(m.bar, r); setText(m.pct, r + m.suf);
    }
  });
  if (d.temp !== undefined) {
    setText("hm-temp", Math.round(d.temp));
    setBar("hm-bar-temp", Math.min(100, d.temp * 2));
    setText("hm-pct-temp", Math.round(d.temp) + "°C");
  }
}


function atualizarSentinela(s) {
  if (s.dispositivos_rede) {
    setText("sec-dev-count", s.dispositivos_rede.length);
    const list = s.dispositivos_rede.slice(0, 8);
    $("sec-dev-list").innerHTML = list.map(d =>
      `<div class="sec-entry"><span class="sec-entry-ip">${esc(d.ip)}</span><span class="sec-entry-mac">${esc(d.mac)}</span></div>`
    ).join("") + (s.dispositivos_rede.length > 8 ? `<div class="sec-entry muted">+${s.dispositivos_rede.length - 8} mais</div>` : "");
  }
  if (s.trackers) {
    setText("sec-trk-count", s.trackers.length);
    $("sec-trk-list").innerHTML = s.trackers.slice(0, 5).map(t =>
      `<div class="sec-entry warn"><span class="sec-entry-ip">${esc(t.ip)}</span><span class="sec-entry-host">${esc(t.host)}</span></div>`
    ).join("") + (s.trackers.length > 5 ? `<div class="sec-entry muted">+${s.trackers.length - 5} mais</div>` : "");
  }
  if (s.conexoes) {
    setText("sec-con-count", s.conexoes.suspeitas?.length || 0);
    $("sec-con-list").innerHTML = (s.conexoes.suspeitas || []).slice(0, 5).map(c =>
      `<div class="sec-entry danger"><span class="sec-entry-ip">${esc(c.ip)}:${c.porta}</span><span class="sec-entry-proc">${esc(c.processo)}</span></div>`
    ).join("") + ((s.conexoes.suspeitas?.length || 0) > 5 ? `<div class="sec-entry muted">+${s.conexoes.suspeitas.length - 5} mais</div>` : "");
    if (!s.conexoes.suspeitas?.length) $("sec-con-list").innerHTML = '<div class="sec-entry ok">✓ Nenhuma conexão suspeita</div>';
  }
  if (s.firewall) {
    const ativo = s.firewall.ativo;
    const el = $("sec-fw-status");
    if (el) {
      el.textContent = ativo ? "ATIVO" : "INATIVO";
      el.className = "sec-count " + (ativo ? "online" : "offline");
    }
    setText("sec-fw-label", ativo ? "protegido" : "sem proteção");
    $("sec-fw-list").innerHTML = (s.firewall.regras || []).slice(0, 3).map(r =>
      `<div class="sec-entry"><span class="sec-entry-rule">${esc(r.nome || r.linha || "")}</span></div>`
    ).join("") + ((s.firewall.regras?.length || 0) > 3 ? `<div class="sec-entry muted">+${s.firewall.regras.length - 3} regras</div>` : "");
  }
  setText("sec-status", "◉ MONITORANDO");
  $("sec-status").className = "online";
}

function atualizarLMStatus(status) {
  const el = $("hm-lm-status"), topbar = $("topbar-metrics");
  if (el) {
    if (status === true || status === "online") {
      el.textContent = "\u25C9 LM STUDIO ONLINE";
      el.className = "online";
      adicionarLog("ok", "LM Studio operacional.");
    } else {
      el.textContent = "\u25C9 SEM OPERA\u00C7\u00C3O \u2014 SISTEMA FORA DE TRABALHO";
      el.className = "offline";
      adicionarLog("erro", "LM Studio offline ou sem resposta.");
    }
  }
  if (topbar) {
    const ok = (status === true || status === "online");
    topbar.textContent = ok ? "SISTEMA ONLINE" : "SISTEMA OFFLINE";
    topbar.className = ok ? "online" : "offline";
  }
}

window.toggleSentinela = function(ligado) {
  if (jarvis?.alternar_sentinela) {
    jarvis.alternar_sentinela(ligado ? "ativar" : "desativar");
  }
  const status = $("sec-status");
  if (status) {
    status.textContent = ligado ? "MONITORANDO" : "DESATIVADO";
    status.className = ligado ? "online" : "offline";
  }
  if (ligado) {
    adicionarLog("sistema", "Sentinela ativado pelo painel.");
  } else {
    adicionarLog("sistema", "Sentinela desativado pelo painel.");
  }
};

function setText(id, v) { const e = $(id); if (e) e.textContent = v; }
function setBar(id, pct) { const e = $(id); if (e) e.style.width = Math.min(100, pct) + "%"; }

function atualizarStatusIA(s) {
  const label = $("ia-label"), dot = $("ia-dot"), info = $("st-ia-info");
  if (!s) return;
  const modelo = s.modelo || s.ia_mode || "";
  const ok = !!modelo;
  if (label) label.textContent = modelo.toUpperCase() || "OFFLINE";
  if (dot) dot.classList.toggle("online", ok);
  if (info) info.textContent = ok ? `Modelo: ${modelo} | ${s.servidor ? "ONLINE" : "local"}` : "Nenhum modelo detectado.";
  if (ok) atualizarLMStatus("online");
  else atualizarLMStatus(false);
}


function goTo(name) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  const page = $("page-" + name), nav = document.querySelector(`.nav-item[data-s="${name}"]`);
  if (page) page.classList.add("active");
  if (nav) nav.classList.add("active");
  const titles = { home:"INÍCIO", chat:"CHAT", alarms:"ALARMES", weather:"CLIMA", calendar:"CALENDÁRIO", email:"EMAIL", config:"CONFIG", library:"BIBLIOTECA" };
  setText("topbar-title", titles[name] || name.toUpperCase());
  S.page = name;
  if (name === "home") renderLog();
  if (name === "alarms") renderAlarmes();
  if (name === "weather") renderClimaVazio();
  if (name === "library") renderLib();
  if (name === "calendar") { definirDataHoje(); carregarEventos(); }
  if (name === "email") { carregarConfigEmail(); }
}
window.goTo = goTo;

window.ocultarPainel = function () { jarvis?.ocultar_painel?.(); };


function enviarChat() {
  const inp = $("chat-in"), txt = inp.value.trim();
  if (!txt) return;
  adicionarMsg("user", txt);
  inp.value = ""; inp.style.height = "auto";
  adicionarLog("comando", "Comando: " + txt);
  if (jarvis?.executar_comando) jarvis.executar_comando(txt);
}
window.enviarChat = enviarChat;

$("chat-in")?.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarChat(); }
});
$("chat-in")?.addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 120) + "px";
});

function adicionarMsg(role, texto) {
  const msgs = $("chat-msgs");
  if (!msgs) return;
  const div = document.createElement("div");
  div.className = "msg " + (role === "user" ? "user" : "ai");
  div.innerHTML = `<div class="avatar">${role === "user" ? "D" : "J"}</div><div class="bubble">${esc(texto)}</div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}


function carregarAlarmes() {
  if (!jarvis?.obter_alarmes) return;
  jarvis.obter_alarmes((raw) => {
    try {
      const lista = JSON.parse(raw);
      if (Array.isArray(lista)) S.alarmes = lista;
      if (S.page === "alarms") renderAlarmes();
    } catch (e) {}
  });
}

function renderAlarmes() {
  const wrap = $("alarm-list");
  if (!wrap) return;
  const todos = [...S.alarmes.filter(a => a.status === "pendente"), ...S.alarmes.filter(a => a.status !== "pendente")];
  if (!todos.length) { wrap.innerHTML = '<div class="empty-state">⏰ Nenhum alarme cadastrado.</div>'; return; }
  const DIAS = ["Seg","Ter","Qua","Qui","Sex","Sáb","Dom"];
  wrap.innerHTML = todos.map(a => {
    const ok = a.status === "pendente";
    const diasStr = a.dias_semana?.length ? a.dias_semana.map(d => DIAS[d]).join(" · ") : (a.data || "");
    const badges = [diasStr ? `<span class="badge">${esc(diasStr)}</span>` : "", a.repetir ? `<span class="badge rep">↺ REPETIR</span>` : "", !ok ? `<span class="badge done">✓ CONCLUÍDO</span>` : ""].join("");
    return `<div class="alarm-item ${ok ? "" : "done"}"><div class="alm-time">${esc(a.hora || "--:--")}</div><div class="alm-info"><div class="alm-mission">${esc(a.missao || "Alarme")}</div><div class="alm-meta">${badges}</div></div>${ok ? `<div class="alm-actions"><button class="alm-btn snooze" title="Soneca 10min" onclick="snoozeAlarme('${a.hora}','${a.missao}')">💤</button><button class="alm-btn" title="Remover" onclick="deletarAlarme('${a.hora}','${a.missao}','${a.data||""}')">✕</button></div>` : ""}</div>`;
  }).join("");
}

function criarAlarme() {
  const hora = $("alm-hora")?.value?.trim() || "", missao = $("alm-missao")?.value?.trim() || "Alarme", data = $("alm-data")?.value || "", rep = $("alm-rep")?.checked || false;
  const dias = [...document.querySelectorAll(".dia-btn.sel")].map(b => parseInt(b.dataset.d));
  if (!hora) return toast("⚠ INFORME O HORÁRIO");
  const alarme = { hora, missao, status:"pendente", repetir:rep || dias.length > 0, criado_em:new Date().toISOString(), ultimo_disparo:null, data:data||null, dias_semana:dias.length ? dias : null };
  S.alarmes.push(alarme);
  if (jarvis?.salvar_alarme) { try { jarvis.salvar_alarme(JSON.stringify(alarme)); } catch (e) {} }
  if ($("alm-missao")) $("alm-missao").value = "";
  if ($("alm-data")) $("alm-data").value = "";
  if ($("alm-rep")) $("alm-rep").checked = false;
  document.querySelectorAll(".dia-btn.sel").forEach(b => b.classList.remove("sel"));
  toast("⏰ ALARME " + hora + " CRIADO");
  adicionarLog("comando", "Alarme criado: " + missao + " às " + hora);
  renderAlarmes();
}
window.criarAlarme = criarAlarme;

function deletarAlarme(hora, missao, data) {
  const idx = S.alarmes.findIndex(a => a.hora === hora && a.missao === missao && (a.data||"") === (data||""));
  if (idx >= 0) S.alarmes.splice(idx, 1);
  if (jarvis?.remover_alarme) { try { jarvis.remover_alarme(JSON.stringify({hora,missao,data:data||null})); } catch (e) {} }
  toast("ALARME REMOVIDO");
  renderAlarmes();
}
window.deletarAlarme = deletarAlarme;

function snoozeAlarme(hora, missao) {
  const nova = new Date(Date.now() + 10*60000), h = nova.toTimeString().slice(0,5), d = nova.toISOString().slice(0,10);
  const sn = { hora:h, missao:"💤 Soneca", status:"pendente", repetir:false, criado_em:new Date().toISOString(), ultimo_disparo:null, data:d, dias_semana:null };
  S.alarmes.push(sn);
  if (jarvis?.salvar_alarme) { try { jarvis.salvar_alarme(JSON.stringify(sn)); } catch (e) {} }
  toast("💤 SONECA: " + h);
  renderAlarmes();
}
window.snoozeAlarme = snoozeAlarme;

function limparConcluidos() {
  S.alarmes = S.alarmes.filter(a => a.status === "pendente");
  if (jarvis?.limpar_alarmes_concluidos) { try { jarvis.limpar_alarmes_concluidos(); } catch (e) {} }
  toast("CONCLUÍDOS REMOVIDOS");
  renderAlarmes();
}
window.limparConcluidos = limparConcluidos;


function buscarClima() {
  const cidade = $("wx-city")?.value?.trim() || "", res = $("wx-result");
  if (!res) return;
  res.innerHTML = '<div class="wx-card"><div class="wx-title">BUSCANDO...</div></div>';
  adicionarLog("comando", "Buscando clima: " + cidade);
  if (jarvis?.solicitar_clima) jarvis.solicitar_clima(cidade);
  else res.innerHTML = '<div class="wx-error">Backend não disponível.</div>';
}
window.buscarClima = buscarClima;

function renderClimaVazio() {
  const res = $("wx-result");
  if (res && !res.children.length) res.innerHTML = '<div class="empty-state">Digite uma cidade e clique em BUSCAR.</div>';
}

function renderClima(raw, cidade) {
  const res = $("wx-result");
  if (!res) return;
  try {
    const d = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!d || d.error) { res.innerHTML = `<div class="wx-error">⚠ ${esc(d?.error || "Dados indisponíveis.")}</div>`; return; }
    if (d.main && d.weather) {
      res.innerHTML = `<div class="wx-card"><div class="wx-title">${esc((d.name||cidade||"").toUpperCase())} · AGORA</div><div class="wx-temp">${Math.round(d.main.temp)}°C</div><div class="wx-desc">${esc(d.weather[0]?.description||"")}</div><div class="wx-grid"><div class="wx-cell"><div class="wx-cell-lbl">SENSAÇÃO</div><div class="wx-cell-val">${Math.round(d.main.feels_like)}°C</div></div><div class="wx-cell"><div class="wx-cell-lbl">UMIDADE</div><div class="wx-cell-val">${d.main.humidity}%</div></div><div class="wx-cell"><div class="wx-cell-lbl">VENTO</div><div class="wx-cell-val">${Math.round((d.wind?.speed||0)*3.6)} km/h</div></div></div></div>`;
      return;
    }
    res.innerHTML = '<div class="wx-error">Formato desconhecido.</div>';
  } catch (e) { res.innerHTML = `<div class="wx-error">Erro: ${esc(e.message)}</div>`; }
}


function definirDataHoje() {
  const hoje = new Date().toISOString().slice(0,10);
  if ($("cal-data") && !$("cal-data").value) $("cal-data").value = hoje;
  if ($("cal-filtro") && !$("cal-filtro").value) $("cal-filtro").value = hoje;
}

function adicionarEvento() {
  const titulo = $("cal-titulo")?.value?.trim();
  const data = $("cal-data")?.value;
  const hora = $("cal-hora")?.value || "";
  if (!titulo) return toast("⚠ DIGITE UM TÍTULO");
  if (!data) return toast("⚠ SELECIONE UMA DATA");
  const cmd = "adicionar evento " + titulo + " em " + data + (hora ? " as " + hora : "");
  if (jarvis?.executar_comando) jarvis.executar_comando(cmd);
  $("cal-titulo").value = "";
  adicionarLog("comando", "Evento: " + titulo + " em " + data);
  toast("📅 EVENTO ENVIADO");
}
window.adicionarEvento = adicionarEvento;

function carregarEventos() {
  const data = $("cal-filtro")?.value || new Date().toISOString().slice(0,10);
  if (jarvis?.obter_eventos_por_data) {
    jarvis.obter_eventos_por_data(data, (raw) => {
      try {
        S.eventos = JSON.parse(raw);
        if (Array.isArray(S.eventos)) renderEventos();
        else S.eventos = [];
      } catch (e) { S.eventos = []; }
      if (!S.eventos || !S.eventos.length) {
        $("cal-lista").innerHTML = `<div class="cal-empty">Nenhum evento para ${data}.</div>`;
      } else adicionarLog("info", S.eventos.length + " evento(s) carregado(s) para " + data);
    });
  } else $("cal-lista").innerHTML = '<div class="cal-empty">Backend não disponível.</div>';
}
window.carregarEventos = carregarEventos;

function renderEventos() {
  const wrap = $("cal-lista");
  if (!wrap) return;
  const data = $("cal-filtro")?.value || new Date().toISOString().slice(0,10);
  const eventos = S.eventos || [];
  const filtrados = eventos.filter(e => e.data === data);
  if (!filtrados.length) { wrap.innerHTML = `<div class="cal-empty">Nenhum evento para ${data}.</div>`; return; }
  wrap.innerHTML = filtrados.map(e =>
    `<div class="cal-item"><div class="cal-hora">${e.hora || "--:--"}</div><div class="cal-info"><div class="cal-titulo">${esc(e.titulo)}</div><div class="cal-data">${esc(e.data)}${e.fonte ? " · "+esc(e.fonte) : ""}</div></div><button class="cal-btn-rm" title="Remover" onclick="removerEvento('${esc(e.titulo)}','${e.data}')">✕</button></div>`
  ).join("");
}

function removerEvento(titulo, data) {
  if (!jarvis?.executar_comando) return;
  jarvis.executar_comando("remover evento " + titulo);
  adicionarLog("comando", "Removendo evento: " + titulo);
  toast("🗑 EVENTO REMOVIDO");
  setTimeout(carregarEventos, 800);
}
window.removerEvento = removerEvento;


function salvarConfigEmail() {
  const host = $("mail-host")?.value?.trim();
  const user = $("mail-user")?.value?.trim();
  const pass = $("mail-pass")?.value?.trim();
  if (jarvis?.salvar_configuracao) {
    if (host) jarvis.salvar_configuracao("email_imap_host", host);
    if (user) jarvis.salvar_configuracao("email_user", user);
    if (pass) jarvis.salvar_configuracao("email_pass", pass);
    toast("✉ CONFIGURAÇÃO SALVA");
    adicionarLog("sistema", "Configuração de email salva.");
  }
}
window.salvarConfigEmail = salvarConfigEmail;

function carregarConfigEmail() {
  if (jarvis?.obter_configuracoes_atuais) {
    jarvis.obter_configuracoes_atuais((raw) => {
      try {
        const c = JSON.parse(raw);
        val("mail-host", c.email_imap_host || "");
        val("mail-user", c.email_user || "");
        val("mail-pass", c.email_pass || "");
      } catch (e) {}
    });
  }
}

function verificarEmail() {
  const wrap = $("mail-lista");
  if (!wrap) return;
  wrap.innerHTML = '<div class="mail-empty">Verificando...</div>';
  adicionarLog("comando", "Verificando e-mails...");
  if (jarvis?.obter_emails) {
    jarvis.obter_emails((raw) => {
      try {
        S.emails = JSON.parse(raw);
        if (Array.isArray(S.emails)) renderEmails();
        else S.emails = [];
      } catch (e) { S.emails = []; }
      if (!S.emails || !S.emails.length) {
        wrap.innerHTML = '<div class="mail-empty">Nenhum e-mail não lido ou IMAP não configurado.</div>';
      } else adicionarLog("info", S.emails.length + " e-mail(s) não lido(s).");
    });
  } else wrap.innerHTML = '<div class="mail-empty">Backend não disponível.</div>';
}
window.verificarEmail = verificarEmail;

function renderEmails() {
  const wrap = $("mail-lista");
  if (!wrap) return;
  const emails = S.emails || [];
  if (!emails.length) { wrap.innerHTML = '<div class="mail-empty">Nenhum e-mail não lido.</div>'; return; }
  wrap.innerHTML = emails.map(e =>
    `<div class="mail-item"><div class="mail-assunto">${esc(e.assunto || e.subject || "(sem assunto)")}</div><div class="mail-remetente">${esc(e.de || e.from || "(remetente desconhecido)")}</div><div class="mail-data">${esc(e.data || e.date || "")}</div></div>`
  ).join("");
}


function salvarConfig(chave, inputId, btn) {
  const v = $(inputId)?.value?.trim();
  if (v === undefined || v === "") { toast("⚠ O campo não pode ficar vazio."); return; }
  if (btn) { btn.textContent = "✓"; setTimeout(() => btn.textContent = "SALVAR", 1500); }
  if (jarvis?.salvar_configuracao) jarvis.salvar_configuracao(chave, v);
  toast("SALVO: " + chave.toUpperCase());
  adicionarLog("sistema", "Config atualizada: " + chave);
}
window.salvarConfig = salvarConfig;

function testarVoz() {
  if (jarvis?.testar_voz_painel) jarvis.testar_voz_painel();
  toast("▶ TESTANDO VOZ...");
}
window.testarVoz = testarVoz;

function trocarIA(modo) {
  document.querySelectorAll(".btn-ia").forEach(b => b.classList.remove("active"));
  event?.target?.classList.add("active");
  if (jarvis?.alternar_ia) {
    jarvis.alternar_ia(modo, (raw) => {
      try { const r = JSON.parse(raw); atualizarStatusIA({modelo:r.modo,servidor:true}); toast("IA: "+r.modo.toUpperCase()); adicionarLog("sistema", "Modo IA alterado: "+r.modo); } catch (e) {}
    });
  }
}
window.trocarIA = trocarIA;


const BIBLIOTECA = [
  {cmd:"dormir",label:"DORMIR",cat:"Sistema"},
  {cmd:"boa noite",label:"BOA NOITE",cat:"Sistema"},
  {cmd:"silencio",label:"SILÊNCIO",cat:"Sistema"},
  {cmd:"bloquear",label:"BLOQUEAR TELA",cat:"Sistema"},
  {cmd:"minimizar",label:"MINIMIZAR",cat:"Sistema"},
  {cmd:"fechar",label:"FECHAR JANELA",cat:"Sistema"},
  {cmd:"screenshot",label:"SCREENSHOT",cat:"Sistema"},
  {cmd:"limpar lixeira",label:"LIMPAR LIXEIRA",cat:"Sistema"},
  {cmd:"trabalho",label:"MODO TRABALHO",cat:"Sistema"},
  {cmd:"foco 25",label:"FOCO / POMODORO",cat:"Sistema"},
  {cmd:"pausa 5",label:"PAUSA",cat:"Sistema"},
  {cmd:"parar foco",label:"PARAR FOCO",cat:"Sistema"},
  {cmd:"status foco",label:"STATUS FOCO",cat:"Sistema"},
  {cmd:"noticias",label:"NOTÍCIAS",cat:"Sistema"},
  {cmd:"briefing",label:"BRIEFING MATINAL",cat:"Sistema"},
  {cmd:"terminal dir",label:"TERMINAL",cat:"Sistema"},
  {cmd:"liga tv",label:"LIGAR TV",cat:"TV"},
  {cmd:"desligar tv",label:"DESLIGAR TV",cat:"TV"},
  {cmd:"youtube tv",label:"YOUTUBE NA TV",cat:"TV"},
  {cmd:"volume 40",label:"VOLUME TV",cat:"TV"},
  {cmd:"spotify",label:"TOCAR MÚSICA",cat:"Spotify"},
  {cmd:"playlist",label:"PLAYLIST",cat:"Spotify"},
  {cmd:"favoritas",label:"FAVORITAS",cat:"Spotify"},
  {cmd:"pausar",label:"PAUSAR",cat:"Spotify"},
  {cmd:"continuar",label:"CONTINUAR",cat:"Spotify"},
  {cmd:"proxima",label:"PRÓXIMA",cat:"Spotify"},
  {cmd:"anterior",label:"ANTERIOR",cat:"Spotify"},
  {cmd:"abrir youtube",label:"ABRIR YOUTUBE",cat:"Web"},
  {cmd:"pesquisar youtube",label:"PESQUISAR YT",cat:"Web"},
  {cmd:"pesquisar google",label:"PESQUISAR GOOGLE",cat:"Web"},
  {cmd:"monitorar tela",label:"MONITORAR TELA",cat:"Monitor"},
  {cmd:"desligar monitor",label:"DESLIGAR MONITOR",cat:"Monitor"},
  {cmd:"olha tela",label:"ANALISAR TELA",cat:"Monitor"},
  {cmd:"criar alarme",label:"CRIAR ALARME",cat:"Alarme"},
  {cmd:"parar alarme",label:"PARAR ALARME",cat:"Alarme"},
  {cmd:"acordei",label:"ACORDEI",cat:"Alarme"},
  {cmd:"eventos hoje",label:"EVENTOS HOJE",cat:"Sistema"},
  {cmd:"adicionar evento estudo amanhã 14h",label:"CRIAR EVENTO",cat:"Sistema"},
  {cmd:"email",label:"EMAIL",cat:"Sistema"},
  {cmd:"adicionar comando vscode como code",label:"COMANDO CUSTOM",cat:"Sistema"},
];

const CAT_ICON = {Sistema:"🖥",TV:"📺",Spotify:"🎵",Web:"🌐",Monitor:"👁",Alarme:"⏰"};

function filtrarLib() {
  const busca = ($("lib-busca")?.value || "").toLowerCase();
  const cat = $("lib-cat")?.value || "";
  renderLib(BIBLIOTECA.filter(c => (!cat || c.cat === cat) && (!busca || c.label.toLowerCase().includes(busca) || c.cmd.toLowerCase().includes(busca))));
}
window.filtrarLib = filtrarLib;

function renderLib(lista) {
  lista = lista ?? BIBLIOTECA;
  const wrap = $("lib-list");
  if (!wrap) return;
  if (!lista.length) { wrap.innerHTML = '<div class="empty-state">Nenhum comando encontrado.</div>'; return; }
  const grupos = {};
  lista.forEach(c => { if (!grupos[c.cat]) grupos[c.cat] = []; grupos[c.cat].push(c); });
  wrap.innerHTML = Object.entries(grupos).map(([cat, cmds]) =>
    `<div class="section-hdr" style="margin-top:12px"><h2>${CAT_ICON[cat]||"◇"} ${cat.toUpperCase()}</h2></div><div class="lib-grid">${cmds.map(c => `<div class="lib-card" onclick="executarCmd('${c.cmd}')"><div class="lib-label">${esc(c.label)}</div><div class="lib-exemplo">${esc(c.cmd)}</div></div>`).join("")}</div>`
  ).join("");
}
window.renderLib = renderLib;

function executarCmd(cmd) {
  goTo("chat");
  adicionarMsg("user", cmd);
  adicionarLog("comando", "Comando: " + cmd);
  if (jarvis?.executar_comando) jarvis.executar_comando(cmd);
}
window.executarCmd = executarCmd;
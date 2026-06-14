"use strict";

const S = {
     alarmes: [],
     page: "chat"
};
let jarvis = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

let _toastTimer = null;

function toast(msg, dur = 2200) {
     const t = $("toast");
     t.textContent = msg;
     t.classList.add("show");
     clearTimeout(_toastTimer);
     _toastTimer = setTimeout(() => t.classList.remove("show"), dur);
}

document.addEventListener("DOMContentLoaded", () => {
     if (typeof QWebChannel === "undefined") return inicializarUI(null);
     new QWebChannel(qt.webChannelTransport, (ch) => {
          jarvis = ch.objects.jarvis;
          if (jarvis.dados_para_ui) jarvis.dados_para_ui.connect((raw) => receberDoBackend(raw));
          inicializarUI(jarvis);
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
                    setWhisper(c.whisper_model);
                    atualizarStatusIA(c);
               } catch (e) { }
          });
     }
     carregarAlarmes();
}

function val(id, v) {
     const el = $(id);
     if (el) el.value = v;
}

function setWhisper(m) {
     const s = $("cfg-whisper");
     if (!s || !m) return;
     [...s.options].forEach(o => {
          o.selected = o.value === m;
     });
}

window.receberDoJarvis = function (raw) {
     receberDoBackend(raw);
};

function receberDoBackend(raw) {
     let d;
     try {
          d = typeof raw === "string" ? JSON.parse(raw) : raw;
     } catch (e) {
          return;
     }
     if (d.cpu !== undefined) atualizarMetricas(d.cpu, d.ram);
     if (d.resposta) adicionarMsg("ai", d.resposta);
     if (d.alarmes !== undefined) {
          try {
               S.alarmes = Array.isArray(d.alarmes) ? d.alarmes : JSON.parse(d.alarmes);
          } catch (e) { }
          if (S.page === "alarms") renderAlarmes();
     }
     if (d.clima_dados !== undefined) renderClima(d.clima_dados, d.cidade_buscada);
     if (d.ia_status) atualizarStatusIA(d.ia_status);
     if (d.voz_speaking !== undefined) {
          const w = $("wave");
          w && w.classList.toggle("hidden", !d.voz_speaking);
     }
}

function atualizarMetricas(cpu, ram) {
     const c = Math.round(cpu),
          r = Math.round(ram);
     setText("val-cpu", c);
     setText("t-cpu", c);
     setText("val-ram", r);
     setText("t-ram", r);
     setBar("bar-cpu", c);
     setBar("bar-ram", r);
     setText("st-cpu", c);
     setText("st-ram", r);
     setBar("st-bar-cpu", c);
     setBar("st-bar-ram", r);
}

function setText(id, v) {
     const e = $(id);
     if (e) e.textContent = v;
}

function setBar(id, pct) {
     const e = $(id);
     if (e) e.style.width = Math.min(100, pct) + "%";
}

function atualizarStatusIA(s) {
     const label = $("ia-label"),
          dot = $("ia-dot"),
          info = $("st-ia-info");
     if (!s) return;
     const modelo = s.modelo || s.ia_mode || "";
     const ok = !!modelo;
     if (label) label.textContent = modelo || "OFFLINE";
     if (dot) dot.classList.toggle("online", ok);
     if (info) info.textContent = ok ? `Modelo: ${modelo} | Provedor: ${s.servidor ? "ONLINE" : "local"}` : "Nenhum modelo detectado.";
}

function goTo(name) {
     document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
     document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
     const page = $("page-" + name),
          nav = document.querySelector(`.nav-item[data-s="${name}"]`);
     if (page) page.classList.add("active");
     if (nav) nav.classList.add("active");
     const titles = {
          chat: "CHAT",
          alarms: "ALARMES",
          weather: "CLIMA",
          status: "STATUS",
          config: "CONFIG",
          library: "BIBLIOTECA"
     };
     setText("topbar-title", titles[name] || name.toUpperCase());
     S.page = name;
     if (name === "alarms") renderAlarmes();
     if (name === "weather") renderClimaVazio();
     if (name === "status") pedirStatus();
     if (name === "library") renderLib();
}
window.ocultarPainel = function () {
     jarvis?.ocultar_painel?.();
};

function enviarChat() {
     const inp = $("chat-in"),
          txt = inp.value.trim();
     if (!txt) return;
     adicionarMsg("user", txt);
     inp.value = "";
     inp.style.height = "";
     if (jarvis?.executar_comando) jarvis.executar_comando(txt);
}
window.enviarChat = enviarChat;

$("chat-in")?.addEventListener("keydown", e => {
     if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          enviarChat();
     }
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
          } catch (e) { }
     });
}

function renderAlarmes() {
     const wrap = $("alarm-list");
     if (!wrap) return;
     const todos = [...S.alarmes.filter(a => a.status === "pendente"), ...S.alarmes.filter(a => a.status !== "pendente")];
     if (!todos.length) {
          wrap.innerHTML = '<div class="empty-state">⏰ Nenhum alarme cadastrado.<br><span style="font-size:10px">Use o formulário acima para criar.</span></div>';
          return;
     }
     const DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];
     wrap.innerHTML = todos.map((a) => {
          const ok = a.status === "pendente";
          const diasStr = (a.dias_semana?.length) ? a.dias_semana.map(d => DIAS[d]).join(" · ") : (a.data || "");
          const badges = [diasStr ? `<span class="badge">${esc(diasStr)}</span>` : "", a.repetir ? `<span class="badge rep">↺ REPETIR</span>` : "", !ok ? `<span class="badge done">✓ CONCLUÍDO</span>` : ""].join("");
          const hora = esc(a.hora || "--:--"),
               missao = esc(a.missao || "Alarme"),
               data = esc(a.data || "");
          return `<div class="alarm-item ${ok ? "" : "done"}"><div class="alm-time">${hora}</div><div class="alm-info"><div class="alm-mission">${missao}</div><div class="alm-meta">${badges}</div></div>${ok ? `<div class="alm-actions"><button class="alm-btn snooze" title="Soneca 10min" onclick="snoozeAlarme('${hora}','${missao}')">💤</button><button class="alm-btn" title="Remover" onclick="deletarAlarme('${hora}','${missao}','${data}')">✕</button></div>` : ""}</div>`;
     }).join("");
}

function criarAlarme() {
     const hora = $("alm-hora")?.value?.trim() || "",
          missao = $("alm-missao")?.value?.trim() || "Alarme",
          data = $("alm-data")?.value || "",
          rep = $("alm-rep")?.checked || false;
     const dias = [...document.querySelectorAll(".dia-btn.sel")].map(b => parseInt(b.dataset.d));
     if (!hora) return toast("⚠ INFORME O HORÁRIO");
     const alarme = {
          hora,
          missao,
          status: "pendente",
          repetir: rep || dias.length > 0,
          criado_em: new Date().toISOString(),
          ultimo_disparo: null,
          data: data || null,
          dias_semana: dias.length ? dias : null
     };
     S.alarmes.push(alarme);
     if (jarvis?.salvar_alarme) {
          try {
               jarvis.salvar_alarme(JSON.stringify(alarme));
          } catch (e) { }
     }
     if ($("alm-missao")) $("alm-missao").value = "";
     if ($("alm-data")) $("alm-data").value = "";
     if ($("alm-rep")) $("alm-rep").checked = false;
     document.querySelectorAll(".dia-btn.sel").forEach(b => b.classList.remove("sel"));
     toast(`⏰ ALARME ${hora} CRIADO`);
     renderAlarmes();
}
window.criarAlarme = criarAlarme;

function deletarAlarme(hora, missao, data) {
     hora = hora?.trim() || "";
     missao = missao?.trim() || "";
     if (!hora && !missao) return toast("⚠ IMPOSSÍVEL IDENTIFICAR O ALARME");
     const idx = S.alarmes.findIndex(a => (!hora || a.hora === hora) && (!missao || a.missao === missao) && (!data || (a.data || "") === data));
     if (idx >= 0) S.alarmes.splice(idx, 1);
     if (jarvis?.remover_alarme) {
          try {
               jarvis.remover_alarme(JSON.stringify({
                    hora,
                    missao,
                    data: data || null
               }));
          } catch (e) { }
     }
     toast("ALARME REMOVIDO");
     renderAlarmes();
}
window.deletarAlarme = deletarAlarme;

function snoozeAlarme(hora, missao) {
     const nova = new Date(Date.now() + 10 * 60000),
          h = nova.toTimeString().slice(0, 5),
          d = nova.toISOString().slice(0, 10);
     const sn = {
          hora: h,
          missao: "💤 Soneca",
          status: "pendente",
          repetir: false,
          criado_em: new Date().toISOString(),
          ultimo_disparo: null,
          data: d,
          dias_semana: null
     };
     S.alarmes.push(sn);
     if (jarvis?.salvar_alarme) {
          try {
               jarvis.salvar_alarme(JSON.stringify(sn));
          } catch (e) { }
     }
     toast(`💤 SONECA: ${h}`);
     renderAlarmes();
}
window.snoozeAlarme = snoozeAlarme;

function limparConcluidos() {
     S.alarmes = S.alarmes.filter(a => a.status === "pendente");
     if (jarvis?.limpar_alarmes_concluidos) {
          try {
               jarvis.limpar_alarmes_concluidos();
          } catch (e) { }
     }
     toast("CONCLUÍDOS REMOVIDOS");
     renderAlarmes();
}
window.limparConcluidos = limparConcluidos;

document.addEventListener("DOMContentLoaded", () => {
     document.querySelectorAll(".dia-btn").forEach(b => {
          b.addEventListener("click", () => b.classList.toggle("sel"));
     });
});

function buscarClima() {
     const cidade = $("wx-city")?.value?.trim() || "",
          res = $("wx-result");
     if (!res) return;
     res.innerHTML = '<div class="wx-card"><div class="wx-title">BUSCANDO...</div></div>';
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
          if (!d || d.error) {
               res.innerHTML = `<div class="wx-error">⚠ ${esc(d?.error || "Dados indisponíveis.")}</div>`;
               return;
          }
          if (d.main && d.weather) {
               res.innerHTML = wxCard(d.name || cidade || "", Math.round(d.main.temp), Math.round(d.main.feels_like), d.weather[0]?.description || "", d.main.humidity, Math.round((d.wind?.speed || 0) * 3.6));
               return;
          }
          if (d.current_condition) {
               const atual = d.current_condition[0];
               res.innerHTML = wxCard(d.nearest_area?.[0]?.areaName?.[0]?.value || cidade || "", parseInt(atual.temp_C), parseInt(atual.FeelsLikeC), atual.lang_pt?.[0]?.value || atual.weatherDesc?.[0]?.value || "—", parseInt(atual.humidity), parseInt(atual.windspeedKmph));
               return;
          }
          res.innerHTML = '<div class="wx-error">Formato de dados desconhecido.</div>';
     } catch (e) {
          res.innerHTML = `<div class="wx-error">Erro ao processar dados: ${esc(e.message)}</div>`;
     }
}
window.parseWeatherData = function (raw, cidade) {
     renderClima(raw, cidade);
};

function wxCard(cidade, temp, sensacao, desc, umidade, vento) {
     return `<div class="wx-card"><div class="wx-title">${esc(cidade.toUpperCase())} · AGORA</div><div class="wx-temp">${temp}°C</div><div class="wx-desc">${esc(desc)}</div><div class="wx-grid"><div class="wx-cell"><div class="wx-cell-lbl">SENSAÇÃO</div><div class="wx-cell-val">${sensacao}°C</div></div><div class="wx-cell"><div class="wx-cell-lbl">UMIDADE</div><div class="wx-cell-val">${umidade}%</div></div><div class="wx-cell"><div class="wx-cell-lbl">VENTO</div><div class="wx-cell-val">${vento} km/h</div></div></div></div>`;
}

function pedirStatus() {
     if (jarvis?.obter_ia_status) {
          jarvis.obter_ia_status((raw) => {
               try {
                    atualizarStatusIA(JSON.parse(raw));
               } catch (e) { }
          });
     }
}

function salvar(chave, inputId, btn) {
     const v = $(inputId)?.value?.trim();
     if (v === undefined) return;
     if (btn) {
          btn.textContent = "✓";
          setTimeout(() => btn.textContent = "SALVAR", 1500);
     }
     if (jarvis?.salvar_configuracao) jarvis.salvar_configuracao(chave, v);
     toast("SALVO: " + chave.toUpperCase());
}
window.salvar = salvar;

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
               try {
                    const r = JSON.parse(raw);
                    atualizarStatusIA({
                         modelo: r.modo,
                         servidor: true
                    });
                    toast("IA: " + r.modo.toUpperCase());
               } catch (e) { }
          });
     }
}
window.trocarIA = trocarIA;


function abrirAdicionarItem() { }

//  BIBLIOTECA DE COMANDOS 
const BIBLIOTECA = [
     { cmd: "dormir", label: "DORMIR", cat: "Sistema" },
     { cmd: "boa noite", label: "BOA NOITE", cat: "Sistema" },
     { cmd: "silencio", label: "SILÊNCIO", cat: "Sistema" },
     { cmd: "bloquear", label: "BLOQUEAR TELA", cat: "Sistema" },
     { cmd: "minimizar", label: "MINIMIZAR", cat: "Sistema" },
     { cmd: "fechar", label: "FECHAR JANELA", cat: "Sistema" },
     { cmd: "screenshot", label: "SCREENSHOT", cat: "Sistema" },
     { cmd: "limpar lixeira", label: "LIMPAR LIXEIRA", cat: "Sistema" },
     { cmd: "trabalho", label: "MODO TRABALHO", cat: "Sistema" },
     { cmd: "liga tv", label: "LIGAR TV", cat: "TV" },
     { cmd: "desligar tv", label: "DESLIGAR TV", cat: "TV" },
     { cmd: "youtube tv", label: "YOUTUBE NA TV", cat: "TV" },
     { cmd: "volume 40", label: "VOLUME TV", cat: "TV" },
     { cmd: "spotify", label: "TOCAR MÚSICA", cat: "Spotify" },
     { cmd: "playlist", label: "PLAYLIST", cat: "Spotify" },
     { cmd: "favoritas", label: "FAVORITAS", cat: "Spotify" },
     { cmd: "pausar", label: "PAUSAR", cat: "Spotify" },
     { cmd: "continuar", label: "CONTINUAR", cat: "Spotify" },
     { cmd: "proxima", label: "PRÓXIMA", cat: "Spotify" },
     { cmd: "anterior", label: "ANTERIOR", cat: "Spotify" },
     { cmd: "abrir youtube", label: "ABRIR YOUTUBE", cat: "Web" },
     { cmd: "pesquisar youtube", label: "PESQUISAR YT", cat: "Web" },
     { cmd: "pesquisar google", label: "PESQUISAR GOOGLE", cat: "Web" },
     { cmd: "monitorar tela", label: "MONITORAR TELA", cat: "Monitor" },
     { cmd: "desligar monitor", label: "DESLIGAR MONITOR", cat: "Monitor" },
     { cmd: "monitor status", label: "STATUS MONITOR", cat: "Monitor" },
     { cmd: "olha tela", label: "ANALISAR TELA", cat: "Monitor" },
     { cmd: "olha camera", label: "VER CÂMERA", cat: "Monitor" },
     { cmd: "criar alarme", label: "CRIAR ALARME", cat: "Alarme" },
     { cmd: "parar alarme", label: "PARAR ALARME", cat: "Alarme" },
     { cmd: "acordei", label: "ACORDEI", cat: "Alarme" },
];

const CAT_ICON = { Sistema: "🖥", TV: "📺", Spotify: "🎵", Web: "🌐", Monitor: "👁", Alarme: "⏰" };

function filtrarLib() {
     const busca = ($("lib-busca")?.value || "").toLowerCase();
     const cat = $("lib-cat")?.value || "";
     renderLib(BIBLIOTECA.filter(c =>
          (!cat || c.cat === cat) &&
          (!busca || c.label.toLowerCase().includes(busca) || c.cmd.toLowerCase().includes(busca))
     ));
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
          `<div class="section-hdr" style="margin-top:12px"><h2>${CAT_ICON[cat] || "◇"} ${cat.toUpperCase()}</h2></div>
     <div class="lib-grid">${cmds.map(c =>
               `<div class="lib-card" onclick="executarCmd('${c.cmd}')">
          <div class="lib-label">${esc(c.label)}</div>
          <div class="lib-exemplo">${esc(c.cmd)}</div>
        </div>`).join("")}</div>`
     ).join("");
}
window.renderLib = renderLib;

function executarCmd(cmd) {
     goTo("chat");
     adicionarMsg("user", cmd);
     if (jarvis?.executar_comando) jarvis.executar_comando(cmd);
}
window.executarCmd = executarCmd;
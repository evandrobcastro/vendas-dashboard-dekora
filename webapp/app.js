/* =========================================================================
   Boletim Casa Dekora — dashboard web (fase 1)
   Login + 8 KPIs com comparativo de metas + gráfico projetado vs realizado.
   Mesma lógica do app Streamlit (dashboard/app.py), portada para o navegador.
   ========================================================================= */
"use strict";

const API = "https://wsolnhmboycbjqcexvei.supabase.co/functions/v1";
const VENDEDOR_GERAL = "GERAL";

// Como agregar a meta ao longo do período: KPIs que acumulam somam as metas
// dos meses; KPIs de média/proporção usam a média (igual ao app.py).
const AGREGACAO_META = {
  valor_vendas: "soma",
  valor_orcamentos: "soma",
  qtd_vendas: "soma",
  qtd_orcamentos: "soma",
  ticket_medio: "media",
  ticket_medio_orcamentos: "media",
  taxa_conversao: "media",
  forecast_vendas: "media",
};

const MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun",
                  "jul", "ago", "set", "out", "nov", "dez"];

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
let REGISTROS = [];   // objetos já com data_referencia
let METAS = [];
let FILTROS = { inicio: "", fim: "", vendedores: [], cidades: [], situacoes: [],
                valorMin: null, valorMax: null };
let graficoVendas = null;

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

const fmtMoeda2 = (v) => "R$ " + v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtMoeda0 = (v) => "R$ " + Math.round(v).toLocaleString("pt-BR");
const fmtInt = (v) => Math.round(v).toLocaleString("pt-BR");
const fmtPct = (v) => `${Math.round(v)}%`;

function hojeISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function diasAtrasISO(dias) {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Lista de 'YYYY-MM' de cada mês entre início e fim (inclusive)
function mesesNoPeriodo(inicio, fim) {
  const meses = [];
  let ano = +inicio.slice(0, 4), mes = +inicio.slice(5, 7);
  const anoF = +fim.slice(0, 4), mesF = +fim.slice(5, 7);
  while (ano < anoF || (ano === anoF && mes <= mesF)) {
    meses.push(`${ano}-${String(mes).padStart(2, "0")}`);
    mes += 1;
    if (mes > 12) { mes = 1; ano += 1; }
  }
  return meses;
}

function mostrarCarregando(sim) { $("carregando").classList.toggle("oculto", !sim); }

// ---------------------------------------------------------------------------
// Autenticação
// ---------------------------------------------------------------------------
function token() { return localStorage.getItem("cd_token") || ""; }

function mostrarLogin(mensagem) {
  $("tela-app").classList.add("oculto");
  $("tela-login").classList.remove("oculto");
  const erro = $("login-erro");
  if (mensagem) { erro.textContent = mensagem; erro.classList.remove("oculto"); }
  else erro.classList.add("oculto");
}

async function fazerLogin(ev) {
  ev.preventDefault();
  const btn = $("btn-entrar");
  btn.disabled = true; btn.textContent = "Entrando…";
  try {
    const resp = await fetch(`${API}/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: $("login-email").value, senha: $("login-senha").value }),
    });
    const corpo = await resp.json();
    if (!resp.ok) { mostrarLogin(corpo.erro || "Falha no login."); return; }
    localStorage.setItem("cd_token", corpo.token);
    localStorage.setItem("cd_nome", corpo.nome || corpo.email);
    $("login-erro").classList.add("oculto");
    await carregarDados();
  } catch {
    mostrarLogin("Sem conexão com o servidor. Tente novamente.");
  } finally {
    btn.disabled = false; btn.textContent = "Entrar";
  }
}

function sair() {
  localStorage.removeItem("cd_token");
  localStorage.removeItem("cd_nome");
  mostrarLogin();
}

// ---------------------------------------------------------------------------
// Carregamento de dados
// ---------------------------------------------------------------------------
function paraObjetos(bloco) {
  const cols = bloco.columns;
  return bloco.rows.map((linha) => {
    const o = {};
    cols.forEach((c, i) => { o[c] = linha[i]; });
    return o;
  });
}

async function carregarDados() {
  mostrarCarregando(true);
  try {
    const resp = await fetch(`${API}/dados`, {
      headers: { Authorization: `Bearer ${token()}` },
    });
    if (resp.status === 401) { sair(); mostrarLogin("Sessão expirada. Entre novamente."); return; }
    if (!resp.ok) throw new Error("http " + resp.status);
    const d = await resp.json();

    REGISTROS = paraObjetos(d.registros);
    // Data de referência p/ período: vendas usam aprovação; demais, cadastro.
    for (const r of REGISTROS) {
      r.data_referencia = r.tipo === "venda" ? r.data_aprovacao : r.data_cadastro;
    }
    METAS = paraObjetos(d.metas);

    if (d.ultima_sincronizacao) {
      const q = new Date(d.ultima_sincronizacao);
      $("info-sync").textContent = "Dados sincronizados em " +
        q.toLocaleDateString("pt-BR") + " " +
        q.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    }

    $("usuario-nome").textContent = localStorage.getItem("cd_nome") || "";
    $("tela-login").classList.add("oculto");
    $("tela-app").classList.remove("oculto");

    montarFiltros();
    renderizar();
  } catch (e) {
    console.error(e);
    mostrarLogin("Não foi possível carregar os dados. Tente novamente.");
  } finally {
    mostrarCarregando(false);
  }
}

// ---------------------------------------------------------------------------
// Filtros
// ---------------------------------------------------------------------------
function valoresUnicos(campo) {
  const s = new Set();
  for (const r of REGISTROS) if (r[campo]) s.add(r[campo]);
  return [...s].sort();
}

// Dropdown com caixas de seleção; texto do botão resume a escolha.
function criarMultiselect(idContainer, opcoes, aoMudar) {
  const cont = $(idContainer);
  cont.innerHTML = "";
  cont.classList.add("ms");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "ms-botao";
  const lista = document.createElement("div");
  lista.className = "ms-lista oculto";

  const selecionados = new Set();
  const atualizarBotao = () => {
    btn.textContent = selecionados.size === 0 ? "Todos"
      : selecionados.size === 1 ? [...selecionados][0]
      : `${selecionados.size} selecionados`;
  };

  for (const op of opcoes) {
    const lab = document.createElement("label");
    const cx = document.createElement("input");
    cx.type = "checkbox";
    cx.addEventListener("change", () => {
      if (cx.checked) selecionados.add(op); else selecionados.delete(op);
      atualizarBotao();
      aoMudar([...selecionados]);
    });
    lab.appendChild(cx);
    lab.appendChild(document.createTextNode(op));
    lista.appendChild(lab);
  }
  const limpar = document.createElement("button");
  limpar.type = "button";
  limpar.className = "ms-limpar";
  limpar.textContent = "Limpar seleção";
  limpar.addEventListener("click", () => {
    selecionados.clear();
    lista.querySelectorAll("input").forEach((i) => { i.checked = false; });
    atualizarBotao();
    aoMudar([]);
  });
  lista.appendChild(limpar);

  btn.addEventListener("click", () => lista.classList.toggle("oculto"));
  document.addEventListener("click", (ev) => {
    if (!cont.contains(ev.target)) lista.classList.add("oculto");
  });

  atualizarBotao();
  cont.appendChild(btn);
  cont.appendChild(lista);
}

function parseValorBR(texto) {
  texto = texto.trim().replace(/\./g, "").replace(",", ".");
  if (!texto) return null;
  const v = parseFloat(texto);
  return Number.isFinite(v) ? v : null;
}

function montarFiltros() {
  const hoje = hojeISO();
  const inicioAno = hoje.slice(0, 4) + "-01-01";
  const datas = REGISTROS.map((r) => r.data_referencia).filter(Boolean).sort();
  const dataMin = datas.length ? datas[0] : inicioAno;

  const fInicio = $("filtro-inicio"), fFim = $("filtro-fim");
  fInicio.min = dataMin; fInicio.max = hoje; fInicio.value = inicioAno;
  fFim.min = dataMin; fFim.max = hoje; fFim.value = hoje;
  FILTROS.inicio = inicioAno; FILTROS.fim = hoje;
  fInicio.addEventListener("change", () => { FILTROS.inicio = fInicio.value; renderizar(); });
  fFim.addEventListener("change", () => { FILTROS.fim = fFim.value; renderizar(); });

  criarMultiselect("ms-vendedor", valoresUnicos("vendedor"), (v) => { FILTROS.vendedores = v; renderizar(); });
  criarMultiselect("ms-cidade", valoresUnicos("cidade"), (v) => { FILTROS.cidades = v; renderizar(); });
  criarMultiselect("ms-situacao", valoresUnicos("situacao"), (v) => { FILTROS.situacoes = v; renderizar(); });

  $("filtro-valor-min").addEventListener("change", (ev) => { FILTROS.valorMin = parseValorBR(ev.target.value); renderizar(); });
  $("filtro-valor-max").addEventListener("change", (ev) => { FILTROS.valorMax = parseValorBR(ev.target.value); renderizar(); });
}

// Filtros não-temporais (base p/ forecast) e recorte de período, como no app.py
function aplicarFiltros() {
  const f = FILTROS;
  const base = REGISTROS.filter((r) =>
    (!f.vendedores.length || f.vendedores.includes(r.vendedor)) &&
    (!f.cidades.length || f.cidades.includes(r.cidade)) &&
    (!f.situacoes.length || f.situacoes.includes(r.situacao)) &&
    (f.valorMin === null || r.valor >= f.valorMin) &&
    (f.valorMax === null || r.valor <= f.valorMax)
  );
  const filtrado = base.filter((r) =>
    r.data_referencia && r.data_referencia >= f.inicio && r.data_referencia <= f.fim
  );
  return { base, filtrado };
}

// ---------------------------------------------------------------------------
// KPIs (mesma matemática de _kpis_periodo do app.py)
// ---------------------------------------------------------------------------
function kpisPeriodo(linhas) {
  const vendas = linhas.filter((r) => r.tipo === "venda");
  const orcamentos = linhas.filter((r) => r.tipo === "orcamento");

  const soma = (arr) => arr.reduce((t, r) => t + (r.valor || 0), 0);
  const totalVendido = soma(vendas);
  const qtdVendas = vendas.length;
  const totalOrcado = soma(orcamentos);
  const qtdOrcamentos = orcamentos.length;

  return {
    total_vendido: totalVendido,
    ticket_medio: qtdVendas ? totalVendido / qtdVendas : 0,
    qtd_vendas: qtdVendas,
    // Taxa de conversão por VALOR: R$ vendido / R$ orçado no período.
    taxa_conversao: totalOrcado ? (totalVendido / totalOrcado) * 100 : 0,
    total_orcado: totalOrcado,
    ticket_medio_orcamentos: qtdOrcamentos ? totalOrcado / qtdOrcamentos : 0,
    qtd_orcamentos: qtdOrcamentos,
  };
}

// Meta agregada do período p/ um KPI, respeitando o filtro de vendedor
function metaAlvo(tipoKpi, mesesPeriodo, vendedoresAlvo) {
  const valores = METAS
    .filter((m) => m.tipo_kpi === tipoKpi &&
                   mesesPeriodo.includes(m.ano_mes) &&
                   vendedoresAlvo.includes(m.vendedor))
    .map((m) => +m.valor_meta)
    .filter((v) => v !== 0);
  if (!valores.length) return null;
  const total = valores.reduce((a, b) => a + b, 0);
  return AGREGACAO_META[tipoKpi] === "media" ? total / valores.length : total;
}

function deltaHTML(meta, realizado, fmt) {
  if (!meta) return '<div class="cd-delta cd-delta-neutro">sem meta para este período</div>';
  const pct = (realizado / meta) * 100;
  const atingiu = realizado >= meta;
  const seta = atingiu ? "▲" : "▼";
  const classe = atingiu ? "cd-delta-up" : "cd-delta-down";
  return `<div class="cd-delta ${classe}">${seta} ${Math.round(pct)}% da meta (${fmt(meta)})</div>`;
}

function renderKpis(filtrado, base, mesesPeriodo, vendedoresAlvo) {
  const atual = kpisPeriodo(filtrado);

  // Forecast: orçamentos dos últimos 30 dias (janela própria) × taxa de conversão
  const limite30 = diasAtrasISO(30);
  const orc30 = base.filter((r) => r.tipo === "orcamento" &&
                                   r.data_cadastro && r.data_cadastro >= limite30);
  const forecast = orc30.reduce((t, r) => t + (r.valor || 0), 0) * atual.taxa_conversao / 100;

  const delta = (tipoKpi, realizado, fmt) =>
    deltaHTML(metaAlvo(tipoKpi, mesesPeriodo, vendedoresAlvo), realizado, fmt);

  const caixas = [
    ["Vendas no período", fmtMoeda2(atual.total_vendido), delta("valor_vendas", atual.total_vendido, fmtMoeda0)],
    ["Ticket médio", fmtMoeda2(atual.ticket_medio), delta("ticket_medio", atual.ticket_medio, fmtMoeda0)],
    ["Número de pedidos", fmtInt(atual.qtd_vendas), delta("qtd_vendas", atual.qtd_vendas, fmtInt)],
    ["Taxa de conversão", fmtPct(atual.taxa_conversao), delta("taxa_conversao", atual.taxa_conversao, fmtPct)],
    ["Orçamentos no período", fmtMoeda2(atual.total_orcado), delta("valor_orcamentos", atual.total_orcado, fmtMoeda0)],
    ["Ticket médio de orçamentos", fmtMoeda2(atual.ticket_medio_orcamentos), delta("ticket_medio_orcamentos", atual.ticket_medio_orcamentos, fmtMoeda0)],
    ["Número total de orçamentos", fmtInt(atual.qtd_orcamentos), delta("qtd_orcamentos", atual.qtd_orcamentos, fmtInt)],
    ["Forecast de vendas", fmtMoeda2(forecast), delta("forecast_vendas", forecast, fmtMoeda0)],
  ];

  $("kpis").innerHTML = caixas.map(([rotulo, valor, deltaHtml]) => `
    <div class="kpi">
      <div class="kpi-label">${rotulo}</div>
      <div class="kpi-valor">${valor}</div>
      ${deltaHtml}
    </div>`).join("");

  return atual;
}

// ---------------------------------------------------------------------------
// Gráfico: Vendas — projetado vs realizado
// ---------------------------------------------------------------------------
function renderGraficoVendas(filtrado, mesesPeriodo, vendedoresAlvo) {
  const el = $("grafico-vendas");
  const vazio = $("grafico-vendas-vazio");

  // Vendas realizadas por mês (já com período + filtros)
  const vendasPorMes = {};
  for (const r of filtrado) {
    if (r.tipo !== "venda" || !r.data_aprovacao) continue;
    const am = r.data_aprovacao.slice(0, 7);
    vendasPorMes[am] = (vendasPorMes[am] || 0) + (r.valor || 0);
  }
  // Metas de valor_vendas somadas por mês (várias linhas c/ + de um vendedor)
  const metasPorMes = {};
  for (const m of METAS) {
    if (m.tipo_kpi !== "valor_vendas" || !mesesPeriodo.includes(m.ano_mes) ||
        !vendedoresAlvo.includes(m.vendedor)) continue;
    metasPorMes[m.ano_mes] = (metasPorMes[m.ano_mes] || 0) + (+m.valor_meta || 0);
  }

  const rotulos = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);
  const serieVendas = mesesPeriodo.map((am) => vendasPorMes[am] || 0);
  const serieMetas = mesesPeriodo.map((am) => metasPorMes[am] || 0);
  const total = [...serieVendas, ...serieMetas].reduce((a, b) => a + b, 0);

  if (total === 0) {
    el.classList.add("oculto");
    vazio.classList.remove("oculto");
    return;
  }
  el.classList.remove("oculto");
  vazio.classList.add("oculto");

  const grad = (base, topo) => new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: topo },
    { offset: 1, color: base },
  ]);
  const rotuloK = (v) => v > 0 ? "R$ " + Math.round(v / 1000).toLocaleString("pt-BR") + "k" : "";

  if (!graficoVendas) graficoVendas = echarts.init(el);
  graficoVendas.setOption({
    animationDuration: 300,
    grid: { left: 54, right: 14, top: 28, bottom: 30 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (v) => fmtMoeda0(v || 0),
      textStyle: { fontFamily: "Montserrat, sans-serif" },
    },
    xAxis: {
      type: "category",
      data: rotulos,
      axisLine: { lineStyle: { color: "#B9AD9E" } },
      axisTick: { show: false },
      axisLabel: { color: "#8A6A4A", fontWeight: 600, fontFamily: "Montserrat, sans-serif" },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: "#EFE7DA" } },
      axisLabel: {
        color: "#8A6A4A", fontFamily: "Montserrat, sans-serif",
        formatter: (v) => v >= 1e6 ? (v / 1e6).toLocaleString("pt-BR") + "M"
                        : v >= 1e3 ? Math.round(v / 1e3) + "k" : v,
      },
    },
    series: [
      {
        name: "Vendas", type: "bar", data: serieVendas,
        itemStyle: { color: grad("#8B3C05", "#C9712E"), borderRadius: [4, 4, 0, 0] },
        barGap: "10%", barCategoryGap: "30%",
        label: { show: true, position: "top", formatter: (p) => rotuloK(p.value),
                 color: "#000", fontSize: 11, fontWeight: "bold",
                 fontFamily: "Montserrat, sans-serif" },
      },
      {
        name: "Metas", type: "bar", data: serieMetas,
        itemStyle: { color: grad("#A89B89", "#C7BCAE"), borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: "top", formatter: (p) => rotuloK(p.value),
                 color: "#000", fontSize: 11, fontWeight: "bold",
                 fontFamily: "Montserrat, sans-serif" },
      },
    ],
  });
  graficoVendas.resize();
}

// ---------------------------------------------------------------------------
// Render geral
// ---------------------------------------------------------------------------
function renderizar() {
  const { base, filtrado } = aplicarFiltros();
  const mesesPeriodo = (FILTROS.inicio && FILTROS.fim && FILTROS.inicio <= FILTROS.fim)
    ? mesesNoPeriodo(FILTROS.inicio, FILTROS.fim)
    : [hojeISO().slice(0, 7)];
  const vendedoresAlvo = FILTROS.vendedores.length ? FILTROS.vendedores : [VENDEDOR_GERAL];

  renderKpis(filtrado, base, mesesPeriodo, vendedoresAlvo);
  renderGraficoVendas(filtrado, mesesPeriodo, vendedoresAlvo);
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------
$("form-login").addEventListener("submit", fazerLogin);
$("btn-sair").addEventListener("click", sair);
$("btn-menu").addEventListener("click", () => {
  $("sidebar").classList.toggle("aberta");
  $("sidebar-fundo").classList.toggle("visivel");
});
$("sidebar-fundo").addEventListener("click", () => {
  $("sidebar").classList.remove("aberta");
  $("sidebar-fundo").classList.remove("visivel");
});
window.addEventListener("resize", () => { if (graficoVendas) graficoVendas.resize(); });

if (token()) carregarDados();
else mostrarLogin();

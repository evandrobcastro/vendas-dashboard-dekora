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

// Cores fixas por segmento, em tons da marca (terracota + neutros). A ordem
// (e portanto a cor) vem do total geral, então não muda com o filtro.
const PALETA_SEG = ["#8B3C05", "#C9712E", "#8A6A4A", "#B8860B", "#B9AD9E", "#D8CFC0", "#6E4B2A"];
const CORES_COMISS = { "Comissionado": "#C9712E", "Cliente Final": "#8B3C05" };
const ORDEM_COMISS = ["Comissionado", "Cliente Final"]; // base -> topo

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
let REGISTROS = [];   // objetos já com data_referencia
let METAS = [];
let FILTROS = { inicio: "", fim: "", vendedores: [], cidades: [], situacoes: [],
                valorMin: null, valorMax: null };
let SEGMENTOS_ORDEM = [];
let CORES_SEG = {};
const GRAFICOS = {}; // instâncias ECharts por id de elemento

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

    // Ordem/cor fixa dos segmentos, pelo total geral de vendas (todos os dados)
    const totalPorSeg = {};
    for (const r of REGISTROS) {
      if (r.tipo !== "venda") continue;
      const seg = r.segmento ?? "Não informado";
      totalPorSeg[seg] = (totalPorSeg[seg] || 0) + (r.valor || 0);
    }
    SEGMENTOS_ORDEM = Object.entries(totalPorSeg)
      .sort((a, b) => b[1] - a[1]).map(([s]) => s);
    CORES_SEG = {};
    SEGMENTOS_ORDEM.forEach((s, i) => { CORES_SEG[s] = PALETA_SEG[i % PALETA_SEG.length]; });

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

  const g = grafico("grafico-vendas");
  g.setOption({
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
  g.resize();
}

// ---------------------------------------------------------------------------
// Rankings, Segmento de clientes e Comissionado vs Cliente Final
// ---------------------------------------------------------------------------
function grafico(idEl) {
  if (!GRAFICOS[idEl]) GRAFICOS[idEl] = echarts.init($(idEl));
  return GRAFICOS[idEl];
}

const FONTE = "Montserrat, sans-serif";
const EIXO_X = (rotulos, nome) => ({
  type: "category", data: rotulos, name: nome, nameLocation: "middle",
  nameGap: 30, nameTextStyle: { color: "#8A6A4A", fontWeight: 600, fontFamily: FONTE },
  axisLine: { lineStyle: { color: "#B9AD9E" } }, axisTick: { show: false },
  axisLabel: { color: "#8A6A4A", fontWeight: 600, fontFamily: FONTE },
});
const compactoBR = (v) => v >= 1e6 ? (v / 1e6).toLocaleString("pt-BR") + "M"
                        : v >= 1e3 ? Math.round(v / 1e3) + "k" : v;

function renderRankings(filtrado) {
  const topPor = (tipo) => {
    const somas = {};
    for (const r of filtrado) {
      if (r.tipo !== tipo || !r.vendedor) continue;
      somas[r.vendedor] = (somas[r.vendedor] || 0) + (r.valor || 0);
    }
    return Object.entries(somas).sort((a, b) => b[1] - a[1]).slice(0, 4);
  };
  const html = (titulo, itens) => {
    if (!itens.length) {
      return `<h4>${titulo}</h4><div class="grafico-vazio">Sem dados no filtro selecionado.</div>`;
    }
    const maximo = itens[0][1] || 1;
    return `<h4>${titulo}</h4>` + itens.map(([nome, valor], i) => `
      <div class="cd-rank-row">
        <div class="cd-rank-num">${i + 1}</div>
        <div class="cd-rank-name" title="${nome}">${nome}</div>
        <div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:${Math.round(valor / maximo * 100)}%"></div></div>
        <div class="cd-rank-value">R$ ${Math.round(valor / 1000).toLocaleString("pt-BR")}k</div>
      </div>`).join("");
  };
  $("rank-vendas").innerHTML = html("Top vendedores — vendas", topPor("venda"));
  $("rank-orcamentos").innerHTML = html("Top vendedores — orçamentos", topPor("orcamento"));
}

// Rótulo branco com contorno escuro (halo), legível sobre qualquer barra
const ROTULO_HALO = (formatter, fontSize) => ({
  show: true, position: "inside", formatter, color: "#fff",
  fontSize, fontWeight: "bold", fontFamily: FONTE,
  textBorderColor: "#3a2410", textBorderWidth: 2,
});

function pizza(idEl, idVazio, dados, coresPorNome, rotuloInterno = false) {
  const el = $(idEl), vazio = $(idVazio);
  const comValor = dados.filter((d) => d.value > 0).sort((a, b) => b.value - a.value);
  if (!comValor.length) {
    el.classList.add("oculto"); vazio.classList.remove("oculto");
    if (GRAFICOS[idEl]) GRAFICOS[idEl].clear();
    return;
  }
  el.classList.remove("oculto"); vazio.classList.add("oculto");
  // Com poucas fatias grandes o rótulo cabe dentro (fora, na horizontal,
  // ele encosta na borda do cartão e o ECharts corta com "…").
  const label = rotuloInterno
    ? { position: "inside", formatter: (p) => Math.round(p.percent) + "%",
        color: "#fff", fontSize: 11, fontWeight: "bold", fontFamily: FONTE,
        textBorderColor: "#3a2410", textBorderWidth: 2 }
    : { formatter: (p) => Math.round(p.percent) + "%", color: "#5b5048",
        fontSize: 10, fontWeight: "bold", fontFamily: FONTE };
  const g = grafico(idEl);
  g.setOption({
    animationDuration: 300,
    tooltip: {
      trigger: "item",
      formatter: (p) => `${p.name}<br>${fmtMoeda0(p.value)} (${p.percent.toLocaleString("pt-BR")}%)`,
      textStyle: { fontFamily: FONTE },
    },
    series: [{
      type: "pie", radius: ["35%", "68%"],
      data: comValor.map((d) => ({ ...d, itemStyle: { color: coresPorNome[d.name] } })),
      label,
      labelLine: { show: !rotuloInterno, lineStyle: { color: "#B9AD9E" } },
    }],
  }, true);
  g.resize();
}

function legendaHTML(idEl, nomes, cores) {
  $(idEl).innerHTML = nomes.map(
    (n) => `<span><i style="background:${cores[n]}"></i>${n}</span>`
  ).join("");
}

function renderSegmento(filtrado, mesesPeriodo) {
  const el = $("grafico-segmento"), vazio = $("grafico-segmento-vazio");
  const rotulos = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);

  // Soma por (mês, segmento) das vendas do período
  const porMesSeg = {};
  for (const r of filtrado) {
    if (r.tipo !== "venda" || !r.data_aprovacao) continue;
    const am = r.data_aprovacao.slice(0, 7);
    const seg = r.segmento ?? "Não informado";
    (porMesSeg[am] ??= {})[seg] = (porMesSeg[am][seg] || 0) + (r.valor || 0);
  }
  const totaisMes = mesesPeriodo.map(
    (am) => Object.values(porMesSeg[am] || {}).reduce((a, b) => a + b, 0)
  );
  const maiorColuna = Math.max(...totaisMes, 0);
  // Só rotula segmentos com altura razoável (>=5% da maior coluna)
  const limiar = maiorColuna * 0.05;

  if (maiorColuna === 0) {
    el.classList.add("oculto"); vazio.classList.remove("oculto");
    if (GRAFICOS["grafico-segmento"]) GRAFICOS["grafico-segmento"].clear();
  } else {
    el.classList.remove("oculto"); vazio.classList.add("oculto");
    const g = grafico("grafico-segmento");
    g.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 16, bottom: 46 },
      tooltip: {
        trigger: "item",
        formatter: (p) => `${p.name} — ${p.seriesName}<br>${fmtMoeda2(p.value)}`,
        textStyle: { fontFamily: FONTE },
      },
      xAxis: EIXO_X(rotulos, "Mês aprovação"),
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#EFE7DA" } },
        axisLabel: { color: "#8A6A4A", fontFamily: FONTE, formatter: compactoBR },
      },
      series: SEGMENTOS_ORDEM.map((seg) => ({
        name: seg, type: "bar", stack: "total", barCategoryGap: "35%",
        data: mesesPeriodo.map((am) => porMesSeg[am]?.[seg] || 0),
        itemStyle: { color: CORES_SEG[seg] },
        label: ROTULO_HALO(
          (p) => p.value >= limiar ? Math.round(p.value).toLocaleString("pt-BR") : "", 9),
      })),
    }, true);
    g.resize();
  }

  // Pizza com a distribuição % do período inteiro
  const totalPorSeg = {};
  for (const am of mesesPeriodo) {
    for (const [seg, v] of Object.entries(porMesSeg[am] || {})) {
      totalPorSeg[seg] = (totalPorSeg[seg] || 0) + v;
    }
  }
  pizza("pizza-segmento", "pizza-segmento-vazio",
        SEGMENTOS_ORDEM.map((s) => ({ name: s, value: totalPorSeg[s] || 0 })), CORES_SEG);
  legendaHTML("legenda-segmento", SEGMENTOS_ORDEM, CORES_SEG);
}

function renderComissionado(filtrado, mesesPeriodo) {
  const el = $("grafico-comissionado"), vazio = $("grafico-comissionado-vazio");
  const rotulos = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);

  // Só vendas do segmento CLIENTE FINAL: separa quem teve comissionado
  const vendasCF = filtrado.filter(
    (r) => r.tipo === "venda" && r.data_aprovacao &&
           String(r.segmento ?? "").trim().toUpperCase() === "CLIENTE FINAL"
  );
  const porMesCat = {};
  const totalPorCat = { "Comissionado": 0, "Cliente Final": 0 };
  for (const r of vendasCF) {
    const am = r.data_aprovacao.slice(0, 7);
    const cat = String(r.comissionado ?? "").trim() ? "Comissionado" : "Cliente Final";
    (porMesCat[am] ??= {})[cat] = (porMesCat[am][cat] || 0) + (r.valor || 0);
    totalPorCat[cat] += r.valor || 0;
  }

  const fracoes = {}; // cat -> [frações por mês]
  for (const cat of ORDEM_COMISS) fracoes[cat] = [];
  let temDados = false;
  for (const am of mesesPeriodo) {
    const totalMes = Object.values(porMesCat[am] || {}).reduce((a, b) => a + b, 0);
    for (const cat of ORDEM_COMISS) {
      fracoes[cat].push(totalMes > 0 ? (porMesCat[am]?.[cat] || 0) / totalMes : 0);
    }
    if (totalMes > 0) temDados = true;
  }

  if (!temDados) {
    el.classList.add("oculto"); vazio.classList.remove("oculto");
    if (GRAFICOS["grafico-comissionado"]) GRAFICOS["grafico-comissionado"].clear();
  } else {
    el.classList.remove("oculto"); vazio.classList.add("oculto");
    const pctBR = (v, casas) => (v * 100).toLocaleString("pt-BR",
      { minimumFractionDigits: casas, maximumFractionDigits: casas }) + "%";
    const g = grafico("grafico-comissionado");
    g.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 16, bottom: 46 },
      tooltip: {
        trigger: "item",
        formatter: (p) => `${p.name} — ${p.seriesName}<br>${pctBR(p.value, 1)}`,
        textStyle: { fontFamily: FONTE },
      },
      xAxis: EIXO_X(rotulos, "Mês aprovação"),
      yAxis: {
        type: "value", max: 1,
        splitLine: { lineStyle: { color: "#EFE7DA" } },
        axisLabel: { color: "#8A6A4A", fontFamily: FONTE,
                     formatter: (v) => Math.round(v * 100) + "%" },
      },
      series: ORDEM_COMISS.map((cat) => ({
        name: cat, type: "bar", stack: "total", barCategoryGap: "35%",
        data: fracoes[cat],
        itemStyle: { color: CORES_COMISS[cat] },
        label: ROTULO_HALO((p) => p.value > 0 ? pctBR(p.value, 1) : "", 10),
      })),
    }, true);
    g.resize();
  }

  pizza("pizza-comissionado", "pizza-comissionado-vazio",
        ORDEM_COMISS.map((c) => ({ name: c, value: totalPorCat[c] })), CORES_COMISS, true);
  legendaHTML("legenda-comissionado", ORDEM_COMISS, CORES_COMISS);
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
  renderRankings(filtrado);
  renderSegmento(filtrado, mesesPeriodo);
  renderComissionado(filtrado, mesesPeriodo);
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
window.addEventListener("resize", () => {
  Object.values(GRAFICOS).forEach((g) => g.resize());
});

if (token()) carregarDados();
else mostrarLogin();

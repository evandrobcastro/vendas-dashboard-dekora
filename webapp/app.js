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
// Classes de produto podem passar de 7: mais dois tons da marca p/ nao repetir
const PALETA_CLASSES = [...PALETA_SEG, "#4E342E", "#DBA05B"];

// Grandes classes: agrupamento definido pelo usuário (17/07/2026).
// Classe que não estiver no mapa aparece com o próprio nome.
const GRANDES_CLASSES = {
  "DECORAÇÃO PEÇA AVULSA": "DECORAÇÃO",
  "DECORAÇÃO ESPELHOS CASA DEKORA": "DECORAÇÃO",
  "DECORAÇÃO ESPELHOS MOLDURA AÇO": "DECORAÇÃO",
  "ENGENHARIA / TEMPERADO": "ENGENHARIA",
  "GUARDA CORPO": "ENGENHARIA",
  "ROLLDOOR": "ENGENHARIA",
  "ESQUADRIA ALUMÍNIO": "ESQUADRIA",
  "PORTÃO": "ESQUADRIA",
  "LACA108": "LACA108",
};
const grandeClasse = (c) => GRANDES_CLASSES[c] || c;
const CORES_COMISS = { "Comissionado": "#C9712E", "Cliente Final": "#8B3C05" };
const ORDEM_COMISS = ["Comissionado", "Cliente Final"]; // base -> topo

// Chaves canônicas de KPI que as caixas da aba Comercial reconhecem
const TIPOS_KPI_SUGERIDOS = [
  "valor_vendas", "ticket_medio", "qtd_vendas", "taxa_conversao",
  "valor_orcamentos", "ticket_medio_orcamentos", "qtd_orcamentos", "forecast_vendas",
];
const OUTRO = "Outro (digitar abaixo)";

// ---------------------------------------------------------------------------
// Estado
// ---------------------------------------------------------------------------
let REGISTROS = [];   // objetos já com data_referencia
let METAS = [];
let FILTROS = { inicio: "", fim: "", vendedores: [], cidades: [], situacoes: [],
                valorMin: null, valorMax: null };
let SEGMENTOS_ORDEM = [];
let CORES_SEG = {};
let SYNC_LOG = [];
let PRODUTOS = [];
let CLASSES_ORDEM = [];
let CORES_CLASSE = {};
let GC_ORDEM = [];
let CORES_GC = {};
let PRODUTOS_VISAO = "grandes"; // "grandes" | "detalhe"
let FINANCEIRO = [];
let PREVISTO = [];
let LOJA_SEL = "CASA DEKORA";
let REPOSICOES = [];
let REPO_DADOS = []; // OS do período atual (p/ paginação da tabela)
const REPO_PAG = { pagina: 0 };
// cores fixas por tipo de OS, em tons da marca
const CORES_REPO = {
  "MANUTENÇÃO - MONTADOR": "#8B3C05",
  "MANUTENÇÃO - FORNECEDOR": "#C9712E",
  "REPOSIÇÃO EMPRESA": "#8A6A4A",
  "REPOSIÇÃO CLIENTE": "#B8860B",
  "REPOSIÇÃO FORNECEDOR": "#6E4B2A",
  "MANUTENÇÃO": "#B9AD9E",
};
const GRAFICOS = {}; // instâncias ECharts por id de elemento
let ULTIMO_FILTRADO = []; // linhas da aba Tabela (recalculadas a cada filtro)
const TABELA = { pagina: 0, ordenarPor: "data_referencia", asc: false };
const METAS_PAG = { pagina: 0 };
let syncTimer = null;

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
    SYNC_LOG = d.sync_log ? paraObjetos(d.sync_log) : [];
    PRODUTOS = d.produtos ? paraObjetos(d.produtos) : [];
    FINANCEIRO = d.financeiro ? paraObjetos(d.financeiro) : [];
    PREVISTO = d.financeiro_previsto ? paraObjetos(d.financeiro_previsto) : [];
    REPOSICOES = d.reposicoes ? paraObjetos(d.reposicoes) : [];

    // Ordem/cor fixa das classes de produto, pelo total geral de vendas
    const totalPorClasse = {};
    for (const p of PRODUTOS) {
      totalPorClasse[p.classe] = (totalPorClasse[p.classe] || 0) + (p.valor_venda || 0);
    }
    CLASSES_ORDEM = Object.entries(totalPorClasse)
      .sort((a, b) => b[1] - a[1]).map(([c]) => c);
    CORES_CLASSE = {};
    CLASSES_ORDEM.forEach((c, i) => { CORES_CLASSE[c] = PALETA_CLASSES[i % PALETA_CLASSES.length]; });
    const totalPorGC = {};
    for (const p of PRODUTOS) {
      const gc = grandeClasse(p.classe);
      totalPorGC[gc] = (totalPorGC[gc] || 0) + (p.valor_venda || 0);
    }
    GC_ORDEM = Object.entries(totalPorGC).sort((a, b) => b[1] - a[1]).map(([c]) => c);
    CORES_GC = {};
    GC_ORDEM.forEach((c, i) => { CORES_GC[c] = PALETA_CLASSES[i % PALETA_CLASSES.length]; });

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
    montarAbaMetas();
    montarAdmin();
    renderLog();
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
  let dataMin = datas.length ? datas[0] : inicioAno;
  // historico de produtos/financeiro pode comecar antes dos registros
  const mesesExtras = [...PRODUTOS.map((p) => p.ano_mes),
                       ...FINANCEIRO.map((f) => f.ano_mes),
                       ...REPOSICOES.map((r) => r.ano_mes)].filter(Boolean).sort();
  if (mesesExtras.length && mesesExtras[0] + "-01" < dataMin) {
    dataMin = mesesExtras[0] + "-01";
  }

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
const compactoBR = (v) => {
  const a = Math.abs(v), s = v < 0 ? "-" : "";
  if (a >= 1e6) return s + (a / 1e6).toLocaleString("pt-BR") + "M";
  if (a >= 1e3) return s + Math.round(a / 1e3) + "k";
  return v;
};

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
  // ele encosta na borda do cartão e o ECharts corta com "…"). Se todas as
  // fatias têm >=10%, usa rótulo interno automaticamente.
  const total = comValor.reduce((t, d) => t + d.value, 0);
  const interno = rotuloInterno || comValor.every((d) => d.value / total >= 0.1);
  const label = interno
    ? { position: "inside", formatter: (p) => Math.round(p.percent) + "%",
        color: "#fff", fontSize: 11, fontWeight: "bold", fontFamily: FONTE,
        textBorderColor: "#3a2410", textBorderWidth: 2 }
    : { formatter: (p) => p.percent >= 2 ? Math.round(p.percent) + "%" : "",
        color: "#5b5048", fontSize: 10, fontWeight: "bold", fontFamily: FONTE,
        alignTo: "edge", edgeDistance: 6 };
  const g = grafico(idEl);
  g.setOption({
    animationDuration: 300,
    tooltip: {
      trigger: "item",
      formatter: (p) => `${p.name}<br>${fmtMoeda0(p.value)} (${p.percent.toLocaleString("pt-BR")}%)`,
      textStyle: { fontFamily: FONTE },
    },
    series: [{
      type: "pie", radius: ["32%", "62%"],
      data: comValor.map((d) => ({ ...d, itemStyle: { color: coresPorNome[d.name] } })),
      label,
      labelLine: { show: !interno, lineStyle: { color: "#B9AD9E" } },
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
// Aba Produtos: KPIs, evolução mensal por classe, mix e rankings
// ---------------------------------------------------------------------------
const fmtM2 = (v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 0 }) + " m²";

function renderProdutos(mesesPeriodo) {
  const doPeriodo = PRODUTOS.filter((p) => mesesPeriodo.includes(p.ano_mes));

  // ---- KPIs ----
  const soma = (campo) => doPeriodo.reduce((t, p) => t + (p[campo] || 0), 0);
  const m2 = soma("m2_vidro");
  const venda = soma("valor_venda");
  const lucro = soma("lucro");
  const valorM2 = m2 ? venda / m2 : 0;
  const margem = venda ? (lucro / venda) * 100 : 0;

  const porSub = {};
  for (const p of doPeriodo) {
    const chave = p.subclasse;
    (porSub[chave] ??= { valor: 0, m2: 0 }).valor += p.valor_venda || 0;
    porSub[chave].m2 += p.m2_vidro || 0;
  }
  const campeao = Object.entries(porSub).sort((a, b) => b[1].valor - a[1].valor)[0];

  const caixas = [
    ["M² de vidro vendidos", fmtM2(m2), `média de ${fmtM2(mesesPeriodo.length ? m2 / mesesPeriodo.length : 0)}/mês`],
    ["Valor médio do m²", fmtMoeda2(valorM2), `sobre ${fmtMoeda0(venda)} vendidos`],
    ["Produto campeão", campeao ? campeao[0] : "—", campeao ? `${fmtMoeda0(campeao[1].valor)} no período` : "sem dados"],
    ["Margem de lucro", fmtPct(margem), `${fmtMoeda0(lucro)} de lucro`],
  ];
  $("kpis-produtos").innerHTML = caixas.map(([rotulo, valor, sub], i) => `
    <div class="kpi">
      <div class="kpi-label">${rotulo}</div>
      <div class="kpi-valor${i === 2 ? " kpi-valor-texto" : ""}">${escapaHTML(valor)}</div>
      <div class="cd-delta cd-delta-neutro">${escapaHTML(sub)}</div>
    </div>`).join("");

  // ---- Evolução mensal empilhada por classe (grandes classes ou detalhado) ----
  const detalhe = PRODUTOS_VISAO === "detalhe";
  const chaveClasse = detalhe ? (c) => c : grandeClasse;
  const ordemClasses = detalhe ? CLASSES_ORDEM : GC_ORDEM;
  const coresClasses = detalhe ? CORES_CLASSE : CORES_GC;

  const el = $("grafico-produtos"), vazio = $("grafico-produtos-vazio");
  const rotulos = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);
  const porMesClasse = {};
  for (const p of doPeriodo) {
    const cl = chaveClasse(p.classe);
    (porMesClasse[p.ano_mes] ??= {})[cl] =
      (porMesClasse[p.ano_mes][cl] || 0) + (p.valor_venda || 0);
  }
  const totaisMes = mesesPeriodo.map(
    (am) => Object.values(porMesClasse[am] || {}).reduce((a, b) => a + b, 0)
  );
  const maiorColuna = Math.max(...totaisMes, 0);
  const limiar = maiorColuna * 0.05;

  if (maiorColuna === 0) {
    el.classList.add("oculto"); vazio.classList.remove("oculto");
    if (GRAFICOS["grafico-produtos"]) GRAFICOS["grafico-produtos"].clear();
  } else {
    el.classList.remove("oculto"); vazio.classList.add("oculto");
    const g = grafico("grafico-produtos");
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
      series: ordemClasses.map((classe) => ({
        name: classe, type: "bar", stack: "total", barCategoryGap: "35%",
        data: mesesPeriodo.map((am) => porMesClasse[am]?.[classe] || 0),
        itemStyle: { color: coresClasses[classe] },
        label: ROTULO_HALO(
          (p) => p.value >= limiar ? Math.round(p.value).toLocaleString("pt-BR") : "", 9),
      })),
    }, true);
    g.resize();
  }

  // ---- Mix por classe (pizza) + legenda ----
  const totalClassePeriodo = {};
  for (const p of doPeriodo) {
    const cl = chaveClasse(p.classe);
    totalClassePeriodo[cl] = (totalClassePeriodo[cl] || 0) + (p.valor_venda || 0);
  }
  pizza("pizza-produtos", "pizza-produtos-vazio",
        ordemClasses.map((c) => ({ name: c, value: totalClassePeriodo[c] || 0 })), coresClasses);
  legendaHTML("legenda-produtos", ordemClasses, coresClasses);

  // ---- Rankings de subclasses ----
  const rankHTML = (titulo, itens, fmt) => {
    if (!itens.length) {
      return `<h4>${titulo}</h4><div class="grafico-vazio">Sem dados no período selecionado.</div>`;
    }
    const maximo = itens[0][1] || 1;
    return `<h4>${titulo}</h4>` + itens.map(([nome, valor], i) => `
      <div class="cd-rank-row">
        <div class="cd-rank-num">${i + 1}</div>
        <div class="cd-rank-name" title="${escapaHTML(nome)}">${escapaHTML(nome)}</div>
        <div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:${Math.round(valor / maximo * 100)}%"></div></div>
        <div class="cd-rank-value">${fmt(valor)}</div>
      </div>`).join("");
  };
  const topValor = Object.entries(porSub).map(([n, v]) => [n, v.valor])
    .sort((a, b) => b[1] - a[1]).slice(0, 6);
  const topM2 = Object.entries(porSub).map(([n, v]) => [n, v.m2])
    .filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 6);
  $("rank-produtos-valor").innerHTML = rankHTML("Top produtos — valor",
    topValor, (v) => "R$ " + Math.round(v / 1000).toLocaleString("pt-BR") + "k");
  $("rank-produtos-m2").innerHTML = rankHTML("Top produtos — m² de vidro", topM2, fmtM2);
}

// ---------------------------------------------------------------------------
// Aba Financeiro: DRE (regime de caixa) + KPIs + gráfico
// ---------------------------------------------------------------------------
// Linhas calculadas do DRE: depois de qual grupo (prefixo numérico) entram
const DRE_CALCULADAS = [
  [3, "MARGEM DE CONTRIBUIÇÃO"],
  [7, "LUCRO OPERACIONAL"],
  [9, "LUCRO LÍQUIDO"],
];

const numGrupo = (g) => parseInt(g, 10) || 99;

function renderFinanceiro(mesesPeriodo) {
  const dados = FINANCEIRO.filter(
    (f) => f.loja === LOJA_SEL && mesesPeriodo.includes(f.ano_mes)
  );
  const tabela = $("tabela-dre"), tabVazio = $("tabela-dre-vazio");

  // grupo -> classe -> {ano_mes: valor}
  const arvore = {};
  for (const f of dados) {
    ((arvore[f.grupo] ??= {})[f.classe] ??= {})[f.ano_mes] = f.valor;
  }
  const grupos = Object.keys(arvore).sort((a, b) => numGrupo(a) - numGrupo(b));

  // total de um grupo por mês
  const totalGrupoMes = (g, am) => Object.values(arvore[g] || {})
    .reduce((t, meses) => t + (meses[am] || 0), 0);
  const totalAte = (limite, am) => grupos
    .filter((g) => numGrupo(g) <= limite)
    .reduce((t, g) => t + totalGrupoMes(g, am), 0);

  // ---- KPIs ----
  const somaMeses = (fn) => mesesPeriodo.reduce((t, am) => t + fn(am), 0);
  const receita = somaMeses((am) => totalGrupoMes(grupos.find((g) => numGrupo(g) === 1) || "", am));
  const margemContrib = somaMeses((am) => totalAte(3, am));
  const lucroOper = somaMeses((am) => totalAte(7, am));
  const lucroLiq = somaMeses((am) => totalAte(99, am));
  const pctReceita = (v) => receita ? ` (${Math.round(v / receita * 100)}% da receita)` : "";

  const caixas = [
    ["Receita recebida", fmtMoeda0(receita), "grupo 1 — vendas no período"],
    ["Margem de contribuição", fmtMoeda0(margemContrib), "após impostos e custos" + pctReceita(margemContrib)],
    ["Lucro operacional", fmtMoeda0(lucroOper), "após todas as despesas" + pctReceita(lucroOper)],
    ["Lucro líquido", fmtMoeda0(lucroLiq), "resultado final" + pctReceita(lucroLiq)],
  ];
  $("kpis-financeiro").innerHTML = caixas.map(([rotulo, valor, sub]) => `
    <div class="kpi">
      <div class="kpi-label">${rotulo}</div>
      <div class="kpi-valor">${valor}</div>
      <div class="cd-delta cd-delta-neutro">${escapaHTML(sub)}</div>
    </div>`).join("");

  if (!dados.length) {
    tabela.innerHTML = "";
    tabVazio.classList.remove("oculto");
    $("fin-graficos").classList.add("oculto");
    return;
  }
  tabVazio.classList.add("oculto");
  $("fin-graficos").classList.remove("oculto");

  // ---- Tabela DRE ----
  const rotulosMes = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1] + "/" + am.slice(2, 4));
  const cel = (v, destaque) => {
    if (!v) return `<td class="num"></td>`;
    const neg = v < 0 ? " neg" : "";
    return `<td class="num${neg}">${Math.round(v).toLocaleString("pt-BR")}</td>`;
  };
  const linhaValores = (fn, classeTr, rotulo) => {
    const valores = mesesPeriodo.map(fn);
    const total = valores.reduce((a, b) => a + b, 0);
    return `<tr class="${classeTr}"><td>${escapaHTML(rotulo)}</td>` +
      valores.map((v) => cel(v)).join("") + cel(total) + "</tr>";
  };

  let corpo = "";
  for (const g of grupos) {
    corpo += `<tr class="dre-grupo"><td colspan="${mesesPeriodo.length + 2}">${escapaHTML(g)}</td></tr>`;
    const classes = Object.keys(arvore[g]).sort((a, b) => a.localeCompare(b, "pt-BR"));
    for (const c of classes) {
      corpo += linhaValores((am) => arvore[g][c][am] || 0, "", c);
    }
    corpo += linhaValores((am) => totalGrupoMes(g, am), "dre-total", `TOTAL ${g}`);
    for (const [limite, rotulo] of DRE_CALCULADAS) {
      if (numGrupo(g) === limite ||
          (limite === 9 && g === grupos[grupos.length - 1] && numGrupo(g) < 9)) {
        corpo += linhaValores((am) => totalAte(limite === 9 ? 99 : limite, am),
                              "dre-destaque", rotulo);
      }
    }
  }
  tabela.innerHTML =
    `<thead><tr><th></th>${rotulosMes.map((m) => `<th style="text-align:right">${m}</th>`).join("")}` +
    `<th style="text-align:right">Total</th></tr></thead><tbody>${corpo}</tbody>`;

  // ---- Bateria de gráficos de gestão ----
  const grad = (base, topo) => new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: topo }, { offset: 1, color: base },
  ]);
  const rotuloK = (v) => v ? "R$ " + Math.round(v / 1000).toLocaleString("pt-BR") + "k" : "";
  const rotulosMesCurto = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);
  const EIXO_Y_MOEDA = {
    type: "value",
    splitLine: { lineStyle: { color: "#EFE7DA" } },
    axisLabel: { color: "#8A6A4A", fontFamily: FONTE, formatter: compactoBR },
  };
  const nomeCurto = (g) => g.replace(/^\d+\s*-?\s*/, "").trim();
  const grupoPorNum = (n) => grupos.find((g) => numGrupo(g) === n) || "";
  const totalGrupoPeriodo = (g) => mesesPeriodo.reduce((t, am) => t + totalGrupoMes(g, am), 0);

  // --- 1. Cascata do resultado (período inteiro) ---
  {
    const NOMES = { 1: "Receita", 2: "Impostos", 3: "Custo merc.", 4: "Comercial",
                    5: "Pessoal", 6: "Administrativa", 7: "Operacional",
                    8: "Financeiro", 9: "Dividendos" };
    const passos = [];
    let acumulado = 0;
    const passo = (nome, v, cor, subtotal) => passos.push({ nome, v, cor, subtotal });
    for (const g of grupos) {
      const n = numGrupo(g);
      const v = totalGrupoPeriodo(g);
      if (v !== 0) passo(NOMES[n] || nomeCurto(g), v, n === 1 ? "#8B3C05" : (v > 0 ? "#C9712E" : "#A89B89"), false);
      if (n === 3) passo("MARGEM CONTRIB.", null, "#B8860B", true);
      if (n === 7) passo("LUCRO OPERAC.", null, "#B8860B", true);
    }
    passo("LUCRO LÍQUIDO", null, "#6E4B2A", true);

    const cats = [], base = [], valores = [], reais = [];
    for (const p of passos) {
      cats.push(p.nome);
      if (p.subtotal) {
        base.push(Math.min(acumulado, 0)); valores.push(Math.abs(acumulado)); reais.push(acumulado);
      } else {
        base.push(Math.min(acumulado, acumulado + p.v));
        valores.push(Math.abs(p.v)); reais.push(p.v);
        acumulado += p.v;
      }
    }
    const g1 = grafico("grafico-cascata");
    g1.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 28, bottom: 74 },
      tooltip: {
        trigger: "axis", axisPointer: { type: "shadow" },
        formatter: (ps) => {
          const i = ps[ps.length - 1].dataIndex;
          return `${cats[i]}<br>${fmtMoeda0(reais[i])}`;
        },
        textStyle: { fontFamily: FONTE },
      },
      xAxis: { type: "category", data: cats,
               axisLine: { lineStyle: { color: "#B9AD9E" } }, axisTick: { show: false },
               axisLabel: { color: "#8A6A4A", fontWeight: 600, fontFamily: FONTE,
                            rotate: 35, fontSize: 9, interval: 0, hideOverlap: false } },
      yAxis: EIXO_Y_MOEDA,
      series: [
        { type: "bar", stack: "cascata", data: base, silent: true,
          itemStyle: { color: "transparent" }, emphasis: { disabled: true },
          tooltip: { show: false } },
        { type: "bar", stack: "cascata", barCategoryGap: "35%",
          data: valores.map((v, i) => ({
            value: v,
            itemStyle: { color: passos[i].cor, borderRadius: reais[i] >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] },
          })),
          label: { show: true, position: "top",
                   formatter: (p) => rotuloK(reais[p.dataIndex]),
                   color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
      ],
    }, true);
    g1.resize();
  }

  // --- 2. Evolução das margens (%) ---
  {
    const pct = (num, den) => den > 0 ? +(num / den * 100).toFixed(1) : null;
    const receitaMes = mesesPeriodo.map((am) => totalGrupoMes(grupoPorNum(1), am));
    const series = [
      ["Margem de contribuição", "#8B3C05", mesesPeriodo.map((am, i) => pct(totalAte(3, am), receitaMes[i]))],
      ["Lucro operacional", "#B8860B", mesesPeriodo.map((am, i) => pct(totalAte(7, am), receitaMes[i]))],
      ["Margem líquida", "#8A6A4A", mesesPeriodo.map((am, i) => pct(totalAte(99, am), receitaMes[i]))],
    ];
    const g2 = grafico("grafico-margens");
    g2.setOption({
      animationDuration: 300,
      grid: { left: 44, right: 14, top: 20, bottom: 30 },
      tooltip: { trigger: "axis", valueFormatter: (v) => v == null ? "—" : v.toLocaleString("pt-BR") + "%",
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulosMesCurto, null),
      yAxis: { type: "value",
               splitLine: { lineStyle: { color: "#EFE7DA" } },
               axisLabel: { color: "#8A6A4A", fontFamily: FONTE, formatter: (v) => v + "%" } },
      series: series.map(([nome, cor, dados2]) => ({
        name: nome, type: "line", data: dados2, connectNulls: true,
        lineStyle: { width: 2, color: cor }, itemStyle: { color: cor },
        symbol: "circle", symbolSize: 7,
      })),
    }, true);
    g2.resize();
  }

  // --- 4. Ponto de equilíbrio vs receita ---
  {
    const receitaMes = mesesPeriodo.map((am) => totalGrupoMes(grupoPorNum(1), am));
    const peMes = mesesPeriodo.map((am, i) => {
      const receita2 = receitaMes[i];
      if (receita2 <= 0) return null;
      const mcPct = totalAte(3, am) / receita2;           // margem de contribuição %
      const fixos = Math.abs([4, 5, 6, 7].reduce((t, n) => t + totalGrupoMes(grupoPorNum(n), am), 0));
      return mcPct > 0 ? +(fixos / mcPct).toFixed(0) : null;
    });
    const g3 = grafico("grafico-pe");
    g3.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 28, bottom: 30 },
      tooltip: { trigger: "axis", valueFormatter: (v) => v == null ? "—" : fmtMoeda0(v),
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulosMesCurto, null),
      yAxis: EIXO_Y_MOEDA,
      series: [
        { name: "Receita recebida", type: "bar", data: receitaMes,
          itemStyle: { color: grad("#8B3C05", "#C9712E"), borderRadius: [4, 4, 0, 0] },
          barCategoryGap: "40%",
          label: { show: true, position: "top", formatter: (p) => rotuloK(p.value),
                   color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
        { name: "Ponto de equilíbrio", type: "line", data: peMes, connectNulls: true,
          lineStyle: { width: 2, color: "#B8860B", type: "dashed" },
          itemStyle: { color: "#B8860B" }, symbol: "diamond", symbolSize: 9 },
      ],
    }, true);
    g3.resize();
  }

  // --- 3. Para onde vai o dinheiro (grupos de saída 2-7) ---
  {
    const gruposSaida = grupos.filter((g) => numGrupo(g) >= 2 && numGrupo(g) <= 7)
      .sort((a, b) => Math.abs(totalGrupoPeriodo(b)) - Math.abs(totalGrupoPeriodo(a)));
    const cores = {};
    gruposSaida.forEach((g, i) => { cores[nomeCurto(g)] = PALETA_CLASSES[i % PALETA_CLASSES.length]; });
    const totalSaidaMes = mesesPeriodo.map((am) =>
      gruposSaida.reduce((t, g) => t + Math.abs(Math.min(totalGrupoMes(g, am), 0)), 0));
    const limiar = Math.max(...totalSaidaMes, 0) * 0.05;
    const g4 = grafico("grafico-saidas");
    g4.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 16, bottom: 30 },
      tooltip: { trigger: "item",
                 formatter: (p) => `${p.name} — ${p.seriesName}<br>${fmtMoeda0(p.value)}`,
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulosMesCurto, null),
      yAxis: EIXO_Y_MOEDA,
      series: gruposSaida.map((g) => ({
        name: nomeCurto(g), type: "bar", stack: "total", barCategoryGap: "35%",
        data: mesesPeriodo.map((am) => Math.abs(Math.min(totalGrupoMes(g, am), 0))),
        itemStyle: { color: cores[nomeCurto(g)] },
        label: ROTULO_HALO(
          (p) => p.value >= limiar ? Math.round(p.value).toLocaleString("pt-BR") : "", 9),
      })),
    }, true);
    g4.resize();
    pizza("pizza-saidas", "pizza-saidas-vazio",
          gruposSaida.map((g) => ({ name: nomeCurto(g), value: Math.abs(totalGrupoPeriodo(g)) })),
          cores);
    legendaHTML("legenda-saidas", gruposSaida.map(nomeCurto), cores);
  }

  // --- Ranking: maiores despesas por classe ---
  {
    const porClasse = {};
    for (const f of dados) {
      if (f.valor < 0) porClasse[f.classe] = (porClasse[f.classe] || 0) + Math.abs(f.valor);
    }
    const top = Object.entries(porClasse).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const maximo = top.length ? top[0][1] : 1;
    $("rank-despesas").innerHTML = "<h4>Maiores despesas do período</h4>" +
      (top.length ? top.map(([nome, v], i) => `
        <div class="cd-rank-row">
          <div class="cd-rank-num">${i + 1}</div>
          <div class="cd-rank-name" title="${escapaHTML(nome)}">${escapaHTML(nome)}</div>
          <div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:${Math.round(v / maximo * 100)}%"></div></div>
          <div class="cd-rank-value">R$ ${Math.round(v / 1000).toLocaleString("pt-BR")}k</div>
        </div>`).join("")
      : '<div class="grafico-vazio">Sem despesas no período.</div>');
  }

  // --- 5. Caixa: entradas vs saídas + saldo ---
  {
    const entradas = mesesPeriodo.map((am) => dados
      .filter((f) => f.ano_mes === am && f.valor > 0).reduce((t, f) => t + f.valor, 0));
    const saidas = mesesPeriodo.map((am) => dados
      .filter((f) => f.ano_mes === am && f.valor < 0).reduce((t, f) => t + f.valor, 0));
    const saldo = mesesPeriodo.map((am, i) => entradas[i] + saidas[i]);
    const g5 = grafico("grafico-caixa");
    g5.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 20, bottom: 30 },
      tooltip: { trigger: "axis", valueFormatter: (v) => fmtMoeda0(v || 0),
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulosMesCurto, null),
      yAxis: EIXO_Y_MOEDA,
      series: [
        { name: "Entradas", type: "bar", stack: "caixa", data: entradas,
          itemStyle: { color: grad("#8B3C05", "#C9712E"), borderRadius: [4, 4, 0, 0] },
          barCategoryGap: "40%" },
        { name: "Saídas", type: "bar", stack: "caixa", data: saidas,
          itemStyle: { color: "#A89B89", borderRadius: [0, 0, 4, 4] } },
        { name: "Saldo do mês", type: "line", data: saldo,
          lineStyle: { width: 2, color: "#B8860B" }, itemStyle: { color: "#B8860B" },
          symbol: "circle", symbolSize: 7 },
      ],
    }, true);
    g5.resize();
  }

  // --- Previsão de caixa: lançamentos futuros (independe do período) ---
  {
    const prev = PREVISTO.filter((f) => f.loja === LOJA_SEL);
    const elP = $("grafico-previsao"), vzP = $("grafico-previsao-vazio");
    const mesesPrev = [...new Set(prev.map((f) => f.ano_mes))].sort();
    if (!mesesPrev.length) {
      elP.classList.add("oculto"); vzP.classList.remove("oculto");
      if (GRAFICOS["grafico-previsao"]) GRAFICOS["grafico-previsao"].clear();
    } else {
      elP.classList.remove("oculto"); vzP.classList.add("oculto");
      const soma = (am, nGrupo, sinal) => prev
        .filter((f) => f.ano_mes === am && numGrupo(f.grupo) === nGrupo)
        .reduce((t, f) => t + (sinal > 0 ? Math.max(f.valor, 0) : Math.min(f.valor, 0)), 0);
      const recebiveis = mesesPrev.map((am) => soma(am, 1, +1));
      const pagamentos = mesesPrev.map((am) => soma(am, 3, -1));
      const saldoPrev = mesesPrev.map((_, i) => recebiveis[i] + pagamentos[i]);
      const rotulosPrev = mesesPrev.map(
        (am) => MESES_PT[+am.slice(5, 7) - 1] + "/" + am.slice(2, 4));
      const gP = grafico("grafico-previsao");
      gP.setOption({
        animationDuration: 300,
        grid: { left: 54, right: 14, top: 20, bottom: 30 },
        tooltip: { trigger: "axis", valueFormatter: (v) => fmtMoeda0(v || 0),
                   textStyle: { fontFamily: FONTE } },
        xAxis: EIXO_X(rotulosPrev, null),
        yAxis: EIXO_Y_MOEDA,
        series: [
          { name: "Recebíveis previstos", type: "bar", stack: "prev", data: recebiveis,
            itemStyle: { color: grad("#B8860B", "#D9B84A"), borderRadius: [4, 4, 0, 0] },
            barCategoryGap: "40%",
            label: { show: true, position: "top",
                     formatter: (p) => Math.abs(p.value) >= 1000 ? rotuloK(p.value) : "",
                     color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
          { name: "Pagamentos a fornecedores", type: "bar", stack: "prev", data: pagamentos,
            itemStyle: { color: "#A89B89", borderRadius: [0, 0, 4, 4] },
            label: { show: true, position: "bottom",
                     formatter: (p) => Math.abs(p.value) >= 1000 ? rotuloK(p.value) : "",
                     color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
          { name: "Saldo previsto", type: "line", data: saldoPrev,
            lineStyle: { width: 2, color: "#8B3C05" }, itemStyle: { color: "#8B3C05" },
            symbol: "circle", symbolSize: 7 },
        ],
      }, true);
      gP.resize();
    }
  }

  // --- 6. Recebido (caixa) vs vendido (aprovação) ---
  {
    const vendidoMes = mesesPeriodo.map((am) => REGISTROS
      .filter((r) => r.tipo === "venda" && r.data_aprovacao &&
                     r.data_aprovacao.slice(0, 7) === am)
      .reduce((t, r) => t + (r.valor || 0), 0));
    const recebidoMes = mesesPeriodo.map((am) => totalGrupoMes(grupoPorNum(1), am));
    const g6 = grafico("grafico-recebido-vendido");
    g6.setOption({
      animationDuration: 300,
      grid: { left: 54, right: 14, top: 28, bottom: 30 },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
                 valueFormatter: (v) => fmtMoeda0(v || 0),
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulosMesCurto, null),
      yAxis: EIXO_Y_MOEDA,
      series: [
        { name: "Vendido (aprovação)", type: "bar", data: vendidoMes,
          itemStyle: { color: grad("#8B3C05", "#C9712E"), borderRadius: [4, 4, 0, 0] },
          barGap: "10%", barCategoryGap: "30%",
          label: { show: true, position: "top", formatter: (p) => rotuloK(p.value),
                   color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
        { name: "Recebido (caixa)", type: "bar", data: recebidoMes,
          itemStyle: { color: grad("#B8860B", "#D9B84A"), borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: "top", formatter: (p) => rotuloK(p.value),
                   color: "#000", fontSize: 10, fontWeight: "bold", fontFamily: FONTE } },
      ],
    }, true);
    g6.resize();
  }
}

// ---------------------------------------------------------------------------
// Aba Reposições: KPIs, evolução por tipo, motivos, causadores, custos, tabela
// ---------------------------------------------------------------------------
const fmtHoras = (v) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " h";

// separa um campo "A|B|C" em tags limpas
function _tagsRepo(texto) {
  return (texto || "").split("|").map((t) => t.trim()).filter(Boolean);
}

function renderReposicoes(mesesPeriodo) {
  const dados = REPOSICOES.filter((r) => mesesPeriodo.includes(r.ano_mes));
  REPO_DADOS = dados;

  // ---- KPIs ----
  const totalOS = dados.length;
  const horas = dados.reduce((t, r) => t + (r.horas || 0), 0);
  const custo = dados.reduce((t, r) => t + (r.custo || 0), 0);
  const finalizadas = dados.filter((r) => /finaliz/i.test(r.status || "")).length;
  const pendentes = dados.filter((r) => /pendente/i.test(r.status || "")).length;
  const pctFin = totalOS ? Math.round(finalizadas / totalOS * 100) : 0;

  const caixas = [
    ["Ordens de serviço", fmtInt(totalOS), `${mesesPeriodo.length} mes(es) no período`],
    ["Horas trabalhadas", fmtHoras(horas), totalOS ? `média de ${fmtHoras(horas / totalOS)}/OS` : ""],
    ["% finalizadas", pctFin + "%", `${finalizadas} de ${totalOS} concluídas`],
    ["OS pendentes", fmtInt(pendentes), custo > 0 ? `custo total ${fmtMoeda0(custo)}` : "aguardando conclusão"],
  ];
  $("kpis-reposicoes").innerHTML = caixas.map(([rotulo, valor, sub]) => `
    <div class="kpi">
      <div class="kpi-label">${rotulo}</div>
      <div class="kpi-valor">${valor}</div>
      <div class="cd-delta cd-delta-neutro">${escapaHTML(sub)}</div>
    </div>`).join("");

  // ---- Tipos presentes (ordem fixa pela cor conhecida, extras ao fim) ----
  const tiposPresentes = [...new Set(dados.map((r) => r.tipo).filter(Boolean))];
  const ordemTipos = Object.keys(CORES_REPO).filter((t) => tiposPresentes.includes(t))
    .concat(tiposPresentes.filter((t) => !(t in CORES_REPO)));
  const corTipo = (t) => CORES_REPO[t] || PALETA_CLASSES[ordemTipos.indexOf(t) % PALETA_CLASSES.length];
  const coresTipo = {};
  ordemTipos.forEach((t) => { coresTipo[t] = corTipo(t); });

  // ---- Evolução mensal empilhada por tipo ----
  const el = $("grafico-repo-mes"), vazio = $("grafico-repo-mes-vazio");
  const rotulos = mesesPeriodo.map((am) => MESES_PT[+am.slice(5, 7) - 1]);
  const porMesTipo = {};
  for (const r of dados) {
    (porMesTipo[r.ano_mes] ??= {})[r.tipo] = (porMesTipo[r.ano_mes]?.[r.tipo] || 0) + 1;
  }
  if (!totalOS) {
    el.classList.add("oculto"); vazio.classList.remove("oculto");
    if (GRAFICOS["grafico-repo-mes"]) GRAFICOS["grafico-repo-mes"].clear();
  } else {
    el.classList.remove("oculto"); vazio.classList.add("oculto");
    const g = grafico("grafico-repo-mes");
    g.setOption({
      animationDuration: 300,
      grid: { left: 44, right: 14, top: 16, bottom: 30 },
      tooltip: { trigger: "item",
                 formatter: (p) => `${p.name} — ${p.seriesName}<br>${p.value} OS`,
                 textStyle: { fontFamily: FONTE } },
      xAxis: EIXO_X(rotulos, null),
      yAxis: { type: "value", minInterval: 1,
               splitLine: { lineStyle: { color: "#EFE7DA" } },
               axisLabel: { color: "#8A6A4A", fontFamily: FONTE } },
      series: ordemTipos.map((tipo) => ({
        name: tipo, type: "bar", stack: "total", barCategoryGap: "35%",
        data: mesesPeriodo.map((am) => porMesTipo[am]?.[tipo] || 0),
        itemStyle: { color: coresTipo[tipo] },
        label: ROTULO_HALO((p) => p.value > 0 ? p.value : "", 10),
      })),
    }, true);
    g.resize();
  }

  // ---- Mix por tipo (pizza) + legenda ----
  const totalPorTipo = {};
  for (const r of dados) totalPorTipo[r.tipo] = (totalPorTipo[r.tipo] || 0) + 1;
  pizza("pizza-repo", "pizza-repo-vazio",
        ordemTipos.map((t) => ({ name: t, value: totalPorTipo[t] || 0 })), coresTipo);
  legendaHTML("legenda-repo", ordemTipos, coresTipo);

  // ---- Rankings (contagem e custo) por motivo e causador ----
  const agrega = (campo) => {
    const cont = {}, cst = {};
    for (const r of dados) {
      for (const tag of _tagsRepo(r[campo])) {
        cont[tag] = (cont[tag] || 0) + 1;
        cst[tag] = (cst[tag] || 0) + (r.custo || 0);
      }
    }
    return { cont, cst };
  };
  const motivos = agrega("motivos");
  const causadores = agrega("causadores");

  const rankHTML = (titulo, entradas, fmt, vazioTxt) => {
    const top = entradas.sort((a, b) => b[1] - a[1]).slice(0, 6).filter(([, v]) => v > 0);
    if (!top.length) return `<h4>${titulo}</h4><div class="grafico-vazio">${vazioTxt}</div>`;
    const maximo = top[0][1] || 1;
    return `<h4>${titulo}</h4>` + top.map(([nome, v], i) => `
      <div class="cd-rank-row">
        <div class="cd-rank-num">${i + 1}</div>
        <div class="cd-rank-name" title="${escapaHTML(nome)}">${escapaHTML(nome)}</div>
        <div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:${Math.round(v / maximo * 100)}%"></div></div>
        <div class="cd-rank-value">${fmt(v)}</div>
      </div>`).join("");
  };
  $("rank-motivos").innerHTML = rankHTML("Motivos mais frequentes",
    Object.entries(motivos.cont), fmtInt, "Sem motivos no período.");
  $("rank-causadores").innerHTML = rankHTML("Causadores mais frequentes",
    Object.entries(causadores.cont), fmtInt, "Sem causadores identificados.");
  $("rank-custo-motivo").innerHTML = rankHTML("Custo por motivo",
    Object.entries(motivos.cst), fmtMoeda0, "Sem custo registrado no período.");
  $("rank-custo-causador").innerHTML = rankHTML("Custo por causador",
    Object.entries(causadores.cst), fmtMoeda0, "Sem custo registrado no período.");

  renderTabelaRepo(dados);
}

const COLS_REPO_TABELA = [
  ["os", "OS"], ["tipo", "Tipo"], ["identificacao", "Identificação"],
  ["cliente", "Cliente"], ["cidade", "Cidade"], ["data_cadastro", "Cadastro", (v) => fmtData(v)],
  ["causadores", "Causador(es)", (v) => _tagsRepo(v).join(", ")],
  ["motivos", "Motivos", (v) => _tagsRepo(v).join(", ")],
  ["horas", "Horas", (v) => (v || 0).toLocaleString("pt-BR", { maximumFractionDigits: 2 }), true],
  ["custo", "Custo (R$)", (v) => v ? fmtMoeda2(v) : "", true],
  ["status", "Status"],
];

function renderTabelaRepo(dados) {
  const linhas = [...dados].sort((a, b) =>
    (b.data_cadastro || "").localeCompare(a.data_cadastro || ""));
  const total = linhas.length;
  const paginas = Math.max(Math.ceil(total / LINHAS_POR_PAGINA), 1);
  REPO_PAG.pagina = Math.min(REPO_PAG.pagina, paginas - 1);
  const ini = REPO_PAG.pagina * LINHAS_POR_PAGINA;
  const visiveis = linhas.slice(ini, ini + LINHAS_POR_PAGINA);

  const ths = COLS_REPO_TABELA.map(([, r]) => `<th>${r}</th>`).join("");
  const trs = visiveis.map((r) => "<tr>" + COLS_REPO_TABELA.map(([c, , fmt, num]) => {
    const bruto = r[c];
    const txt = fmt ? fmt(bruto) : escapaHTML(bruto ?? "");
    return `<td${num ? ' class="num"' : ""}>${txt}</td>`;
  }).join("") + "</tr>").join("");
  $("tabela-repo").innerHTML = `<thead><tr>${ths}</tr></thead><tbody>${trs}</tbody>`;
  $("repo-info").textContent =
    total ? `${ini + 1}–${Math.min(ini + LINHAS_POR_PAGINA, total)} de ${total.toLocaleString("pt-BR")} OS`
          : "Nenhuma OS no período";
  $("repo-ant").disabled = REPO_PAG.pagina === 0;
  $("repo-prox").disabled = REPO_PAG.pagina >= paginas - 1;
}

// ---------------------------------------------------------------------------
// Aba Tabela: registros filtrados, com ordenação e paginação
// ---------------------------------------------------------------------------
const fmtData = (iso) => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";
const fmtDataHora = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("pt-BR") + " " +
         d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
};
const escapaHTML = (v) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
                                          .replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// [campo, rótulo, formatador?, numérica?]
const COLS_TABELA = [
  ["codigo", "Código"],
  ["tipo", "Tipo"],
  ["cliente", "Cliente"],
  ["situacao", "Situação"],
  ["valor", "Valor (R$)", fmtMoeda2, true],
  ["vendedor", "Vendedor"],
  ["cidade", "Cidade"],
  ["segmento", "Segmento"],
  ["comissionado", "Comissionado"],
  ["data_cadastro", "Cadastro", fmtData],
  ["data_aprovacao", "Aprovação", fmtData],
  ["dias_aprovacao", "Dias aprov.", null, true],
  ["metragem", "Metragem", null, true],
  ["desconto", "Desconto", fmtMoeda2, true],
  ["valor_sem_desc", "Valor s/ desc.", fmtMoeda2, true],
  ["forma_divulgacao", "Divulgação"],
  ["identificacao", "Identificação"],
];
const LINHAS_POR_PAGINA = 50;

function renderTabela() {
  const linhas = [...ULTIMO_FILTRADO];
  const campo = TABELA.ordenarPor;
  linhas.sort((a, b) => {
    const va = a[campo], vb = b[campo];
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
    const cmp = typeof va === "number" ? va - vb : String(va).localeCompare(String(vb), "pt-BR");
    return TABELA.asc ? cmp : -cmp;
  });

  const total = linhas.length;
  const paginas = Math.max(Math.ceil(total / LINHAS_POR_PAGINA), 1);
  TABELA.pagina = Math.min(TABELA.pagina, paginas - 1);
  const ini = TABELA.pagina * LINHAS_POR_PAGINA;
  const visiveis = linhas.slice(ini, ini + LINHAS_POR_PAGINA);

  const ths = COLS_TABELA.map(([campo2, rotulo]) => {
    const marca = campo2 === TABELA.ordenarPor ? (TABELA.asc ? " ▲" : " ▼") : "";
    return `<th class="ordenavel" data-campo="${campo2}">${rotulo}${marca}</th>`;
  }).join("");
  const trs = visiveis.map((r) => "<tr>" + COLS_TABELA.map(([c, , fmt, num]) => {
    const bruto = r[c];
    const txt = bruto == null ? "" : (fmt ? fmt(bruto) : escapaHTML(bruto));
    return `<td${num ? ' class="num"' : ""}>${txt}</td>`;
  }).join("") + "</tr>").join("");

  $("tabela-registros").innerHTML = `<thead><tr>${ths}</tr></thead><tbody>${trs}</tbody>`;
  $("tabela-registros").querySelectorAll("th.ordenavel").forEach((th) => {
    th.addEventListener("click", () => {
      const c = th.dataset.campo;
      if (TABELA.ordenarPor === c) TABELA.asc = !TABELA.asc;
      else { TABELA.ordenarPor = c; TABELA.asc = true; }
      renderTabela();
    });
  });
  $("tab-info").textContent =
    total ? `${ini + 1}–${Math.min(ini + LINHAS_POR_PAGINA, total)} de ${total.toLocaleString("pt-BR")} registros`
          : "Nenhum registro no filtro selecionado";
  $("tab-ant").disabled = TABELA.pagina === 0;
  $("tab-prox").disabled = TABELA.pagina >= paginas - 1;
}

// ---------------------------------------------------------------------------
// Aba Metas: formulário individual, lote e listagem
// ---------------------------------------------------------------------------
async function apiAdmin(metodo, corpo) {
  const resp = await fetch(`${API}/admin`, {
    method: metodo,
    headers: {
      Authorization: `Bearer ${token()}`,
      ...(corpo ? { "Content-Type": "application/json" } : {}),
    },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  if (resp.status === 401) { sair(); mostrarLogin("Sessão expirada. Entre novamente."); throw new Error("401"); }
  return { ok: resp.ok, status: resp.status, corpo: await resp.json() };
}

function mensagem(idEl, texto, ok) {
  const el = $(idEl);
  el.className = ok ? "msg-ok" : "msg-erro";
  el.textContent = texto;
}

function upsertMetaLocal(l) {
  const chave = (m) => `${m.tipo_kpi}|${m.vendedor}|${m.ano_mes}`;
  const nova = {
    tipo_kpi: String(l.tipo_kpi).trim(),
    vendedor: String(l.vendedor ?? "").trim() || VENDEDOR_GERAL,
    ano_mes: String(l.ano_mes).trim(),
    valor_meta: +l.valor_meta,
    atualizado_em: new Date().toISOString(),
  };
  const i = METAS.findIndex((m) => chave(m) === chave(nova));
  if (i >= 0) METAS[i] = nova; else METAS.push(nova);
}

function preencherSelect(sel, opcoes) {
  sel.innerHTML = opcoes.map((o) => `<option>${escapaHTML(o)}</option>`).join("");
}

function montarAbaMetas() {
  preencherSelect($("meta-kpi"), [...TIPOS_KPI_SUGERIDOS, OUTRO]);
  preencherSelect($("meta-vendedor"), [VENDEDOR_GERAL, ...valoresUnicos("vendedor"), OUTRO]);
  const hoje = hojeISO();
  $("meta-mes").value = hoje.slice(0, 7);

  const ligaOutro = (selId, inputId) => {
    $(selId).addEventListener("change", () => {
      $(inputId).classList.toggle("oculto", $(selId).value !== OUTRO);
    });
  };
  ligaOutro("meta-kpi", "meta-kpi-outro");
  ligaOutro("meta-vendedor", "meta-vendedor-outro");

  $("btn-salvar-meta").addEventListener("click", salvarMetaIndividual);
  $("btn-lote-add").addEventListener("click", () => adicionarLinhaLote());
  $("btn-lote-salvar").addEventListener("click", salvarLote);
  $("metas-ant").addEventListener("click", () => { METAS_PAG.pagina--; renderMetasLista(); });
  $("metas-prox").addEventListener("click", () => { METAS_PAG.pagina++; renderMetasLista(); });

  $("lote-linhas").innerHTML = "";
  adicionarLinhaLote({ tipo_kpi: "valor_vendas", vendedor: VENDEDOR_GERAL,
                       ano_mes: hoje.slice(0, 7), valor_meta: "" });
  renderMetasLista();
}

async function salvarMetaIndividual() {
  const btn = $("btn-salvar-meta");
  const tipoKpi = $("meta-kpi").value === OUTRO ? $("meta-kpi-outro").value.trim() : $("meta-kpi").value;
  const vendedor = $("meta-vendedor").value === OUTRO ? $("meta-vendedor-outro").value.trim() : $("meta-vendedor").value;
  const anoMes = $("meta-mes").value; // AAAA-MM
  const valor = parseValorBR($("meta-valor").value);
  if (!tipoKpi) { mensagem("meta-msg", "Informe o KPI.", false); return; }
  if (!anoMes) { mensagem("meta-msg", "Informe o mês de referência.", false); return; }
  if (valor === null) { mensagem("meta-msg", "Informe o valor da meta.", false); return; }

  btn.disabled = true;
  try {
    const linha = { tipo_kpi: tipoKpi, vendedor, ano_mes: anoMes, valor_meta: valor };
    const r = await apiAdmin("POST", { acao: "meta", ...linha });
    if (!r.ok) { mensagem("meta-msg", r.corpo.erro || "Falha ao salvar.", false); return; }
    upsertMetaLocal(linha);
    mensagem("meta-msg", `Meta salva: ${tipoKpi} / ${vendedor} / ${anoMes}`, true);
    $("meta-valor").value = "";
    renderMetasLista();
    renderizar(); // atualiza comparativos das caixas e o gráfico de metas
  } catch (e) {
    if (String(e.message) !== "401") mensagem("meta-msg", "Sem conexão com o servidor.", false);
  } finally {
    btn.disabled = false;
  }
}

function adicionarLinhaLote(valores) {
  const v = valores ?? { tipo_kpi: "", vendedor: VENDEDOR_GERAL, ano_mes: "", valor_meta: "" };
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input data-campo="tipo_kpi" value="${escapaHTML(v.tipo_kpi)}" placeholder="valor_vendas"></td>
    <td><input data-campo="vendedor" value="${escapaHTML(v.vendedor)}" placeholder="GERAL"></td>
    <td><input data-campo="ano_mes" value="${escapaHTML(v.ano_mes)}" placeholder="AAAA-MM"></td>
    <td><input data-campo="valor_meta" value="${escapaHTML(v.valor_meta)}" placeholder="0,00" inputmode="decimal"></td>
    <td><button class="lote-remover" title="Remover linha">✕</button></td>`;
  tr.querySelector(".lote-remover").addEventListener("click", () => tr.remove());
  $("lote-linhas").appendChild(tr);
}

async function salvarLote() {
  const btn = $("btn-lote-salvar");
  const linhas = [...$("lote-linhas").querySelectorAll("tr")].map((tr) => {
    const pega = (c) => tr.querySelector(`input[data-campo="${c}"]`).value;
    return {
      tipo_kpi: pega("tipo_kpi").trim(),
      vendedor: pega("vendedor").trim(),
      ano_mes: pega("ano_mes").trim(),
      valor_meta: parseValorBR(pega("valor_meta")),
    };
  }).filter((l) => l.tipo_kpi || l.ano_mes || l.valor_meta !== null);
  if (!linhas.length) { mensagem("lote-msg", "Nenhuma linha para salvar.", false); return; }

  btn.disabled = true;
  try {
    const r = await apiAdmin("POST", { acao: "metas_lote", linhas });
    if (!r.ok) { mensagem("lote-msg", r.corpo.erro || "Falha ao salvar.", false); return; }
    const { sucesso, erros } = r.corpo;
    // atualiza localmente apenas as linhas que NÃO deram erro
    const comErro = new Set((erros || []).map((e) => parseInt(e.match(/^Linha (\d+)/)?.[1] ?? "0", 10) - 1));
    linhas.forEach((l, i) => { if (!comErro.has(i)) upsertMetaLocal(l); });
    if (erros && erros.length) {
      mensagem("lote-msg", `${sucesso} salva(s). Erros:\n${erros.join("\n")}`, false);
    } else {
      mensagem("lote-msg", `${sucesso} meta(s) salva(s) com sucesso.`, true);
    }
    renderMetasLista();
    renderizar();
  } catch (e) {
    if (String(e.message) !== "401") mensagem("lote-msg", "Sem conexão com o servidor.", false);
  } finally {
    btn.disabled = false;
  }
}

function renderMetasLista() {
  const linhas = [...METAS].sort((a, b) =>
    b.ano_mes.localeCompare(a.ano_mes) ||
    a.vendedor.localeCompare(b.vendedor, "pt-BR") ||
    a.tipo_kpi.localeCompare(b.tipo_kpi, "pt-BR"));
  const total = linhas.length;
  const paginas = Math.max(Math.ceil(total / LINHAS_POR_PAGINA), 1);
  METAS_PAG.pagina = Math.max(Math.min(METAS_PAG.pagina, paginas - 1), 0);
  const ini = METAS_PAG.pagina * LINHAS_POR_PAGINA;
  const visiveis = linhas.slice(ini, ini + LINHAS_POR_PAGINA);

  $("tabela-metas").innerHTML =
    "<thead><tr><th>KPI</th><th>Vendedor</th><th>Mês</th><th>Valor da meta</th><th>Atualizada em</th></tr></thead>" +
    "<tbody>" + visiveis.map((m) => `<tr>
      <td>${escapaHTML(m.tipo_kpi)}</td>
      <td>${escapaHTML(m.vendedor)}</td>
      <td>${escapaHTML(m.ano_mes)}</td>
      <td class="num">${(+m.valor_meta).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}</td>
      <td>${fmtDataHora(m.atualizado_em)}</td>
    </tr>`).join("") + "</tbody>";
  $("metas-info").textContent =
    total ? `${ini + 1}–${Math.min(ini + LINHAS_POR_PAGINA, total)} de ${total.toLocaleString("pt-BR")} metas`
          : "Nenhuma meta cadastrada";
  $("metas-ant").disabled = METAS_PAG.pagina === 0;
  $("metas-prox").disabled = METAS_PAG.pagina >= paginas - 1;
}

// ---------------------------------------------------------------------------
// Aba Log de sincronização
// ---------------------------------------------------------------------------
function renderLog() {
  $("tabela-log").innerHTML =
    "<thead><tr><th>Executado em</th><th>Novas</th><th>Atualizadas</th>" +
    "<th>Removidas</th><th>Status</th><th>Mensagem</th></tr></thead>" +
    "<tbody>" + SYNC_LOG.map((l) => `<tr>
      <td>${fmtDataHora(l.executado_em)}</td>
      <td class="num">${l.linhas_novas ?? 0}</td>
      <td class="num">${l.linhas_atualizadas ?? 0}</td>
      <td class="num">${l.linhas_removidas ?? 0}</td>
      <td>${escapaHTML(l.status)}</td>
      <td>${escapaHTML(l.mensagem ?? "")}</td>
    </tr>`).join("") + "</tbody>";
}

// ---------------------------------------------------------------------------
// Administração: Sincronizar agora (fila de pedidos p/ o PC)
// ---------------------------------------------------------------------------
function montarAdmin() {
  $("sync-desde").value = diasAtrasISO(7);
  $("sync-desde").max = hojeISO();
  $("btn-sync").addEventListener("click", pedirSync);
  atualizarStatusSync();
}

function mostrarStatusSync(info) {
  $("btn-sync").disabled = info.em_andamento;
  const u = info.ultimo;
  let txt = "";
  if (info.em_andamento) {
    txt = "⏳ Sincronização em andamento no PC. O resultado aparece aqui em alguns minutos.";
  } else if (u) {
    const quando = fmtDataHora(u.atualizado_em);
    if (u.status === "concluido") txt = `✅ Última sincronização (${quando}): ${u.mensagem}`;
    else if (u.status === "falhou") txt = `⚠️ Última tentativa falhou (${quando}): ${u.mensagem}`;
  }
  $("sync-status").textContent = txt;
}

async function atualizarStatusSync() {
  try {
    const r = await apiAdmin("GET");
    if (!r.ok) return;
    mostrarStatusSync(r.corpo);
    if (r.corpo.em_andamento && !syncTimer) {
      syncTimer = setInterval(async () => {
        const r2 = await apiAdmin("GET");
        if (r2.ok) {
          mostrarStatusSync(r2.corpo);
          if (!r2.corpo.em_andamento) {
            clearInterval(syncTimer); syncTimer = null;
            $("sync-status").textContent += " — recarregue a página para ver os dados novos.";
          }
        }
      }, 20000);
    }
  } catch { /* rede: tenta de novo na próxima ação */ }
}

async function pedirSync() {
  const desde = $("sync-desde").value || diasAtrasISO(7);
  const dias = Math.max(Math.round((new Date(hojeISO()) - new Date(desde)) / 86400000), 0);
  $("btn-sync").disabled = true;
  try {
    const r = await apiAdmin("POST", { acao: "sync", dias });
    if (r.status === 409) {
      $("sync-status").textContent = "⏳ Já existe uma sincronização em andamento. Aguarde ela terminar.";
    } else if (r.ok) {
      $("sync-status").textContent =
        "✅ Pedido enviado! O PC vai sincronizar em instantes. O status atualiza aqui sozinho.";
    } else {
      $("sync-status").textContent = "⚠️ " + (r.corpo.erro || "Falha ao enviar o pedido.");
      $("btn-sync").disabled = false;
      return;
    }
    atualizarStatusSync();
  } catch (e) {
    if (String(e.message) !== "401") {
      $("sync-status").textContent = "⚠️ Sem conexão com o servidor.";
      $("btn-sync").disabled = false;
    }
  }
}

// ---------------------------------------------------------------------------
// Abas
// ---------------------------------------------------------------------------
document.querySelectorAll(".cd-tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".cd-tabs .tab").forEach((b) => b.classList.remove("ativa"));
    document.querySelectorAll(".aba-conteudo").forEach((a) => a.classList.add("oculto"));
    btn.classList.add("ativa");
    $(btn.dataset.aba).classList.remove("oculto");
    // gráficos inicializados com a aba oculta precisam de resize ao aparecer
    Object.values(GRAFICOS).forEach((g) => g.resize());
  });
});
$("tab-ant").addEventListener("click", () => { TABELA.pagina--; renderTabela(); });
$("tab-prox").addEventListener("click", () => { TABELA.pagina++; renderTabela(); });
$("repo-ant").addEventListener("click", () => { REPO_PAG.pagina--; renderTabelaRepo(REPO_DADOS); });
$("repo-prox").addEventListener("click", () => { REPO_PAG.pagina++; renderTabelaRepo(REPO_DADOS); });

// Visão da aba Produtos: grandes classes x detalhado
function mudarVisaoProdutos(visao) {
  PRODUTOS_VISAO = visao;
  $("visao-grandes").classList.toggle("ativa", visao === "grandes");
  $("visao-detalhe").classList.toggle("ativa", visao === "detalhe");
  renderizar();
}
$("visao-grandes").addEventListener("click", () => mudarVisaoProdutos("grandes"));
$("visao-detalhe").addEventListener("click", () => mudarVisaoProdutos("detalhe"));

// Seletor de loja da aba Financeiro
document.querySelectorAll("#toggle-loja button").forEach((btn) => {
  btn.addEventListener("click", () => {
    LOJA_SEL = btn.dataset.loja;
    document.querySelectorAll("#toggle-loja button").forEach(
      (b) => b.classList.toggle("ativa", b === btn));
    renderizar();
  });
});

// ---------------------------------------------------------------------------
// Render geral
// ---------------------------------------------------------------------------
function renderizar() {
  const { base, filtrado } = aplicarFiltros();
  const mesesPeriodo = (FILTROS.inicio && FILTROS.fim && FILTROS.inicio <= FILTROS.fim)
    ? mesesNoPeriodo(FILTROS.inicio, FILTROS.fim)
    : [hojeISO().slice(0, 7)];
  const vendedoresAlvo = FILTROS.vendedores.length ? FILTROS.vendedores : [VENDEDOR_GERAL];

  ULTIMO_FILTRADO = filtrado;
  renderKpis(filtrado, base, mesesPeriodo, vendedoresAlvo);
  renderGraficoVendas(filtrado, mesesPeriodo, vendedoresAlvo);
  renderRankings(filtrado);
  renderSegmento(filtrado, mesesPeriodo);
  renderComissionado(filtrado, mesesPeriodo);
  renderProdutos(mesesPeriodo);
  renderFinanceiro(mesesPeriodo);
  renderReposicoes(mesesPeriodo);
  renderTabela();
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

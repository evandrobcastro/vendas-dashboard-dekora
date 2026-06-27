"""Dashboard de Vendas - Casa Dekora"""
import base64
import sys
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import bcrypt
import pandas as pd
import streamlit as st

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from database import (  # noqa: E402
    get_connection,
    init_db,
    criar_pedido_sync,
    pedido_sync_em_andamento,
    ultimo_pedido_sync,
)

LOGO_PATH = BASE / "dashboard" / "assets" / "logo_casadekora.png"
LOGO_NEGATIVO_PATH = BASE / "dashboard" / "assets" / "logo_negativo.png"

st.set_page_config(
    page_title="Boletim Casa Dekora",
    page_icon=str(LOGO_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)

_LOGO_NEGATIVO_B64 = base64.b64encode(LOGO_NEGATIVO_PATH.read_bytes()).decode()

# ---------------------------------------------------------------------------
# Identidade visual Casa Dekora (terracota #8B3C05 como acento, fundo areia)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap');

    :root {
        --terracota: #8B3C05;
        --preto: #000000;
        --branco: #FFFFFF;
        --areia: #EFE7DA;
        --taupe: #B9AD9E;
        --madeira: #8A6A4A;
        --verde: #2E7D32;
        --vermelho: #C62828;
        --amarelo: #B8860B;
    }

    .stApp, .stApp * { font-family: 'Aileron', 'Montserrat', sans-serif; }

    /* A regra '*' acima sobrescreve a fonte de icones do Streamlit (Material
       Symbols), fazendo o nome do icone aparecer como texto cru — ex.:
       "keyboard_double_arrow_left" no botao de recolher a barra lateral e
       "arrow_..." no painel "Administracao". Aqui restauramos a fonte de
       icone apenas nesses elementos. */
    .stApp [data-testid="stIconMaterial"],
    .stApp span[data-testid="stIconMaterial"],
    .stApp [class*="material-symbols"],
    .stApp [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
                     'Material Icons' !important;
    }

    .stApp { background-color: var(--areia); }

    /* Cartoes genericos (top vendedores, metas, registros recentes) */
    .cd-card {
        background: var(--branco);
        border-radius: 10px;
        padding: 18px 20px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        margin-bottom: 18px;
    }
    .cd-card h4 {
        margin: 0 0 14px 0;
        font-size: 13px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        color: var(--preto);
    }

    /* Mini grafico de barras (Vendas por mes) */
    .cd-bars { display: flex; align-items: flex-end; gap: 14px; height: 170px; padding-top: 10px; }
    .cd-bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
    .cd-bar-value { font-size: 12px; font-weight: 700; color: var(--preto); margin-bottom: 4px; }
    .cd-bar-shape { width: 70%; max-width: 42px; border-radius: 4px 4px 0 0; background: linear-gradient(180deg, #C9712E 0%, var(--terracota) 100%); }
    .cd-bar-label { font-size: 11px; color: var(--madeira); margin-top: 6px; font-weight: 600; }

    /* Legenda manual do grafico "projetado vs realizado" (combina com o
       gradiente das barras, que o Vega-Lite nao consegue exibir na legenda). */
    .cd-chart-legend { display: flex; gap: 22px; justify-content: center; margin-top: -8px; font-size: 12px; font-weight: 600; color: var(--madeira); }
    .cd-chart-legend i { display: inline-block; width: 13px; height: 13px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }

    /* Ranking de vendedores com barras horizontais */
    .cd-rank-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
    .cd-rank-num { width: 18px; font-weight: 800; color: var(--madeira); font-size: 13px; }
    .cd-rank-name { width: 110px; font-size: 13px; color: var(--preto); font-weight: 600; flex-shrink: 0; }
    .cd-rank-bar-bg { flex: 1; background: var(--areia); border-radius: 6px; height: 10px; overflow: hidden; }
    .cd-rank-bar-fill { height: 100%; background: linear-gradient(90deg, #C9712E, var(--terracota)); border-radius: 6px; }
    .cd-rank-value { width: 70px; text-align: right; font-size: 12px; font-weight: 700; color: var(--preto); }

    /* Barras de progresso de metas */
    .cd-progress-row { margin-bottom: 16px; }
    .cd-progress-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
    .cd-progress-label { font-size: 13px; font-weight: 700; color: var(--preto); text-transform: uppercase; letter-spacing: 0.3px; }
    .cd-progress-text { font-size: 12px; color: var(--madeira); font-weight: 600; }
    .cd-progress-bg { background: var(--areia); border-radius: 8px; height: 14px; overflow: hidden; }
    .cd-progress-fill { height: 100%; background: var(--terracota); border-radius: 8px; }

    /* Tabela "Ultimos registros" */
    .cd-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .cd-table thead th {
        background: var(--preto); color: var(--branco); text-align: left;
        padding: 10px 12px; font-weight: 700; text-transform: uppercase; font-size: 11px; letter-spacing: 0.3px;
    }
    .cd-table tbody td { padding: 10px 12px; border-bottom: 1px solid #EFE7DA; color: var(--preto); }
    .cd-table tbody tr:nth-child(even) { background: #FAF6EF; }
    .cd-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 700; }
    .cd-badge-verde { background: #E3F1E1; color: var(--verde); }
    .cd-badge-vermelho { background: #FBE4E2; color: var(--vermelho); }
    .cd-badge-amarelo { background: #FBF1DA; color: var(--amarelo); }
    .cd-badge-neutro { background: var(--areia); color: var(--madeira); }

    /* Deltas dos KPIs (vs periodo anterior) */
    .cd-delta { font-size: 12px; font-weight: 700; margin-top: 2px; }
    .cd-delta-up { color: var(--verde); }
    .cd-delta-down { color: var(--vermelho); }
    .cd-delta-neutro { color: var(--madeira); font-weight: 600; }

    /* Cola o texto comparativo (% da meta) logo abaixo da caixa de KPI,
       removendo o vao vertical padrao do Streamlit entre os dois blocos. */
    div[data-testid="stMetric"] { margin-bottom: 0 !important; }
    div[data-testid="stElementContainer"]:has(.cd-delta) { margin-top: -14px; }
    .cd-delta { margin-bottom: 10px; }

    /* Barra preta no topo do conteudo, com logo negativo + titulo */
    .cd-topbar {
        background: var(--preto);
        color: var(--branco);
        padding: 18px 28px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        gap: 14px;
        margin-bottom: 6px;
    }
    .cd-topbar img { height: 36px; }
    .cd-topbar .cd-title { font-weight: 800; font-size: 22px; letter-spacing: 0.3px; }
    .cd-topbar .cd-title span { color: var(--terracota); }
    .cd-accent-bar { height: 5px; background: var(--terracota); border-radius: 0 0 6px 6px; margin-bottom: 24px; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: var(--branco);
        border-right: 1px solid #E3D9C8;
    }
    /* Garante que a barra de filtros apareca sempre no desktop, mesmo que o
       Streamlit tente recolhe-la (no celular continua como sobreposicao,
       aberta/fechada pelo botao de setas). */
    @media (min-width: 641px) {
        section[data-testid="stSidebar"] {
            transform: none !important;
            visibility: visible !important;
            min-width: 244px !important;
        }
        section[data-testid="stSidebar"][aria-expanded="false"] {
            margin-left: 0 !important;
        }
    }
    section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        color: var(--terracota) !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 800;
        border-bottom: 2px solid var(--terracota);
        padding-bottom: 6px;
    }

    /* Abas */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 2px solid var(--taupe); }
    .stTabs [data-baseweb="tab"] {
        color: var(--madeira);
        font-weight: 700;
        font-size: 15px;
        padding: 10px 18px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--terracota) !important;
        border-bottom: 3px solid var(--terracota) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] { background-color: var(--terracota) !important; }

    /* Cards de KPI (st.metric) */
    div[data-testid="stMetric"] {
        background: var(--branco);
        border-left: 5px solid var(--terracota);
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    div[data-testid="stMetricLabel"] { color: var(--madeira); font-weight: 600; text-transform: uppercase; font-size: 12px; }
    div[data-testid="stMetricValue"] { color: var(--preto); font-weight: 800; }

    /* Botoes */
    .stButton > button, .stFormSubmitButton > button {
        background-color: var(--terracota);
        color: var(--branco);
        border: none;
        border-radius: 6px;
        font-weight: 700;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        background-color: var(--madeira);
        color: var(--branco);
    }

    /* Paineis (tabelas, expanders, graficos) */
    div[data-testid="stExpander"], div[data-testid="stDataFrame"],
    div[data-testid="stVegaLiteChart"] {
        background: var(--branco);
        border-radius: 10px;
        padding: 16px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        box-sizing: border-box;
        overflow: hidden;
        width: 100%;
    }
    div[data-testid="stVegaLiteChart"] > div { width: 100% !important; }
    div[data-testid="stVegaLiteChart"] canvas,
    div[data-testid="stVegaLiteChart"] svg {
        max-width: 100% !important;
    }

    /* Esconde so o menu Deploy/hamburguer/decoracao, mantendo o header
       visivel para nao perder o botao de recolher/expandir a sidebar */
    header[data-testid="stHeader"] {
        background-color: transparent;
        box-shadow: none;
        z-index: 999999;
    }
    div[data-testid="stToolbar"] { display: none; }
    div[data-testid="stDecoration"] { display: none; }
    button[data-testid="stSidebarCollapsedControl"],
    div[data-testid="stSidebarCollapsedControl"] {
        z-index: 999999 !important;
        visibility: visible !important;
        display: flex !important;
    }
    button[data-testid="stSidebarCollapsedControl"] svg,
    div[data-testid="stSidebarCollapsedControl"] svg {
        fill: var(--terracota) !important;
    }

    /* Mobile: reduz espacamentos e fonte do topo */
    @media (max-width: 640px) {
        .cd-topbar { padding: 12px 16px; gap: 10px; }
        .cd-topbar img { height: 26px; }
        .cd-topbar .cd-title { font-size: 16px; }
        div[data-testid="stMetric"] { padding: 10px 12px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------
def autenticar(email: str, senha: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT email, senha_hash, nome FROM usuarios WHERE email = %s", (email.lower().strip(),))
    row = cur.fetchone()
    conn.close()
    if row and bcrypt.checkpw(senha.encode("utf-8"), row[1].encode("utf-8")):
        return {"email": row[0], "nome": row[2]}
    return None


def tela_login():
    st.markdown(
        f"""
        <div class="cd-topbar">
            <img src="data:image/png;base64,{_LOGO_NEGATIVO_B64}">
            <div class="cd-title">Boletim <span>Casa Dekora</span></div>
        </div>
        <div class="cd-accent-bar"></div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar")
    if ok:
        usuario = autenticar(email, senha)
        if usuario:
            st.session_state["usuario"] = usuario
            st.rerun()
        else:
            st.error("E-mail ou senha incorretos.")


if "usuario" not in st.session_state:
    init_db()
    tela_login()
    st.stop()


# ---------------------------------------------------------------------------
# Carregamento de dados
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM registros", conn)
    conn.close()
    # Normaliza espacos sobrando nos nomes (o ERP as vezes grava "NOME ").
    # Sem isso, o filtro de vendedor e o casamento das metas por vendedor
    # falham (a meta e gravada sem espaco).
    for col in ("vendedor", "cidade", "cliente"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    for col in ("data_cadastro", "data_aprovacao"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    # Data de referencia para filtros de periodo: vendas (aprovado/fechado)
    # usam a data de aprovacao; orcamentos em aberto usam a data de cadastro.
    df["data_referencia"] = df["data_cadastro"].where(
        df["tipo"] != "venda", df["data_aprovacao"]
    )
    return df


@st.cache_data(ttl=60)
def carregar_sync_log() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM sync_log ORDER BY executado_em DESC LIMIT 20", conn)
    conn.close()
    return df


df = carregar_dados()

# ---------------------------------------------------------------------------
# Sidebar: usuario, filtros e sincronizacao manual
# ---------------------------------------------------------------------------
with st.sidebar:
    st.write(f"Logado como **{st.session_state['usuario']['nome']}**")
    if st.button("Sair"):
        del st.session_state["usuario"]
        st.rerun()

    st.divider()
    st.header("Filtros")

    if df.empty:
        st.info("Banco ainda sem dados. Sincronize para começar.")
        periodo = None
        vendedores_sel, cidades_sel, situacoes_sel = [], [], []
        valor_min_sel, valor_max_sel = None, None
    else:
        data_min = df["data_referencia"].min().date()
        data_max = date.today()
        inicio_ano_atual = date.today().replace(month=1, day=1)
        periodo = st.date_input(
            "Período (cadastro p/ orçamentos, aprovação p/ vendas)",
            value=(inicio_ano_atual, data_max),
            min_value=data_min,
            max_value=data_max,
        )

        vendedores = sorted(df["vendedor"].dropna().unique())
        cidades = sorted(df["cidade"].dropna().unique())
        situacoes = sorted(df["situacao"].dropna().unique())

        vendedores_sel = st.multiselect("Vendedor", vendedores)
        cidades_sel = st.multiselect("Cidade", cidades)
        situacoes_sel = st.multiselect("Situação", situacoes)

        st.caption("Faixa de valor do pedido (R$) — deixe em branco para não limitar")
        col_de, col_ate = st.columns(2)
        with col_de:
            valor_de_texto = st.text_input("De:", value="", placeholder="sem mínimo")
        with col_ate:
            valor_ate_texto = st.text_input("Até:", value="", placeholder="sem máximo")

        def _parse_valor(texto: str) -> float | None:
            texto = texto.strip().replace(".", "").replace(",", ".")
            if not texto:
                return None
            try:
                return float(texto)
            except ValueError:
                st.sidebar.error(f"Valor inválido: '{texto}'")
                return None

        valor_min_sel = _parse_valor(valor_de_texto)
        valor_max_sel = _parse_valor(valor_ate_texto)

    st.divider()
    with st.expander("Administração"):
        st.caption(
            "A sincronização baixa os dados do ERP e roda no PC da Casa Dekora "
            "(que fica ligado). Você pode pedir daqui de qualquer lugar — celular "
            "ou outro computador — e o resultado aparece em alguns minutos."
        )
        data_desde = st.date_input(
            "Sincronizar desde",
            value=date.today() - timedelta(days=7),
            max_value=date.today(),
        )

        em_andamento = pedido_sync_em_andamento()
        if em_andamento:
            st.info("⏳ Já existe uma sincronização em andamento. Aguarde ela terminar.")

        if st.button("🔄 Sincronizar agora", disabled=em_andamento):
            dias = max((date.today() - data_desde).days, 0)
            criar_pedido_sync(st.session_state["usuario"]["email"], dias)
            st.success(
                "Pedido enviado! O PC vai sincronizar em instantes. "
                "Recarregue a página em alguns minutos para ver os dados novos."
            )
            st.rerun()

        ultimo = ultimo_pedido_sync()
        if ultimo:
            quando = ultimo["atualizado_em"]
            quando_txt = quando.strftime("%d/%m %H:%M") if hasattr(quando, "strftime") else ""
            if ultimo["status"] == "concluido":
                st.caption(f"✅ Última sincronização ({quando_txt}): {ultimo['mensagem']}")
            elif ultimo["status"] == "falhou":
                st.caption(f"⚠️ Última tentativa falhou ({quando_txt}): {ultimo['mensagem']}")
            elif ultimo["status"] == "processando":
                st.caption("🔄 Sincronizando agora no PC...")

# ---------------------------------------------------------------------------
# Aplica filtros
# ---------------------------------------------------------------------------
# Filtros nao-temporais (vendedor/cidade/situacao/valor). Ficam separados do
# recorte de periodo porque o "Forecast de vendas" usa uma janela propria
# (orcamentos dos ultimos 30 dias), independente do periodo selecionado.
df_base = df.copy()
if vendedores_sel:
    df_base = df_base[df_base["vendedor"].isin(vendedores_sel)]
if cidades_sel:
    df_base = df_base[df_base["cidade"].isin(cidades_sel)]
if situacoes_sel:
    df_base = df_base[df_base["situacao"].isin(situacoes_sel)]
if valor_min_sel is not None:
    df_base = df_base[df_base["valor"] >= valor_min_sel]
if valor_max_sel is not None:
    df_base = df_base[df_base["valor"] <= valor_max_sel]

# Recorte do periodo selecionado (vendas por aprovacao, orcamentos por cadastro)
df_filtrado = df_base.copy()
if not df.empty and periodo and len(periodo) == 2:
    inicio, fim = periodo
    df_filtrado = df_filtrado[
        (df_filtrado["data_referencia"].dt.date >= inicio)
        & (df_filtrado["data_referencia"].dt.date <= fim)
    ]

# ---------------------------------------------------------------------------
# Conteudo principal
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="cd-topbar">
        <img src="data:image/png;base64,{_LOGO_NEGATIVO_B64}">
        <div class="cd-title">Boletim <span>Casa Dekora</span></div>
    </div>
    <div class="cd-accent-bar"></div>
    """,
    unsafe_allow_html=True,
)

aba_tabela, aba_kpis, aba_metas, aba_log = st.tabs(
    ["Tabela", "Comercial", "Metas", "Log de sincronização"]
)

with aba_tabela:
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)


def _kpis_periodo(frame: pd.DataFrame) -> dict:
    vendas = frame[frame["tipo"] == "venda"]
    orcamentos = frame[frame["tipo"] == "orcamento"]
    abertos = orcamentos[~orcamentos["situacao"].str.lower().str.contains("cancelad", na=False)]

    total_vendido = vendas["valor"].sum()
    qtd_vendas = len(vendas)
    ticket_medio = total_vendido / qtd_vendas if qtd_vendas else 0

    total_orcado = orcamentos["valor"].sum()
    qtd_orcamentos = len(orcamentos)
    ticket_medio_orcamentos = total_orcado / qtd_orcamentos if qtd_orcamentos else 0

    qtd_orcamentos_abertos = len(abertos)
    # Taxa de conversao por VALOR: R$ vendido / R$ orcado no periodo.
    taxa_conversao = (total_vendido / total_orcado * 100) if total_orcado else 0
    return {
        "total_vendido": total_vendido,
        "ticket_medio": ticket_medio,
        "qtd_vendas": qtd_vendas,
        "taxa_conversao": taxa_conversao,
        "total_orcado": total_orcado,
        "ticket_medio_orcamentos": ticket_medio_orcamentos,
        "qtd_orcamentos": qtd_orcamentos,
        "orcamentos_abertos": qtd_orcamentos_abertos,
    }


# Como agregar a meta ao longo do periodo: KPIs que ACUMULAM (vendas, pedidos,
# orcamentos) somam as metas dos meses do periodo; KPIs de MEDIA/proporcao
# (ticket medio, taxa de conversao, forecast mensal) usam a media das metas.
AGREGACAO_META = {
    "valor_vendas": "soma",
    "valor_orcamentos": "soma",
    "qtd_vendas": "soma",
    "qtd_orcamentos": "soma",
    "ticket_medio": "media",
    "ticket_medio_orcamentos": "media",
    "taxa_conversao": "media",
    "forecast_vendas": "media",
}


def _meses_no_periodo(inicio: date, fim: date) -> list:
    """Lista de 'YYYY-MM' de cada mes entre inicio e fim (inclusive)."""
    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return meses


def _meta_alvo(metas_df: pd.DataFrame, tipo_kpi: str, meses_periodo: list,
               vendedores_alvo: list) -> float | None:
    """Meta agregada do periodo para um KPI, respeitando o filtro de vendedor
    (ou GERAL). Soma ou media conforme AGREGACAO_META. None se nao houver meta."""
    if metas_df.empty:
        return None
    sel = metas_df[
        (metas_df["tipo_kpi"] == tipo_kpi)
        & (metas_df["ano_mes"].isin(meses_periodo))
        & (metas_df["vendedor"].isin(vendedores_alvo))
    ]
    valores = sel["valor_meta"].astype(float)
    valores = valores[valores != 0]
    if valores.empty:
        return None
    return valores.sum() if AGREGACAO_META.get(tipo_kpi, "soma") == "soma" else valores.mean()


def _meta_delta_html(meta: float | None, realizado: float, fmt) -> str:
    """Comparativo da caixa de KPI com a meta agregada do periodo."""
    if not meta:
        return '<div class="cd-delta cd-delta-neutro">sem meta para este período</div>'
    pct = realizado / meta * 100
    atingiu = realizado >= meta
    seta = "▲" if atingiu else "▼"
    classe = "cd-delta-up" if atingiu else "cd-delta-down"
    return f'<div class="cd-delta {classe}">{seta} {pct:.0f}% da meta ({fmt(meta)})</div>'


with aba_kpis:
    from metas import listar_metas, VENDEDOR_GERAL

    atual = _kpis_periodo(df_filtrado)

    # Forecast de vendas: valor dos orcamentos cadastrados nos ultimos 30 dias
    # (independente do periodo selecionado) multiplicado pela taxa de conversao.
    forecast = 0.0
    if not df.empty:
        limite_30 = date.today() - timedelta(days=30)
        orc_30d = df_base[
            (df_base["tipo"] == "orcamento")
            & (df_base["data_cadastro"].dt.date >= limite_30)
        ]
        forecast = orc_30d["valor"].sum() * atual["taxa_conversao"] / 100

    # Metas: base do comparativo de cada caixa. Agrega as metas de TODOS os
    # meses do periodo selecionado (soma ou media, conforme o KPI) e respeita
    # o filtro de vendedor — se nenhum vendedor estiver filtrado, usa GERAL.
    metas_df = listar_metas()
    if periodo and len(periodo) == 2:
        meses_periodo = _meses_no_periodo(periodo[0], periodo[1])
    else:
        meses_periodo = [date.today().strftime("%Y-%m")]
    vendedores_alvo = vendedores_sel if vendedores_sel else [VENDEDOR_GERAL]

    def delta(tipo_kpi, realizado, fmt):
        meta = _meta_alvo(metas_df, tipo_kpi, meses_periodo, vendedores_alvo)
        return _meta_delta_html(meta, realizado, fmt)

    moeda = lambda v: f"R$ {v:,.0f}"
    inteiro = lambda v: f"{v:,.0f}".replace(",", ".")
    pct_fmt = lambda v: f"{v:.0f}%"

    # Linha 1 — Vendas
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Vendas no período", f"R$ {atual['total_vendido']:,.2f}")
        st.markdown(delta("valor_vendas", atual["total_vendido"], moeda), unsafe_allow_html=True)
    with c2:
        st.metric("Ticket médio", f"R$ {atual['ticket_medio']:,.2f}")
        st.markdown(delta("ticket_medio", atual["ticket_medio"], moeda), unsafe_allow_html=True)
    with c3:
        st.metric("Número de pedidos", inteiro(atual["qtd_vendas"]),
                  help="Quantidade de vendas (pedidos com status aprovado/fechado) no período.")
        st.markdown(delta("qtd_vendas", atual["qtd_vendas"], inteiro), unsafe_allow_html=True)
    with c4:
        st.metric("Taxa de conversão", f"{atual['taxa_conversao']:.0f}%")
        st.markdown(delta("taxa_conversao", atual["taxa_conversao"], pct_fmt), unsafe_allow_html=True)

    # Linha 2 — Orçamentos
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.metric("Orçamentos no período", f"R$ {atual['total_orcado']:,.2f}",
                  help="Valor total dos orçamentos cadastrados no período.")
        st.markdown(delta("valor_orcamentos", atual["total_orcado"], moeda), unsafe_allow_html=True)
    with c6:
        st.metric("Ticket médio de orçamentos", f"R$ {atual['ticket_medio_orcamentos']:,.2f}",
                  help="Valor total de orçamentos dividido pelo número de orçamentos no período.")
        st.markdown(delta("ticket_medio_orcamentos", atual["ticket_medio_orcamentos"], moeda), unsafe_allow_html=True)
    with c7:
        st.metric("Número total de orçamentos", inteiro(atual["qtd_orcamentos"]),
                  help="Quantidade de orçamentos cadastrados no período.")
        st.markdown(delta("qtd_orcamentos", atual["qtd_orcamentos"], inteiro), unsafe_allow_html=True)
    with c8:
        st.metric("Forecast de vendas", f"R$ {forecast:,.2f}",
                  help="Valor dos orçamentos cadastrados nos últimos 30 dias × taxa de conversão.")
        st.markdown(delta("forecast_vendas", forecast, moeda), unsafe_allow_html=True)

    st.write("")

    # --- Vendas: projetado (metas) vs realizado, mes a mes ---
    # Segue os MESMOS filtros das caixas: meses do periodo selecionado e
    # vendedor(es) filtrado(s) (ou GERAL). Ocupa a largura inteira.
    meses_pt = {1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
                7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez"}

    # Vendas realizadas por mes, ja com periodo + filtros (df_filtrado).
    vendas_periodo = df_filtrado[df_filtrado["tipo"] == "venda"].copy()
    vendas_periodo["ano_mes"] = vendas_periodo["data_aprovacao"].dt.strftime("%Y-%m")
    vendas_por_am = vendas_periodo.groupby("ano_mes")["valor"].sum()

    # Metas de valor_vendas para os vendedores alvo, somadas por mes (varias
    # linhas quando ha mais de um vendedor selecionado).
    metas_vendas = (
        metas_df[
            (metas_df["tipo_kpi"] == "valor_vendas")
            & (metas_df["ano_mes"].isin(meses_periodo))
            & (metas_df["vendedor"].isin(vendedores_alvo))
        ]
        if not metas_df.empty
        else pd.DataFrame(columns=["ano_mes", "valor_meta"])
    )
    metas_por_am = metas_vendas.groupby("ano_mes")["valor_meta"].sum()

    linhas_chart = []
    ordem_meses = []
    for am in meses_periodo:
        rotulo_mes = meses_pt[int(am.split("-")[1])]
        ordem_meses.append(rotulo_mes)
        linhas_chart.append({"mes": rotulo_mes, "Série": "Vendas",
                             "valor": float(vendas_por_am.get(am, 0.0))})
        linhas_chart.append({"mes": rotulo_mes, "Série": "Metas",
                             "valor": float(metas_por_am.get(am, 0.0))})
    chart_df = pd.DataFrame(linhas_chart)
    meses_labels = ordem_meses  # ordem do eixo X

    if chart_df["valor"].sum() == 0:
        st.markdown(
            '<div class="cd-card"><h4>Vendas — projetado vs realizado</h4>'
            'Sem vendas nem metas para o período/filtros selecionados.</div>',
            unsafe_allow_html=True,
        )
    else:
        # Gradientes terracota (Vendas) e cinza (Metas), no espirito do grafico
        # anterior; cantos superiores arredondados e rotulos "R$ Xk" escuros.
        def _grad(cor_base, cor_topo):
            return {
                "gradient": "linear", "x1": 0, "y1": 1, "x2": 0, "y2": 0,
                "stops": [
                    {"offset": 0, "color": cor_base},
                    {"offset": 1, "color": cor_topo},
                ],
            }

        # Gradiente nao e aceito no range de cor (schema do Vega-Lite), entao
        # cada serie e uma camada propria com o gradiente no preenchimento.
        base_chart = alt.Chart(chart_df).transform_calculate(
            rotulo="'R$ ' + format(datum.valor / 1000, ',.0f') + 'k'"
        ).encode(
            x=alt.X("mes:N", sort=meses_labels, title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("Série:N", scale=alt.Scale(domain=["Vendas", "Metas"])),
            y=alt.Y("valor:Q", title=None, axis=alt.Axis(format="~s")),
        )

        def _camada_barras(serie, gradiente):
            return base_chart.transform_filter(
                alt.datum["Série"] == serie
            ).mark_bar(
                cornerRadiusTopLeft=4, cornerRadiusTopRight=4, fill=gradiente,
            ).encode(
                tooltip=[
                    alt.Tooltip("mes:N", title="Mês"),
                    alt.Tooltip("Série:N", title="Série"),
                    alt.Tooltip("valor:Q", title="Valor", format=",.0f"),
                ],
            )

        barras_vendas = _camada_barras("Vendas", _grad("#8B3C05", "#C9712E"))
        barras_metas = _camada_barras("Metas", _grad("#A89B89", "#C7BCAE"))
        rotulos = base_chart.mark_text(
            dy=-6, fontSize=11, fontWeight="bold", color="#000000",
        ).encode(
            text=alt.Text("rotulo:N"),
            opacity=alt.condition("datum.valor > 0", alt.value(1), alt.value(0)),
        )
        grafico = (barras_vendas + barras_metas + rotulos).properties(
            height=320,
            title=alt.TitleParams(
                "Vendas — projetado vs realizado",
                anchor="start", fontSize=14, fontWeight="bold", color="#000000",
            ),
        )
        st.altair_chart(grafico, use_container_width=True)
        # Legenda manual, combinando com o gradiente das barras.
        st.markdown(
            '<div class="cd-chart-legend">'
            '<span><i style="background:linear-gradient(180deg,#C9712E,#8B3C05)"></i>Vendas</span>'
            '<span><i style="background:linear-gradient(180deg,#C7BCAE,#A89B89)"></i>Metas</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # --- Rankings por vendedor (mesmo periodo/filtros), lado a lado ---
    # Esquerda: vendas por vendedor; direita: orcamentos por vendedor.
    def _ranking_html(titulo, serie):
        if serie.empty:
            return f'<div class="cd-card"><h4>{titulo}</h4>Sem dados no filtro selecionado.</div>'
        maximo = serie.max() or 1
        linhas = "".join(
            f'<div class="cd-rank-row">'
            f'<div class="cd-rank-num">{i}</div>'
            f'<div class="cd-rank-name">{nome}</div>'
            f'<div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:{valor/maximo*100:.0f}%"></div></div>'
            f'<div class="cd-rank-value">R$ {valor/1000:,.0f}k</div>'
            f'</div>'
            for i, (nome, valor) in enumerate(serie.items(), start=1)
        )
        return f'<div class="cd-card"><h4>{titulo}</h4>{linhas}</div>'

    top_vendas = (
        df_filtrado[df_filtrado["tipo"] == "venda"]
        .groupby("vendedor")["valor"].sum().sort_values(ascending=False).head(4)
    )
    top_orcamentos = (
        df_filtrado[df_filtrado["tipo"] == "orcamento"]
        .groupby("vendedor")["valor"].sum().sort_values(ascending=False).head(4)
    )
    col_vend, col_orc = st.columns(2)
    with col_vend:
        st.markdown(_ranking_html("Top vendedores — vendas", top_vendas), unsafe_allow_html=True)
    with col_orc:
        st.markdown(_ranking_html("Top vendedores — orçamentos", top_orcamentos), unsafe_allow_html=True)

with aba_metas:
    from metas import upsert_meta, upsert_lote, listar_metas, VENDEDOR_GERAL, TIPOS_KPI_SUGERIDOS

    st.subheader("Cadastrar/atualizar uma meta")
    st.caption(
        "Inserir a mesma combinação de KPI + vendedor + mês de novo apenas "
        "atualiza o valor (use para replanejamento)."
    )
    with st.form("form_meta_individual"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            tipo_kpi_opcoes = TIPOS_KPI_SUGERIDOS + ["Outro (digitar abaixo)"]
            tipo_kpi_sel = st.selectbox("KPI", tipo_kpi_opcoes)
            tipo_kpi_custom = st.text_input("KPI personalizado", disabled=tipo_kpi_sel != "Outro (digitar abaixo)")
        with col2:
            vendedores_existentes = [VENDEDOR_GERAL] + (
                sorted(df["vendedor"].dropna().unique()) if not df.empty else []
            )
            vendedor_sel = st.selectbox("Vendedor (ou Geral)", vendedores_existentes + ["Outro (digitar abaixo)"])
            vendedor_custom = st.text_input("Vendedor personalizado", disabled=vendedor_sel != "Outro (digitar abaixo)")
        with col3:
            mes_ref = st.date_input("Mês de referência", value=date.today().replace(day=1))
        with col4:
            valor_meta_input = st.number_input("Valor da meta", min_value=0.0, step=100.0)

        salvar_individual = st.form_submit_button("💾 Salvar meta")

    if salvar_individual:
        tipo_kpi_final = tipo_kpi_custom if tipo_kpi_sel == "Outro (digitar abaixo)" else tipo_kpi_sel
        vendedor_final = vendedor_custom if vendedor_sel == "Outro (digitar abaixo)" else vendedor_sel
        ano_mes_final = mes_ref.strftime("%Y-%m")
        if not tipo_kpi_final:
            st.error("Informe o KPI.")
        else:
            try:
                upsert_meta(tipo_kpi_final, vendedor_final, ano_mes_final, valor_meta_input)
                st.success(f"Meta salva: {tipo_kpi_final} / {vendedor_final} / {ano_mes_final}")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar: {e}")

    st.divider()
    st.subheader("Inserção em lote")
    st.caption(
        "Edite a tabela abaixo (adicione/cole várias linhas) e clique em "
        "Salvar todas. vendedor='GERAL' para meta da empresa. ano_mes no "
        "formato AAAA-MM."
    )
    modelo_lote = pd.DataFrame(
        [{"tipo_kpi": "valor_vendas", "vendedor": VENDEDOR_GERAL, "ano_mes": date.today().strftime("%Y-%m"), "valor_meta": 0.0}]
    )
    lote_editado = st.data_editor(modelo_lote, num_rows="dynamic", use_container_width=True, key="editor_lote_metas")

    if st.button("💾 Salvar todas"):
        resultado_lote = upsert_lote(lote_editado)
        if resultado_lote["erros"]:
            st.warning(f"{resultado_lote['sucesso']} salva(s). Erros:\n" + "\n".join(resultado_lote["erros"]))
        else:
            st.success(f"{resultado_lote['sucesso']} meta(s) salva(s) com sucesso.")
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Metas cadastradas")
    st.dataframe(listar_metas(), use_container_width=True, hide_index=True)

with aba_log:
    log = carregar_sync_log()
    st.dataframe(log, use_container_width=True, hide_index=True)

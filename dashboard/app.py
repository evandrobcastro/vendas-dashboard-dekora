"""Dashboard de Vendas - Casa Dekora"""
import base64
import sys
from datetime import date, timedelta
from pathlib import Path

import bcrypt
import pandas as pd
import streamlit as st

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from database import get_connection, init_db  # noqa: E402

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
        data_desde = st.date_input(
            "Sincronizar desde",
            value=date.today() - timedelta(days=7),
            max_value=date.today(),
        )
        if st.button("🔄 Sincronizar agora"):
            with st.spinner("Conectando ao ERP, baixando e processando dados..."):
                try:
                    import os
                    from dotenv import load_dotenv
                    from download_erp import baixar_vendas_e_orcamentos
                    from process_data import unificar
                    from storage import sincronizar

                    load_dotenv(BASE / ".env")
                    arquivos = baixar_vendas_e_orcamentos(
                        usuario=os.getenv("ECG_USER"),
                        senha=os.getenv("ECG_PASSWORD"),
                        download_dir=BASE / "downloads",
                        data_inicio=data_desde,
                        data_fim=date.today(),
                        headless=True,
                    )
                    df_novo = unificar(arquivos["vendas"], arquivos["orcamentos"])
                    resultado = sincronizar(df_novo)
                    st.success(
                        f"Sincronizado! {resultado['novos']} novo(s), "
                        f"{resultado['atualizados']} atualizado(s)."
                    )
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Falha na sincronização: {e}")

# ---------------------------------------------------------------------------
# Aplica filtros
# ---------------------------------------------------------------------------
df_filtrado = df.copy()
if not df.empty and periodo and len(periodo) == 2:
    inicio, fim = periodo
    df_filtrado = df_filtrado[
        (df_filtrado["data_referencia"].dt.date >= inicio)
        & (df_filtrado["data_referencia"].dt.date <= fim)
    ]
if vendedores_sel:
    df_filtrado = df_filtrado[df_filtrado["vendedor"].isin(vendedores_sel)]
if cidades_sel:
    df_filtrado = df_filtrado[df_filtrado["cidade"].isin(cidades_sel)]
if valor_min_sel is not None:
    df_filtrado = df_filtrado[df_filtrado["valor"] >= valor_min_sel]
if valor_max_sel is not None:
    df_filtrado = df_filtrado[df_filtrado["valor"] <= valor_max_sel]
if situacoes_sel:
    df_filtrado = df_filtrado[df_filtrado["situacao"].isin(situacoes_sel)]

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

aba_tabela, aba_graficos, aba_kpis, aba_metas, aba_log = st.tabs(
    ["Tabela", "Gráficos", "KPIs", "Metas", "Log de sincronização"]
)

with aba_tabela:
    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

with aba_graficos:
    df_vendas = df_filtrado[df_filtrado["tipo"] == "venda"].copy()
    if df_vendas.empty:
        st.info("Sem vendas no filtro selecionado.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Vendas por mês")
            df_vendas["mes"] = df_vendas["data_aprovacao"].dt.to_period("M").astype(str)
            por_mes = df_vendas.groupby("mes")["valor"].sum().sort_index()
            st.bar_chart(por_mes, color="#8B3C05")

        with col2:
            st.subheader("Top vendedores")
            top_vendedores = df_vendas.groupby("vendedor")["valor"].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_vendedores, color="#8B3C05")

        st.subheader("Top cidades")
        top_cidades = df_vendas.groupby("cidade")["valor"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_cidades, color="#8B3C05")

def _badge_situacao(situacao: str) -> str:
    s = (situacao or "").strip().lower()
    if "cancelad" in s:
        classe = "cd-badge-vermelho"
    elif "aprovad" in s or "fechad" in s:
        classe = "cd-badge-verde"
    elif "aguard" in s:
        classe = "cd-badge-amarelo"
    elif "pré" in s or "pre-aprovad" in s or "pre aprovad" in s:
        classe = "cd-badge-amarelo"
    else:
        classe = "cd-badge-neutro"
    return f'<span class="cd-badge {classe}">{situacao}</span>'


def _kpis_periodo(frame: pd.DataFrame) -> dict:
    vendas = frame[frame["tipo"] == "venda"]
    orcamentos = frame[frame["tipo"] == "orcamento"]
    abertos = orcamentos[~orcamentos["situacao"].str.lower().str.contains("cancelad", na=False)]
    total_vendido = vendas["valor"].sum()
    qtd_vendas = len(vendas)
    ticket_medio = total_vendido / qtd_vendas if qtd_vendas else 0
    qtd_orcamentos_abertos = len(abertos)
    base_conversao = qtd_vendas + qtd_orcamentos_abertos
    taxa_conversao = (qtd_vendas / base_conversao * 100) if base_conversao else 0
    return {
        "total_vendido": total_vendido,
        "ticket_medio": ticket_medio,
        "orcamentos_abertos": qtd_orcamentos_abertos,
        "taxa_conversao": taxa_conversao,
    }


def _delta_html(atual: float, anterior: float, sufixo: str = "") -> str:
    if not anterior:
        return ""
    variacao = (atual - anterior) / anterior * 100
    seta = "▲" if variacao >= 0 else "▼"
    classe = "cd-delta-up" if variacao >= 0 else "cd-delta-down"
    return f'<div class="cd-delta {classe}">{seta} {abs(variacao):.1f}{sufixo} vs. período anterior</div>'


with aba_kpis:
    atual = _kpis_periodo(df_filtrado)

    # Periodo imediatamente anterior, de mesma duracao, para comparacao
    anterior_kpis = {}
    if not df.empty and periodo and len(periodo) == 2:
        inicio, fim = periodo
        duracao = (fim - inicio).days + 1
        fim_anterior = inicio - timedelta(days=1)
        inicio_anterior = fim_anterior - timedelta(days=duracao - 1)
        df_periodo_anterior = df[
            (df["data_referencia"].dt.date >= inicio_anterior)
            & (df["data_referencia"].dt.date <= fim_anterior)
        ]
        anterior_kpis = _kpis_periodo(df_periodo_anterior)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Vendas no período", f"R$ {atual['total_vendido']:,.2f}")
        st.markdown(_delta_html(atual["total_vendido"], anterior_kpis.get("total_vendido", 0)), unsafe_allow_html=True)
    with c2:
        st.metric("Ticket médio", f"R$ {atual['ticket_medio']:,.2f}")
        st.markdown(_delta_html(atual["ticket_medio"], anterior_kpis.get("ticket_medio", 0)), unsafe_allow_html=True)
    with c3:
        st.metric("Orçamentos abertos", atual["orcamentos_abertos"])
        st.markdown(_delta_html(atual["orcamentos_abertos"], anterior_kpis.get("orcamentos_abertos", 0)), unsafe_allow_html=True)
    with c4:
        st.metric("Taxa de conversão", f"{atual['taxa_conversao']:.0f}%")
        st.markdown(_delta_html(atual["taxa_conversao"], anterior_kpis.get("taxa_conversao", 0), sufixo=" p.p."), unsafe_allow_html=True)

    st.write("")
    col_graf, col_rank = st.columns([1.3, 1])

    with col_graf:
        df_vendas_kpi = df_filtrado[df_filtrado["tipo"] == "venda"].copy()
        if df_vendas_kpi.empty:
            st.markdown('<div class="cd-card"><h4>Vendas por mês</h4>Sem vendas no filtro selecionado.</div>', unsafe_allow_html=True)
        else:
            df_vendas_kpi["mes"] = df_vendas_kpi["data_aprovacao"].dt.to_period("M")
            por_mes = df_vendas_kpi.groupby("mes")["valor"].sum().sort_index().tail(6)
            maximo = por_mes.max() or 1
            barras = "".join(
                f'<div class="cd-bar-col">'
                f'<div class="cd-bar-value">R$ {valor/1000:,.0f}k</div>'
                f'<div class="cd-bar-shape" style="height:{max(valor/maximo*100, 4):.0f}%"></div>'
                f'<div class="cd-bar-label">{mes.strftime("%b").capitalize()}</div>'
                f'</div>'
                for mes, valor in por_mes.items()
            )
            st.markdown(
                f'<div class="cd-card"><h4>Vendas por mês</h4><div class="cd-bars">{barras}</div></div>',
                unsafe_allow_html=True,
            )

    with col_rank:
        df_vendas_kpi = df_filtrado[df_filtrado["tipo"] == "venda"]
        if df_vendas_kpi.empty:
            st.markdown('<div class="cd-card"><h4>Top vendedores</h4>Sem vendas no filtro selecionado.</div>', unsafe_allow_html=True)
        else:
            top = df_vendas_kpi.groupby("vendedor")["valor"].sum().sort_values(ascending=False).head(4)
            maximo_top = top.max() or 1
            linhas = "".join(
                f'<div class="cd-rank-row">'
                f'<div class="cd-rank-num">{i}</div>'
                f'<div class="cd-rank-name">{nome}</div>'
                f'<div class="cd-rank-bar-bg"><div class="cd-rank-bar-fill" style="width:{valor/maximo_top*100:.0f}%"></div></div>'
                f'<div class="cd-rank-value">R$ {valor/1000:,.0f}k</div>'
                f'</div>'
                for i, (nome, valor) in enumerate(top.items(), start=1)
            )
            st.markdown(
                f'<div class="cd-card"><h4>Top vendedores</h4>{linhas}</div>',
                unsafe_allow_html=True,
            )

    from metas import listar_metas, VENDEDOR_GERAL

    mes_atual = date.today().strftime("%Y-%m")
    metas_df = listar_metas()
    metas_geral_mes = metas_df[
        (metas_df["vendedor"] == VENDEDOR_GERAL) & (metas_df["ano_mes"] == mes_atual)
    ] if not metas_df.empty else pd.DataFrame()

    if metas_geral_mes.empty:
        st.markdown(
            '<div class="cd-card"><h4>Metas do mês — Geral</h4>'
            'Nenhuma meta cadastrada para este mês. Cadastre na aba "Metas".</div>',
            unsafe_allow_html=True,
        )
    else:
        linhas_meta = ""
        for _, linha in metas_geral_mes.iterrows():
            meta_valor = float(linha["valor_meta"])
            if linha["tipo_kpi"] == "valor_vendas":
                realizado = atual["total_vendido"]
                fmt = lambda v: f"R$ {v:,.0f}"
            elif linha["tipo_kpi"] == "ticket_medio":
                realizado = atual["ticket_medio"]
                fmt = lambda v: f"R$ {v:,.0f}"
            else:
                realizado = 0
                fmt = lambda v: f"{v:,.0f}"
            pct = min(realizado / meta_valor * 100, 100) if meta_valor else 0
            linhas_meta += (
                '<div class="cd-progress-row">'
                f'<div class="cd-progress-top"><span class="cd-progress-label">{linha["tipo_kpi"].replace("_", " ")}</span></div>'
                f'<div class="cd-progress-bg"><div class="cd-progress-fill" style="width:{pct:.0f}%"></div></div>'
                f'<div class="cd-progress-text" style="text-align:right">{fmt(realizado)} / {fmt(meta_valor)}</div>'
                '</div>'
            )
        st.markdown(f'<div class="cd-card"><h4>Metas do mês — Geral</h4>{linhas_meta}</div>', unsafe_allow_html=True)

    if df_filtrado.empty:
        st.markdown('<div class="cd-card"><h4>Últimos registros</h4>Sem registros no filtro selecionado.</div>', unsafe_allow_html=True)
    else:
        coluna_ordem = "data_referencia" if "data_referencia" in df_filtrado.columns else df_filtrado.columns[0]
        recentes = df_filtrado.sort_values(coluna_ordem, ascending=False).head(6)
        linhas_tabela = "".join(
            "<tr>"
            f"<td>{r.get('codigo', '')}</td>"
            f"<td>{str(r.get('tipo', '')).capitalize()}</td>"
            f"<td>{r.get('cliente', '')}</td>"
            f"<td>{r.get('vendedor', '')}</td>"
            f"<td>{r.get('cidade', '')}</td>"
            f"<td>R$ {float(r.get('valor') or 0):,.2f}</td>"
            f"<td>{_badge_situacao(r.get('situacao', ''))}</td>"
            "</tr>"
            for _, r in recentes.iterrows()
        )
        st.markdown(
            '<div class="cd-card"><h4>Últimos registros</h4>'
            '<table class="cd-table"><thead><tr>'
            "<th>Código</th><th>Tipo</th><th>Cliente</th><th>Vendedor</th>"
            "<th>Cidade</th><th>Valor</th><th>Situação</th>"
            f"</tr></thead><tbody>{linhas_tabela}</tbody></table></div>",
            unsafe_allow_html=True,
        )

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

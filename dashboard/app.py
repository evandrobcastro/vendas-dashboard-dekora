"""Dashboard de Vendas - Casa Dekora"""
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

st.set_page_config(page_title="Vendas Casa Dekora", layout="wide")


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
    st.title("Vendas Casa Dekora")
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
    else:
        data_min = df["data_cadastro"].min().date()
        data_max = date.today()
        periodo = st.date_input("Período (data cadastro)", value=(data_min, data_max))

        vendedores = sorted(df["vendedor"].dropna().unique())
        cidades = sorted(df["cidade"].dropna().unique())
        situacoes = sorted(df["situacao"].dropna().unique())

        vendedores_sel = st.multiselect("Vendedor", vendedores)
        cidades_sel = st.multiselect("Cidade", cidades)
        situacoes_sel = st.multiselect("Situação", situacoes)

    st.divider()
    with st.expander("Administração"):
        dias = st.number_input("Sincronizar últimos N dias", min_value=1, max_value=365, value=7)
        if st.button("🔄 Sincronizar agora"):
            with st.spinner("Conectando ao ERP, baixando e processando dados..."):
                try:
                    import os
                    from dotenv import load_dotenv
                    from download_erp import baixar_vendas_e_orcamentos
                    from process_data import unificar
                    from storage import sincronizar

                    load_dotenv(BASE / ".env")
                    hoje = date.today()
                    arquivos = baixar_vendas_e_orcamentos(
                        usuario=os.getenv("ECG_USER"),
                        senha=os.getenv("ECG_PASSWORD"),
                        download_dir=BASE / "downloads",
                        data_inicio=hoje - timedelta(days=int(dias)),
                        data_fim=hoje,
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
        (df_filtrado["data_cadastro"].dt.date >= inicio)
        & (df_filtrado["data_cadastro"].dt.date <= fim)
    ]
if vendedores_sel:
    df_filtrado = df_filtrado[df_filtrado["vendedor"].isin(vendedores_sel)]
if cidades_sel:
    df_filtrado = df_filtrado[df_filtrado["cidade"].isin(cidades_sel)]
if situacoes_sel:
    df_filtrado = df_filtrado[df_filtrado["situacao"].isin(situacoes_sel)]

# ---------------------------------------------------------------------------
# Conteudo principal
# ---------------------------------------------------------------------------
st.title("📊 Vendas Casa Dekora")

aba_tabela, aba_graficos, aba_kpis, aba_log = st.tabs(
    ["Tabela", "Gráficos", "KPIs", "Log de sincronização"]
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
            st.bar_chart(por_mes)

        with col2:
            st.subheader("Top vendedores")
            top_vendedores = df_vendas.groupby("vendedor")["valor"].sum().sort_values(ascending=False).head(10)
            st.bar_chart(top_vendedores)

        st.subheader("Top cidades")
        top_cidades = df_vendas.groupby("cidade")["valor"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_cidades)

with aba_kpis:
    df_vendas = df_filtrado[df_filtrado["tipo"] == "venda"]
    total_vendido = df_vendas["valor"].sum()
    qtd_vendas = len(df_vendas)
    ticket_medio = total_vendido / qtd_vendas if qtd_vendas else 0
    total_geral = len(df_filtrado)
    taxa_aprovacao = (qtd_vendas / total_geral * 100) if total_geral else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total vendido", f"R$ {total_vendido:,.2f}")
    c2.metric("Ticket médio", f"R$ {ticket_medio:,.2f}")
    c3.metric("Qtd. vendas", qtd_vendas)
    c4.metric("Taxa de aprovação", f"{taxa_aprovacao:.1f}%")

with aba_log:
    log = carregar_sync_log()
    st.dataframe(log, use_container_width=True, hide_index=True)

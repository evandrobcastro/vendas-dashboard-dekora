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
        periodo = st.date_input(
            "Período (cadastro p/ orçamentos, aprovação p/ vendas)",
            value=(data_min, data_max),
        )

        vendedores = sorted(df["vendedor"].dropna().unique())
        cidades = sorted(df["cidade"].dropna().unique())
        situacoes = sorted(df["situacao"].dropna().unique())

        vendedores_sel = st.multiselect("Vendedor", vendedores)
        cidades_sel = st.multiselect("Cidade", cidades)
        situacoes_sel = st.multiselect("Situação", situacoes)

        valor_min_dados = float(df["valor"].min())
        valor_max_dados = float(df["valor"].max())
        st.caption("Faixa de valor do pedido (R$)")
        col_de, col_ate = st.columns(2)
        with col_de:
            valor_min_sel = st.number_input("De:", min_value=valor_min_dados, max_value=valor_max_dados, value=valor_min_dados, step=100.0)
        with col_ate:
            valor_max_sel = st.number_input("Até:", min_value=valor_min_dados, max_value=valor_max_dados, value=valor_max_dados, step=100.0)

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
    df_filtrado = df_filtrado[
        (df_filtrado["valor"] >= valor_min_sel) & (df_filtrado["valor"] <= valor_max_sel)
    ]
if situacoes_sel:
    df_filtrado = df_filtrado[df_filtrado["situacao"].isin(situacoes_sel)]

# ---------------------------------------------------------------------------
# Conteudo principal
# ---------------------------------------------------------------------------
st.title("📊 Vendas Casa Dekora")

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

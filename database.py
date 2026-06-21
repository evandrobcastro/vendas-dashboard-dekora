"""
Schema e helpers de acesso ao banco.

Fonte de verdade: Postgres no Supabase (DATABASE_URL via .env), compartilhado
entre o pipeline local (PC roda Selenium + grava dados) e o dashboard
hospedado na web (le os mesmos dados). Ver Sprint 6.
"""
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def _config(chave: str, padrao: str | None = None) -> str | None:
    """Le configuracao do .env (PC local) ou de st.secrets (Streamlit Cloud)."""
    valor = os.getenv(chave)
    if valor:
        return valor
    try:
        import streamlit as st
        return st.secrets.get(chave, padrao)
    except Exception:
        return padrao

SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    codigo TEXT PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('venda', 'orcamento')),
    cliente TEXT,
    identificacao TEXT,
    situacao TEXT,
    valor REAL,
    vendedor TEXT,
    desconto REAL,
    data_cadastro TEXT,
    data_aprovacao TEXT,
    dias_aprovacao INTEGER,
    metragem REAL,
    cidade TEXT,
    email TEXT,
    valor_sem_desc REAL,
    segmento TEXT,
    comissionado TEXT,
    forma_divulgacao TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_log (
    id SERIAL PRIMARY KEY,
    executado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    linhas_novas INTEGER DEFAULT 0,
    linhas_atualizadas INTEGER DEFAULT 0,
    linhas_removidas INTEGER DEFAULT 0,
    status TEXT,
    mensagem TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    nome TEXT
);

-- Metas (gerais ou individuais) por KPI e mes. vendedor = 'GERAL' para
-- metas da empresa como um todo. tipo_kpi e livre (ex: valor_vendas,
-- ticket_medio, qtd_vendas, taxa_aprovacao) para suportar metas alem de
-- valor de vendas. UNIQUE(tipo_kpi, vendedor, ano_mes) garante que inserir
-- a meta de novo so atualiza (replanejamento), nunca duplica.
CREATE TABLE IF NOT EXISTS metas (
    id SERIAL PRIMARY KEY,
    tipo_kpi TEXT NOT NULL,
    vendedor TEXT NOT NULL DEFAULT 'GERAL',
    ano_mes TEXT NOT NULL,
    valor_meta REAL NOT NULL,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tipo_kpi, vendedor, ano_mes)
);
"""


def get_connection():
    return psycopg2.connect(
        host=_config("DB_HOST"),
        port=_config("DB_PORT", "5432"),
        dbname=_config("DB_NAME", "postgres"),
        user=_config("DB_USER", "postgres"),
        password=_config("DB_PASSWORD"),
        sslmode="require",
    )


def init_db() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Banco Postgres (Supabase) inicializado. Host: {_config('DB_HOST')}")

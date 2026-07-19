"""
Skill: grava as OS de reposicao/manutencao no Postgres.

Estrategia: substituicao por mes (apaga os meses coletados e reinsere) —
OS que sumiram do relatorio (ex.: canceladas) nao ficam orfas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import get_connection  # noqa: E402

DDL_REPOSICOES = """
CREATE TABLE IF NOT EXISTS reposicoes (
    id SERIAL PRIMARY KEY,
    os TEXT NOT NULL,
    ano_mes TEXT NOT NULL,
    categoria TEXT,
    tipo TEXT,
    identificacao TEXT,
    cliente TEXT,
    cidade TEXT,
    bairro TEXT,
    data_cadastro TEXT,
    causadores TEXT,
    motivos TEXT,
    metragem REAL DEFAULT 0,
    custo REAL DEFAULT 0,
    horas REAL DEFAULT 0,
    status TEXT,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (os, ano_mes)
);
ALTER TABLE reposicoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE reposicoes ADD COLUMN IF NOT EXISTS categoria TEXT;
ALTER TABLE reposicoes ADD COLUMN IF NOT EXISTS responsavel TEXT;
"""


def init_reposicoes() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL_REPOSICOES)
        conn.commit()
    finally:
        conn.close()


def sincronizar_reposicoes(linhas: list[dict], meses: list[str]) -> dict:
    init_reposicoes()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reposicoes WHERE ano_mes = ANY(%s)", (meses,))
            for l in linhas:
                cur.execute(
                    """
                    INSERT INTO reposicoes (os, ano_mes, categoria, responsavel, tipo,
                        identificacao, cliente, cidade, bairro, data_cadastro,
                        causadores, motivos, metragem, custo, horas, status,
                        atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (os, ano_mes) DO UPDATE SET
                        categoria = excluded.categoria, responsavel = excluded.responsavel,
                        tipo = excluded.tipo, identificacao = excluded.identificacao,
                        cliente = excluded.cliente, cidade = excluded.cidade,
                        bairro = excluded.bairro, data_cadastro = excluded.data_cadastro,
                        causadores = excluded.causadores, motivos = excluded.motivos,
                        metragem = excluded.metragem, custo = excluded.custo,
                        horas = excluded.horas, status = excluded.status,
                        atualizado_em = CURRENT_TIMESTAMP
                    """,
                    (l["os"], l["ano_mes"], l.get("categoria"), l.get("responsavel"),
                     l["tipo"], l["identificacao"], l["cliente"], l["cidade"],
                     l["bairro"], l["data_cadastro"], l["causadores"], l["motivos"],
                     l["metragem"], l["custo"], l["horas"], l["status"]),
                )
        conn.commit()
    finally:
        conn.close()
    return {"meses_reposicoes": len(meses), "linhas_reposicoes": len(linhas)}

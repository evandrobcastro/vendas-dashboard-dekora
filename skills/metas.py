"""
Skill: gerenciamento de metas (gerais ou individuais) por KPI e mes.

Estrategia: UPSERT por (tipo_kpi, vendedor, ano_mes). Inserir a mesma
combinacao de novo apenas atualiza o valor (replanejamento). Vendedor novo
= apenas uma linha nova, sem precisar alterar estrutura.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import get_connection, init_db  # noqa: E402

VENDEDOR_GERAL = "GERAL"

TIPOS_KPI_SUGERIDOS = [
    "valor_vendas",
    "ticket_medio",
    "qtd_vendas",
    "taxa_aprovacao",
]


def upsert_meta(tipo_kpi: str, vendedor: str, ano_mes: str, valor_meta: float) -> None:
    """Insere ou atualiza uma unica meta.

    vendedor: nome do vendedor, ou VENDEDOR_GERAL para meta da empresa.
    ano_mes: formato 'YYYY-MM'.
    """
    init_db()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO metas (tipo_kpi, vendedor, ano_mes, valor_meta, criado_em, atualizado_em)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (tipo_kpi, vendedor, ano_mes)
        DO UPDATE SET valor_meta = excluded.valor_meta, atualizado_em = CURRENT_TIMESTAMP
        """,
        (tipo_kpi.strip(), vendedor.strip() or VENDEDOR_GERAL, ano_mes.strip(), valor_meta),
    )
    conn.commit()
    conn.close()


def upsert_lote(df: pd.DataFrame) -> dict:
    """Recebe um DataFrame com colunas tipo_kpi, vendedor, ano_mes, valor_meta
    e faz upsert linha a linha. Retorna contagem de sucesso/erro."""
    sucesso = 0
    erros = []
    for idx, row in df.iterrows():
        try:
            tipo_kpi = str(row["tipo_kpi"]).strip()
            vendedor = str(row["vendedor"]).strip() or VENDEDOR_GERAL
            ano_mes = str(row["ano_mes"]).strip()
            valor_meta = float(row["valor_meta"])
            if not tipo_kpi or not ano_mes:
                raise ValueError("tipo_kpi e ano_mes sao obrigatorios")
            upsert_meta(tipo_kpi, vendedor, ano_mes, valor_meta)
            sucesso += 1
        except Exception as e:
            erros.append(f"Linha {idx + 1}: {e}")
    return {"sucesso": sucesso, "erros": erros}


def listar_metas() -> pd.DataFrame:
    init_db()
    conn = get_connection()
    df = pd.read_sql(
        "SELECT tipo_kpi, vendedor, ano_mes, valor_meta, atualizado_em "
        "FROM metas ORDER BY ano_mes DESC, vendedor, tipo_kpi",
        conn,
    )
    conn.close()
    return df


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(listar_metas().to_string())

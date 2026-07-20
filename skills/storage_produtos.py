"""
Skill: grava as linhas de produtos (classe/subclasse por mes) no Postgres.

Estrategia: substituicao por mes — apaga os meses coletados e insere as
linhas novas na mesma transacao. Assim subclasses que sumiram do relatorio
(ex.: pedido cancelado) nao ficam orfas no banco.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import get_connection  # noqa: E402

DDL_PRODUTOS = """
CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    ano_mes TEXT NOT NULL,
    classe TEXT NOT NULL,
    subclasse TEXT NOT NULL,
    quantidade DOUBLE PRECISION DEFAULT 0,
    m2_vidro DOUBLE PRECISION DEFAULT 0,
    m2_inst DOUBLE PRECISION DEFAULT 0,
    peso_perfil DOUBLE PRECISION DEFAULT 0,
    valor_venda DOUBLE PRECISION DEFAULT 0,
    valor_custo DOUBLE PRECISION DEFAULT 0,
    lucro DOUBLE PRECISION DEFAULT 0,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ano_mes, classe, subclasse)
);
ALTER TABLE produtos ENABLE ROW LEVEL SECURITY;
"""


def init_produtos() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL_PRODUTOS)
        conn.commit()
    finally:
        conn.close()


def sincronizar_produtos(linhas: list[dict], meses: list[str]) -> dict:
    """Substitui os meses informados pelas linhas coletadas."""
    init_produtos()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM produtos WHERE ano_mes = ANY(%s)", (meses,))
            for l in linhas:
                cur.execute(
                    """
                    INSERT INTO produtos (ano_mes, classe, subclasse, quantidade,
                                          m2_vidro, m2_inst, peso_perfil,
                                          valor_venda, valor_custo, lucro,
                                          atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (ano_mes, classe, subclasse) DO UPDATE SET
                        quantidade = excluded.quantidade,
                        m2_vidro = excluded.m2_vidro,
                        m2_inst = excluded.m2_inst,
                        peso_perfil = excluded.peso_perfil,
                        valor_venda = excluded.valor_venda,
                        valor_custo = excluded.valor_custo,
                        lucro = excluded.lucro,
                        atualizado_em = CURRENT_TIMESTAMP
                    """,
                    (l["ano_mes"], l["classe"], l["subclasse"],
                     l.get("quantidade", 0), l.get("m2_vidro", 0),
                     l.get("m2_inst", 0), l.get("peso_perfil", 0),
                     l.get("valor_venda", 0), l.get("valor_custo", 0),
                     l.get("lucro", 0)),
                )
        conn.commit()
    finally:
        conn.close()
    return {"meses_produtos": len(meses), "linhas_produtos": len(linhas)}

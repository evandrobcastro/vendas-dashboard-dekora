"""
Skill: grava as linhas do DRE (classe financeira por mes/loja) no Postgres.

Estrategia: substituicao por (loja x meses coletados) na mesma transacao —
classes que zeraram no ECG somem do banco em vez de ficarem orfas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import get_connection  # noqa: E402

DDL_FINANCEIRO = """
CREATE TABLE IF NOT EXISTS financeiro (
    id SERIAL PRIMARY KEY,
    ano_mes TEXT NOT NULL,
    loja TEXT NOT NULL,
    grupo TEXT NOT NULL,
    classe TEXT NOT NULL,
    valor REAL DEFAULT 0,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ano_mes, loja, grupo, classe)
);
ALTER TABLE financeiro ENABLE ROW LEVEL SECURITY;
CREATE TABLE IF NOT EXISTS financeiro_previsto (
    id SERIAL PRIMARY KEY,
    ano_mes TEXT NOT NULL,
    loja TEXT NOT NULL,
    grupo TEXT NOT NULL,
    classe TEXT NOT NULL,
    valor REAL DEFAULT 0,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ano_mes, loja, grupo, classe)
);
ALTER TABLE financeiro_previsto ENABLE ROW LEVEL SECURITY;
"""


def init_financeiro() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL_FINANCEIRO)
        conn.commit()
    finally:
        conn.close()


def sincronizar_financeiro(linhas: list[dict], meses: list[str],
                           lojas: list[str]) -> dict:
    """Substitui os meses/lojas informados pelas linhas coletadas."""
    init_financeiro()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM financeiro WHERE ano_mes = ANY(%s) AND loja = ANY(%s)",
                (meses, lojas),
            )
            for l in linhas:
                cur.execute(
                    """
                    INSERT INTO financeiro (ano_mes, loja, grupo, classe, valor, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (ano_mes, loja, grupo, classe) DO UPDATE SET
                        valor = excluded.valor, atualizado_em = CURRENT_TIMESTAMP
                    """,
                    (l["ano_mes"], l["loja"], l["grupo"], l["classe"], l["valor"]),
                )
        conn.commit()
    finally:
        conn.close()
    return {"meses_financeiro": len(meses), "linhas_financeiro": len(linhas)}


def sincronizar_previsto(linhas: list[dict]) -> dict:
    """Substitui TODA a previsao futura pelos lancamentos recem-coletados —
    a previsao muda a cada pagamento/recebimento, entao e sempre renovada."""
    init_financeiro()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM financeiro_previsto")
            for l in linhas:
                cur.execute(
                    """
                    INSERT INTO financeiro_previsto (ano_mes, loja, grupo, classe, valor, atualizado_em)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (ano_mes, loja, grupo, classe) DO UPDATE SET
                        valor = excluded.valor, atualizado_em = CURRENT_TIMESTAMP
                    """,
                    (l["ano_mes"], l["loja"], l["grupo"], l["classe"], l["valor"]),
                )
        conn.commit()
    finally:
        conn.close()
    return {"linhas_previsto": len(linhas)}

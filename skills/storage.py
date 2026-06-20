"""
Skill: grava o DataFrame unificado (vendas + orcamentos) no Postgres (Supabase).

Estrategia: UPSERT por 'codigo'.
  - Codigo novo            -> INSERT
  - Codigo existente        -> UPDATE somente se algum campo mudou
                               (cobre o caso de cancelamento: a situacao
                               muda para 'cancelado', o registro permanece
                               no banco para preservar historico)
  - Nunca faz DELETE.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import get_connection, init_db  # noqa: E402

CAMPOS = [
    "codigo", "tipo", "cliente", "identificacao", "situacao", "valor",
    "vendedor", "desconto", "data_cadastro", "data_aprovacao",
    "dias_aprovacao", "metragem", "cidade", "email", "valor_sem_desc",
    "segmento", "comissionado", "forma_divulgacao",
]


def _linha_para_tupla(row: pd.Series) -> tuple:
    valores = []
    for campo in CAMPOS:
        v = row[campo]
        if pd.isna(v):
            v = None
        elif hasattr(v, "item"):  # numpy/pandas scalar -> tipo nativo
            v = v.item()
        valores.append(v)
    return tuple(valores)


def sincronizar(df: pd.DataFrame) -> dict:
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT {', '.join(CAMPOS)} FROM registros")
    existentes = {row[0]: row for row in cur.fetchall()}

    novos = 0
    atualizados = 0

    for _, row in df.iterrows():
        tupla = _linha_para_tupla(row)
        codigo = tupla[0]

        if codigo not in existentes:
            placeholders = ", ".join(["%s"] * len(CAMPOS))
            cur.execute(
                f"INSERT INTO registros ({', '.join(CAMPOS)}, criado_em, atualizado_em) "
                f"VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                tupla,
            )
            novos += 1
        elif tupla != existentes[codigo]:
            set_clause = ", ".join(f"{c} = %s" for c in CAMPOS[1:])
            cur.execute(
                f"UPDATE registros SET {set_clause}, atualizado_em = CURRENT_TIMESTAMP "
                f"WHERE codigo = %s",
                tupla[1:] + (codigo,),
            )
            atualizados += 1

    cur.execute(
        "INSERT INTO sync_log (linhas_novas, linhas_atualizadas, linhas_removidas, status, mensagem) "
        "VALUES (%s, %s, 0, 'sucesso', %s)",
        (novos, atualizados, f"{len(df)} linhas processadas"),
    )

    conn.commit()
    conn.close()

    return {"novos": novos, "atualizados": atualizados, "total_processado": len(df)}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(Path(__file__).parent))
    from process_data import unificar

    downloads = Path(__file__).parent.parent / "downloads"
    vendas_files = sorted(downloads.glob("vendas_*.xlsx"), reverse=True)
    orcamentos_files = sorted(downloads.glob("orcamentos_*.xlsx"), reverse=True)

    if not vendas_files or not orcamentos_files:
        print("Nenhum arquivo encontrado em downloads/. Rode skills/download_erp.py primeiro.")
        sys.exit(1)

    df = unificar(vendas_files[0], orcamentos_files[0])
    resultado = sincronizar(df)
    print(f"Sincronizacao concluida: {resultado}")

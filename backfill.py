"""
Backfill: roda o pipeline completo (download -> processamento -> storage)
para um intervalo de datas especifico, sem disparar e-mail de notificacao.

Uso:
  python backfill.py 2023-01-01 2023-12-31
"""
import sys
from datetime import date, datetime
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from dotenv import load_dotenv  # noqa: E402
import os  # noqa: E402

from download_erp import baixar_vendas_e_orcamentos  # noqa: E402
from process_data import unificar  # noqa: E402
from storage import sincronizar  # noqa: E402


def rodar(data_inicio: date, data_fim: date) -> dict:
    load_dotenv(BASE / ".env")
    print(f"\n=== Backfill {data_inicio} a {data_fim} ===")

    arquivos = baixar_vendas_e_orcamentos(
        usuario=os.getenv("ECG_USER"),
        senha=os.getenv("ECG_PASSWORD"),
        download_dir=BASE / "downloads",
        data_inicio=data_inicio,
        data_fim=data_fim,
        headless=True,
    )
    print(f"Download concluido: {arquivos}")

    df = unificar(arquivos["vendas"], arquivos["orcamentos"])
    print(f"Processamento concluido: {len(df)} linhas")

    resultado = sincronizar(df)
    print(f"Storage concluido: {resultado}")
    return resultado


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3:
        print("Uso: python backfill.py YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)
    inicio = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    fim = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    rodar(inicio, fim)

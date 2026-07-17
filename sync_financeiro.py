"""
Sincroniza a tabela financeiro (DRE conf. pagamentos, regime de caixa) para
um ano inteiro, nas duas lojas (CASA DEKORA e LACA 108).

Uso:
  python sync_financeiro.py            # ano corrente
  python sync_financeiro.py 2025       # ano especifico
"""
import os
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from dotenv import load_dotenv  # noqa: E402

from financeiro_erp import coletar_dre_lojas, LOJAS  # noqa: E402
from storage_financeiro import sincronizar_financeiro  # noqa: E402


def rodar_financeiro(ano: int, headless: bool = True) -> dict:
    load_dotenv(BASE / ".env")
    print(f"=== Financeiro (DRE): coletando {ano} nas lojas {', '.join(LOJAS)} ===")
    linhas = coletar_dre_lojas(
        os.getenv("ECG_USER"), os.getenv("ECG_PASSWORD"),
        ano, 1, ano, 12, headless=headless,
    )
    meses = [f"{ano}-{m:02d}" for m in range(1, 13)]
    resultado = sincronizar_financeiro(linhas, meses, list(LOJAS))
    print(f"Storage concluido: {resultado}")
    return resultado


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ano = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
    rodar_financeiro(ano)

"""
Sincroniza a tabela reposicoes (Relatorio de Reposicoes e Manutencoes do ECG)
para um intervalo de meses, substituindo cada mes coletado.

Uso:
  python sync_reposicoes.py 2023-01 2026-12   # de jan/2023 a dez/2026
  python sync_reposicoes.py 2026-07           # apenas julho/2026
"""
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from dotenv import load_dotenv  # noqa: E402

from reposicoes_erp import coletar_meses  # noqa: E402
from storage_reposicoes import sincronizar_reposicoes  # noqa: E402


def meses_entre(inicio: str, fim: str) -> list[str]:
    ano, mes = int(inicio[:4]), int(inicio[5:7])
    ano_f, mes_f = int(fim[:4]), int(fim[5:7])
    meses = []
    while (ano, mes) <= (ano_f, mes_f):
        meses.append(f"{ano}-{mes:02d}")
        mes += 1
        if mes > 12:
            mes, ano = 1, ano + 1
    return meses


def rodar_reposicoes(meses: list[str], headless: bool = True) -> dict:
    load_dotenv(BASE / ".env")
    print(f"=== Reposicoes: coletando {len(meses)} mes(es) ===")
    linhas = coletar_meses(
        os.getenv("ECG_USER"), os.getenv("ECG_PASSWORD"), meses, headless=headless
    )
    resultado = sincronizar_reposicoes(linhas, meses)
    print(f"Storage concluido: {resultado}")
    return resultado


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) not in (2, 3):
        print("Uso: python sync_reposicoes.py YYYY-MM [YYYY-MM]")
        sys.exit(1)
    inicio = sys.argv[1]
    fim = sys.argv[2] if len(sys.argv) == 3 else inicio
    rodar_reposicoes(meses_entre(inicio, fim))

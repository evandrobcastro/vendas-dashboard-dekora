"""
Exporta para CSV as tabelas que SO existem no Supabase (nao vem do ECG):
metas e usuarios. Gera backup_metas.csv e backup_usuarios.csv na pasta do
projeto (ignorados pelo Git — guarde a copia onde preferir).

Uso:  venv\\Scripts\\python backup_local.py
"""
import csv
import sys
from pathlib import Path

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE / ".env")
from database import get_connection  # noqa: E402

TABELAS = ("metas", "usuarios")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    conn = get_connection()
    try:
        cur = conn.cursor()
        for tabela in TABELAS:
            cur.execute(f"SELECT * FROM {tabela}")
            colunas = [d[0] for d in cur.description]
            destino = BASE / f"backup_{tabela}.csv"
            with open(destino, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(colunas)
                w.writerows(cur.fetchall())
            print(f"{destino.name}: {cur.rowcount} linhas")
    finally:
        conn.close()
    print("Backup local concluido.")

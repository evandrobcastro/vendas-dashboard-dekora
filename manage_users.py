"""Utilitario de linha de comando para cadastrar/atualizar usuarios do dashboard."""
import sys
from pathlib import Path

import bcrypt

sys.path.insert(0, str(Path(__file__).parent))
from database import get_connection, init_db


def adicionar_usuario(email: str, senha: str, nome: str) -> None:
    init_db()
    senha_hash = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO usuarios (email, senha_hash, nome) VALUES (%s, %s, %s) "
        "ON CONFLICT(email) DO UPDATE SET senha_hash = excluded.senha_hash, nome = excluded.nome",
        (email.lower().strip(), senha_hash, nome),
    )
    conn.commit()
    conn.close()
    print(f"Usuario '{email}' cadastrado/atualizado com sucesso.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python manage_users.py <email> <senha> <nome>")
        sys.exit(1)
    adicionar_usuario(sys.argv[1], sys.argv[2], sys.argv[3])

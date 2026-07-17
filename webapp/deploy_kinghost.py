"""
Publica o webapp em dashboard.casadekora.com.br via FTP (KingHost).

Le FTP_HOST/FTP_USER/FTP_PASSWORD do .env (nunca imprime a senha).
Sobe index.html, styles.css, app.js, assets/ e vendor/ para /www/dashboard.

Uso:  python webapp/deploy_kinghost.py
"""
import os
import sys
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path

BASE = Path(__file__).parent          # .../webapp
RAIZ = BASE.parent                    # .../vendas-dashboard

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

DESTINO = "/www/dashboard"
ARQUIVOS = [
    "index.html",
    "styles.css",
    "app.js",
    "assets/logo_negativo.png",
    "vendor/echarts.min.js",
]


def conectar():
    host = os.environ["FTP_HOST"]
    user = os.environ["FTP_USER"]
    senha = os.environ["FTP_PASSWORD"]
    if not senha:
        sys.exit("FTP_PASSWORD vazio no .env — preencha antes de publicar.")
    try:  # prefere conexao cifrada (FTPS)
        ftp = FTP_TLS(host, timeout=30)
        ftp.login(user, senha)
        ftp.prot_p()
        print("Conectado via FTPS (cifrado).")
    except Exception:
        ftp = FTP(host, timeout=30)
        ftp.login(user, senha)
        print("Conectado via FTP.")
    return ftp


def garantir_dir(ftp, caminho):
    try:
        ftp.mkd(caminho)
    except error_perm:
        pass  # ja existe


def main():
    ftp = conectar()
    garantir_dir(ftp, DESTINO)
    garantir_dir(ftp, f"{DESTINO}/assets")
    garantir_dir(ftp, f"{DESTINO}/vendor")
    for rel in ARQUIVOS:
        local = BASE / rel
        remoto = f"{DESTINO}/{rel}"
        with open(local, "rb") as f:
            ftp.storbinary(f"STOR {remoto}", f)
        print(f"enviado: {rel} ({local.stat().st_size / 1024:.0f} KB)")
    print("Conteudo remoto de", DESTINO, ":")
    ftp.cwd(DESTINO)
    ftp.retrlines("NLST")
    ftp.quit()
    print("Publicado com sucesso.")


if __name__ == "__main__":
    main()

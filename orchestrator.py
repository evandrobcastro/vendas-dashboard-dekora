"""
Orquestrador: coordena download -> processamento -> storage -> notificacao.

Pode ser chamado manualmente (botao do dashboard, linha de comando) ou
pelo agendador (scheduler.py, toda sexta as 7:59).
"""
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "skills"))

from download_erp import baixar_vendas_e_orcamentos  # noqa: E402
from process_data import unificar, ValidacaoError  # noqa: E402
from storage import sincronizar  # noqa: E402
from email_notifier import enviar_resumo  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE / "logs" / "orchestrator.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("orchestrator")


def executar(dias: int = 7, headless: bool = True, notificar: bool = True) -> dict:
    load_dotenv(BASE / ".env")
    resultado = None
    erro = None

    try:
        log.info("Iniciando sincronizacao (ultimos %s dias)", dias)
        hoje = date.today()
        arquivos = baixar_vendas_e_orcamentos(
            usuario=os.getenv("ECG_USER"),
            senha=os.getenv("ECG_PASSWORD"),
            download_dir=BASE / "downloads",
            data_inicio=hoje - timedelta(days=dias),
            data_fim=hoje,
            headless=headless,
        )
        log.info("Download concluido: %s", arquivos)

        df = unificar(arquivos["vendas"], arquivos["orcamentos"])
        log.info("Processamento concluido: %s linhas", len(df))

        resultado = sincronizar(df)
        log.info("Storage concluido: %s", resultado)

    except (ValidacaoError, Exception) as e:
        erro = str(e)
        log.exception("Falha na sincronizacao")

    if notificar:
        try:
            enviar_resumo(
                smtp_host=os.getenv("EMAIL_SMTP_HOST"),
                smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
                remetente=os.getenv("EMAIL_FROM"),
                senha=os.getenv("EMAIL_FROM_PASSWORD"),
                destinatarios=[e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()],
                resultado=resultado or {},
                erro=erro,
            )
            log.info("E-mail de notificacao enviado")
        except Exception:
            log.exception("Falha ao enviar e-mail de notificacao")

    if erro:
        raise RuntimeError(erro)
    return resultado


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dias", type=int, default=7)
    parser.add_argument("--sem-email", action="store_true")
    parser.add_argument("--visivel", action="store_true", help="abre o Chrome visivel (nao headless)")
    args = parser.parse_args()

    executar(dias=args.dias, headless=not args.visivel, notificar=not args.sem_email)

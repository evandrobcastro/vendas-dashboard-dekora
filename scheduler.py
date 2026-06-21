"""
Agendador: roda 3 rotinas automaticas.
  1. Toda sexta-feira as 7:59 -> sincronizacao incremental (ultimos 7 dias)
  2. Todo dia 1 de cada mes as 8:30 -> resincronizacao completa do ano
     corrente (01/jan at hoje), para corrigir mudancas perdidas (ex:
     cancelamentos de orcamentos antigos, ver LEIA-ME.md)
  3. Todo 1 de fevereiro as 8:30 -> resincronizacao completa do ano
     anterior (que ja foi "fechado"), garantindo que o ultimo mes dele
     ficou consistente antes de considera-lo definitivamente encerrado

Mantenha este processo rodando continuamente no PC (ver instrucoes no
README/Sprint 6 sobre como deixa-lo iniciando junto com o Windows).
Sincronizacao manual continua disponivel pelo botao no dashboard ou via:
  python orchestrator.py
"""
import logging
import os
import sys
from datetime import date
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from orchestrator import executar  # noqa: E402
from backfill import rodar as rodar_backfill  # noqa: E402
from skills.email_notifier import enviar_resumo  # noqa: E402

log = logging.getLogger("scheduler")
log.setLevel(logging.INFO)
log.propagate = False  # nao usa handlers do root (orchestrator.py ja configura os dele)

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_file_handler = logging.FileHandler(BASE / "logs" / "scheduler.log", encoding="utf-8")
_file_handler.setFormatter(_formatter)
log.addHandler(_file_handler)

if sys.stderr is not None:
    # sys.stderr eh None quando rodando via pythonw.exe (sem console), o
    # que faria o StreamHandler dar erro. So adiciona se houver console.
    _stream_handler = logging.StreamHandler()
    _stream_handler.setFormatter(_formatter)
    log.addHandler(_stream_handler)


def _notificar(resultado: dict | None, erro: str | None) -> None:
    try:
        load_dotenv(BASE / ".env")
        enviar_resumo(
            smtp_host=os.getenv("EMAIL_SMTP_HOST"),
            smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
            remetente=os.getenv("EMAIL_FROM"),
            senha=os.getenv("EMAIL_FROM_PASSWORD"),
            destinatarios=[e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()],
            resultado=resultado or {},
            erro=erro,
        )
    except Exception:
        log.exception("Falha ao enviar e-mail de notificacao")


def job_semanal():
    log.info("Disparando sincronizacao semanal agendada (sexta 7:59)")
    try:
        executar(dias=7, headless=True, notificar=True)
    except Exception:
        log.exception("Sincronizacao semanal agendada falhou")


def job_mensal_ano_corrente():
    hoje = date.today()
    log.info("Disparando resincronizacao mensal do ano corrente (01/%s a %s)", hoje.year, hoje)
    resultado, erro = None, None
    try:
        resultado = rodar_backfill(date(hoje.year, 1, 1), hoje)
    except Exception as e:
        erro = str(e)
        log.exception("Resincronizacao mensal falhou")
    _notificar(resultado, erro)


def job_fechamento_ano_anterior():
    hoje = date.today()
    ano_anterior = hoje.year - 1
    log.info("Disparando resincronizacao de fechamento do ano %s", ano_anterior)
    resultado, erro = None, None
    try:
        resultado = rodar_backfill(date(ano_anterior, 1, 1), date(ano_anterior, 12, 31))
    except Exception as e:
        erro = str(e)
        log.exception("Resincronizacao de fechamento de ano falhou")
    _notificar(resultado, erro)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job_semanal, CronTrigger(day_of_week="fri", hour=7, minute=59))
    scheduler.add_job(job_mensal_ano_corrente, CronTrigger(day=1, hour=8, minute=30))
    scheduler.add_job(job_fechamento_ano_anterior, CronTrigger(month=2, day=1, hour=8, minute=30))
    log.info(
        "Agendador iniciado. Rotinas: sexta 07:59 (semanal), dia 1 de cada mes 08:30 "
        "(ano corrente), 1/fev 08:30 (fechamento ano anterior). Timezone America/Sao_Paulo."
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Agendador interrompido.")

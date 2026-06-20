"""
Agendador: roda a sincronizacao automaticamente toda sexta-feira as 7:59.

Mantenha este processo rodando continuamente no PC (ver instrucoes no
README/Sprint 6 sobre como deixa-lo iniciando junto com o Windows).
Sincronizacao manual continua disponivel pelo botao no dashboard ou via:
  python orchestrator.py
"""
import logging
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from orchestrator import executar  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(BASE / "logs" / "scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("scheduler")


def job():
    log.info("Disparando sincronizacao agendada (sexta 7:59)")
    try:
        executar(dias=7, headless=True, notificar=True)
    except Exception:
        log.exception("Sincronizacao agendada falhou")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job, CronTrigger(day_of_week="fri", hour=7, minute=59))
    log.info("Agendador iniciado. Proxima execucao: toda sexta-feira as 07:59 (America/Sao_Paulo).")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Agendador interrompido.")

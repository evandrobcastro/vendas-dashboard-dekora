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
import threading
from datetime import date
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from orchestrator import executar  # noqa: E402
from backfill import rodar as rodar_backfill  # noqa: E402
from skills.email_notifier import enviar_resumo  # noqa: E402
from database import (  # noqa: E402
    init_db,
    proximo_pedido_pendente,
    atualizar_pedido_sync,
)

# Trava unica para TODA sincronizacao (automatica ou manual): garante que nunca
# rodam dois downloads do ERP ao mesmo tempo (dois Chrome competindo pela mesma
# sessao/pasta de download dariam erro). As rotinas agendadas esperam a vez; a
# verificacao da fila manual desiste e tenta de novo na proxima rodada.
_sync_lock = threading.Lock()

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
    with _sync_lock:  # espera a vez se houver sync manual em andamento
        try:
            executar(dias=7, headless=True, notificar=True)
        except Exception:
            log.exception("Sincronizacao semanal agendada falhou")


def job_processar_pedidos():
    """Verifica a fila de pedidos manuais (vindos do dashboard na nuvem) e
    executa a sincronizacao no PC. Isolado: qualquer falha so marca o pedido
    como 'falhou' e nunca derruba o scheduler nem as rotinas automaticas."""
    try:
        pedido = proximo_pedido_pendente()
    except Exception:
        log.exception("Falha ao consultar a fila de pedidos de sync")
        return
    if not pedido:
        return

    # Nao bloqueia: se uma sync (automatica ou outra manual) esta rodando,
    # deixa o pedido na fila e tenta de novo na proxima verificacao.
    if not _sync_lock.acquire(blocking=False):
        log.info("Sync em andamento; pedido %s aguarda proxima verificacao", pedido["id"])
        return
    try:
        log.info("Processando pedido de sync manual %s (dias=%s)", pedido["id"], pedido["dias"])
        atualizar_pedido_sync(pedido["id"], "processando", "Rodando no PC...")
        try:
            resultado = executar(dias=pedido["dias"], headless=True, notificar=False)
            msg = f"{resultado.get('novos', 0)} novo(s), {resultado.get('atualizados', 0)} atualizado(s)"
            atualizar_pedido_sync(pedido["id"], "concluido", msg)
            log.info("Pedido %s concluido: %s", pedido["id"], msg)
        except Exception as e:
            atualizar_pedido_sync(pedido["id"], "falhou", str(e))
            log.exception("Pedido de sync manual %s falhou", pedido["id"])
    finally:
        _sync_lock.release()


def job_mensal_ano_corrente():
    hoje = date.today()
    log.info("Disparando resincronizacao mensal do ano corrente (01/%s a %s)", hoje.year, hoje)
    resultado, erro = None, None
    with _sync_lock:
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
    with _sync_lock:
        try:
            resultado = rodar_backfill(date(ano_anterior, 1, 1), date(ano_anterior, 12, 31))
        except Exception as e:
            erro = str(e)
            log.exception("Resincronizacao de fechamento de ano falhou")
    _notificar(resultado, erro)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        init_db()  # garante que a tabela pedidos_sync existe
    except Exception:
        log.exception("Falha ao inicializar o banco no arranque do scheduler")
    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(job_semanal, CronTrigger(day_of_week="fri", hour=7, minute=59))
    scheduler.add_job(job_mensal_ano_corrente, CronTrigger(day=1, hour=8, minute=30))
    scheduler.add_job(job_fechamento_ano_anterior, CronTrigger(month=2, day=1, hour=8, minute=30))
    # Verifica a fila de pedidos manuais (botao do dashboard) a cada 20s.
    # coalesce + max_instances=1 evitam acumular execucoes se uma demorar.
    scheduler.add_job(
        job_processar_pedidos,
        IntervalTrigger(seconds=20),
        coalesce=True,
        max_instances=1,
    )
    log.info(
        "Agendador iniciado. Rotinas: sexta 07:59 (semanal), dia 1 de cada mes 08:30 "
        "(ano corrente), 1/fev 08:30 (fechamento ano anterior), fila de pedidos manuais "
        "a cada 20s. Timezone America/Sao_Paulo."
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Agendador interrompido.")

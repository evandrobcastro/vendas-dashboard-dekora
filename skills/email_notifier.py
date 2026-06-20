"""Skill: envia e-mail de resumo da sincronizacao via SMTP."""
import smtplib
from email.mime.text import MIMEText


def enviar_resumo(smtp_host: str, smtp_port: int, remetente: str, senha: str,
                   destinatarios: list[str], resultado: dict, erro: str | None = None) -> None:
    if erro:
        assunto = "⚠️ Falha na sincronização de vendas"
        corpo = f"A sincronização semanal falhou.\n\nErro:\n{erro}"
    else:
        assunto = "✅ Resumo semanal de vendas"
        corpo = (
            "Sincronização concluída com sucesso.\n\n"
            f"Linhas novas: {resultado.get('novos', 0)}\n"
            f"Linhas atualizadas: {resultado.get('atualizados', 0)}\n"
            f"Total processado: {resultado.get('total_processado', 0)}\n\n"
            "Acesse o dashboard para mais detalhes: http://dash.casadekora.com.br"
        )

    msg = MIMEText(corpo, _charset="utf-8")
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(remetente, senha)
        server.sendmail(remetente, destinatarios, msg.as_string())

# Vendas Casa Dekora — Guia rápido

Dashboard de vendas automatizado. Este arquivo explica como voltar a usar o
projeto, mesmo se você não tiver experiência com programação.

## Link do dashboard

https://dashboard-casadekora.streamlit.app/

Login: e-mail e senha individuais (cadastrados com `manage_users.py`, ver abaixo).

## Como pedir alterações no projeto (usando o Claude Code)

1. Abra o terminal (PowerShell) e entre na pasta do projeto:
   ```
   cd C:\Users\Evandro\Desktop\vendas-dashboard
   ```
2. Digite `claude` e aperte Enter.
3. Peça o que quiser em português, por exemplo:
   - "adiciona uma coluna de metas no dashboard"
   - "muda a cor dos gráficos"
   - "quero filtrar por segmento também"
4. Depois que a alteração for feita e testada, ela precisa ser **publicada**
   (commit + push) para o site no ar atualizar. Se você não pedir
   explicitamente, pode perguntar: "já posso publicar essa alteração?"

**Importante:** o site só atualiza depois do *push* para o GitHub. Alterar
arquivos localmente não muda o que está no ar até esse passo ser feito.

## Como funciona o pipeline (visão geral)

```
ECG Glass (ERP)  --Selenium-->  Excel baixado  --processamento-->  Banco Postgres (Supabase)  --leitura-->  Dashboard (Streamlit Cloud)
```

- O **download e processamento** (Selenium) só roda no seu PC Windows
  (precisa do Chrome instalado localmente). Por isso o PC precisa estar
  ligado nos horários de sincronização.
- O **banco de dados** vive na nuvem (Supabase), não no seu PC. É o que
  permite o dashboard na web ler os dados de qualquer lugar.
- O **dashboard** vive no Streamlit Community Cloud, conectado ao
  repositório do GitHub.

## Sincronizar os dados manualmente

Sem precisar abrir o Claude Code:
- **Pelo dashboard:** sidebar → "Administração" → botão "🔄 Sincronizar agora"
- **Pelo terminal:**
  ```
  cd C:\Users\Evandro\Desktop\vendas-dashboard
  .\venv\Scripts\python.exe orchestrator.py
  ```

## Sincronização automática

Se o programa `scheduler.py` estiver rodando continuamente no PC, três
rotinas disparam sozinhas (horário de Brasília):

| Rotina | Quando | O que faz |
|---|---|---|
| Semanal | Toda sexta-feira, 07:59 | Sincroniza só os últimos 7 dias (rápido) |
| Mensal | Todo dia 1, 08:30 | Resincroniza o ano corrente inteiro (01/jan até hoje) |
| Fechamento de ano | Todo 1º de fevereiro, 08:30 | Resincroniza o ano anterior completo (já "fechado") |

Cada execução envia o e-mail de resumo normal.

### Inicialização automática com o Windows

O `scheduler.py` está configurado para iniciar sozinho a cada login no
Windows, via um arquivo na pasta Inicializar:
```
C:\Users\Evandro\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\VendasDashboardScheduler.vbs
```
Esse `.vbs` chama `python.exe scheduler.py` de forma invisível (sem abrir
janela de terminal). Usamos um VBS em vez de atalho direto para
`pythonw.exe` porque o `pythonw.exe` "puro" trava ao importar bibliotecas
do projeto (provável incompatibilidade com `sys.stdout`/`stderr` sendo
`None`).

**Como verificar se está rodando:** abra o Gerenciador de Tarefas e procure
por um processo `python.exe` (sem janela visível) — ou veja se
`logs/scheduler.log` tem uma linha recente "Agendador iniciado".

**Como parar manualmente:** Gerenciador de Tarefas → encontrar o processo
`python.exe` referente ao projeto → Finalizar tarefa.

**Como reiniciar manualmente sem reiniciar o PC:**
```
cd C:\Users\Evandro\Desktop\vendas-dashboard
wscript.exe iniciar_scheduler.vbs
```

## Regra de atualização — janela de datas considerada

A sincronização **semanal** busca no ECG Glass apenas os últimos **7 dias**
antes de hoje:
- **Vendas:** filtra por `Data aprovação` (situação aprovado/fechado)
- **Orçamentos:** filtra por `Data cadastro` (situação aguard. aprov.,
  cancelado, pré-aprovado)

**Limitação conhecida:** um orçamento cadastrado há mais de 7 dias que for
**cancelado hoje** não é capturado pela sincronização semanal, porque o
filtro é pela data de cadastro, não pela data da última mudança. Por isso
existem as rotinas **mensal** e de **fechamento de ano** acima — elas
refazem o intervalo inteiro do zero e corrigem qualquer mudança perdida
pela sincronização semanal.

Para rodar manualmente um backfill de um intervalo qualquer:
```
cd C:\Users\Evandro\Desktop\vendas-dashboard
.\venv\Scripts\python.exe backfill.py 2023-01-01 2026-12-31
```

## Cadastrar/alterar um usuário do dashboard

```
cd C:\Users\Evandro\Desktop\vendas-dashboard
.\venv\Scripts\python.exe manage_users.py "email@casadekora.com.br" "SenhaAqui" "Nome da Pessoa"
```

## Onde estão as configurações sensíveis (senhas, credenciais)

- **No PC local:** arquivo `.env` (nunca é enviado ao GitHub)
- **No site (Streamlit Cloud):** painel do app → Settings → Secrets

Se alguma senha mudar (ERP, e-mail, banco), precisa atualizar nos dois
lugares.

## ⚠️ O repositório do GitHub precisa ficar PÚBLICO

O Streamlit Community Cloud (plano gratuito) só consegue clonar repositórios
**públicos**. Já tentamos autorizar o acesso a um repo privado e não
conseguimos encontrar a opção certa na interface do Streamlit/GitHub.

Se alguém deixar o repo como privado, o dashboard quebra com o erro
"Failed to download the sources for repository" (já aconteceu uma vez).
Não há segredo nenhum no código (senhas ficam só em `.env` local e em
Secrets no Streamlit Cloud), então deixá-lo público é seguro.

Se isso acontecer de novo, a correção é:
```
cd C:\Users\Evandro\Desktop\vendas-dashboard
gh repo edit evandrobcastro/vendas-dashboard-dekora --visibility public --accept-visibility-change-consequences
```
E depois, no painel "Manage app" do Streamlit Cloud: menu (⋮) → "Reboot app".

## Onde está o código

- GitHub (público — ver aviso acima): https://github.com/evandrobcastro/vendas-dashboard-dekora
- Pasta local: `C:\Users\Evandro\Desktop\vendas-dashboard`

## Estrutura de pastas

- `skills/` — as "peças" do pipeline: baixar do ERP, processar dados, gravar no banco, enviar e-mail
- `dashboard/app.py` — o site em si
- `orchestrator.py` — roda o pipeline completo (baixar → processar → gravar → notificar)
- `scheduler.py` — agenda a sincronização semanal
- `database.py` — desenho das tabelas do banco
- `manage_users.py` — cadastro de usuários do dashboard
- `downloads/` — Excel baixados do ERP (temporário)
- `logs/` — registros de execução

# Guia de Backup e Restauração — Dashboard Casa Dekora

> Última revisão: 18/07/2026. Este documento explica onde cada parte do
> sistema vive, o que fazer se o PC for perdido e como remontar tudo do zero.

## 1. Mapa do sistema — onde cada coisa vive

| Componente | Onde vive | Se o PC morrer... |
|---|---|---|
| Código completo (robôs, scheduler, dashboard web) | GitHub: `evandrobcastro/vendas-dashboard-dekora` | ✅ intacto |
| Site `dashboard.casadekora.com.br` | KingHost (`/www/dashboard`) | ✅ continua no ar |
| API (login, dados, admin) | Supabase Edge Functions (projeto `vendas-dekora`) | ✅ continua no ar |
| Dados de vendas/orçamentos/produtos/DRE | Supabase (nuvem) — reconstruíveis a partir do ECG | ✅ intactos |
| **Metas cadastradas e usuários do dashboard** | **Somente no Supabase** (não existem no ECG) | ✅ intactos, mas sem 2ª cópia — ver §4 |
| **Arquivo `.env` (todas as senhas)** | **Somente no PC** | ❌ precisa ser recriado — ver §3 |
| Sincronizações automáticas | Rodam NO PC (scheduler + Chrome) | ❌ param até remontar — ver §2 |

Fonte da verdade dos dados comerciais: o **ERP ECG**. Tudo que os robôs
gravam no Supabase pode ser recoletado de lá.

## 2. Remontar o sistema num PC novo (passo a passo)

1. **Instalar**: [Python 3.12](https://www.python.org/downloads/) (marcar
   "Add to PATH"), [Git](https://git-scm.com/download/win) e Google Chrome.
2. **Clonar o projeto** (no Prompt de Comando):
   ```
   cd %USERPROFILE%\Desktop
   git clone https://github.com/evandrobcastro/vendas-dashboard-dekora.git vendas-dashboard
   cd vendas-dashboard
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   ```
3. **Recriar o `.env`** na raiz do projeto — ver §3.
4. **Testar uma sincronização manual**:
   ```
   venv\Scripts\python orchestrator.py --dias 7
   ```
   Se baixar e gravar sem erro, o pipeline está vivo.
5. **Religar o scheduler no login do Windows**: copiar o arquivo
   `iniciar_scheduler.vbs` para a pasta de inicialização — apertar
   `Win+R`, digitar `shell:startup`, colar o arquivo lá (pode renomear para
   `VendasDashboardScheduler.vbs`). Dar dois cliques nele para iniciar já.
   O catch-up do scheduler recupera sozinho as janelas perdidas.
6. Pronto. O dashboard web e a API não dependem do PC — nada a fazer neles.

## 3. Recriar o arquivo `.env`

O `.env` fica na raiz do projeto e NUNCA vai para o GitHub. Modelo com todas
as chaves usadas (preencher os valores):

```
# ERP ECG (login do robô) — senha: redefinir no próprio ECG se perdida
ECG_USER=
ECG_PASSWORD=

# Banco Supabase — painel supabase.com > projeto vendas-dekora >
# Settings > Database (host/porta/usuário; senha pode ser redefinida lá)
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=

# E-mail de notificação (senha de app do provedor de e-mail)
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=587
EMAIL_FROM=
EMAIL_FROM_PASSWORD=
EMAIL_TO=

# FTP KingHost (deploy do dashboard web) — senha: painel KingHost >
# casadekora.com.br > Gerenciar FTP > Alterar senha
FTP_HOST=ftp.casadekora.com.br
FTP_USER=casadekora
FTP_PASSWORD=
```

Cada senha pode ser **redefinida na própria plataforma** (ECG, Supabase,
provedor de e-mail, KingHost) — nenhuma é irrecuperável.

> Dica: guarde uma foto/cópia do `.env` preenchido no seu gerenciador de
> senhas do celular. É a forma mais rápida de restaurar.

## 4. Dados que só existem no Supabase (metas e usuários)

As **metas** e os **usuários do dashboard** foram cadastrados à mão e não
existem no ECG. Para gerar uma cópia local quando quiser (ex.: antes de
mexidas grandes), rodar na raiz do projeto:

```
venv\Scripts\python backup_local.py
```

Isso cria `backup_metas.csv` e `backup_usuarios.csv` na pasta do projeto
(estão no `.gitignore`; guarde onde preferir). Restauração: pela aba Metas
do dashboard (inserção em lote) ou me chame que eu reimporto.

## 5. Reconstruir o banco a partir do ECG (caso extremo)

Se o banco Supabase for perdido/zerado, os robôs reconstroem tudo:

```
venv\Scripts\python backfill.py 2023-01-01 2026-12-31   # vendas + orçamentos (+ produtos e DRE dos anos)
venv\Scripts\python sync_produtos.py 2023-01 2026-12    # produtos, se precisar refazer só eles
venv\Scripts\python sync_financeiro.py 2023             # DRE por ano (repetir p/ 2024, 2025, 2026)
```

⚠️ Nunca rode dois desses ao mesmo tempo: o ECG permite só uma sessão por
usuário (o segundo login derruba o primeiro).

Metas e usuários: restaurar dos CSVs do §4.

## 6. Republicar o dashboard web (KingHost)

Se precisar reenviar o site (após restaurar o `.env` com a senha de FTP):

```
venv\Scripts\python webapp\deploy_kinghost.py
```

## 7. Recriar as Edge Functions (Supabase)

O código-fonte das três funções (`login`, `dados`, `admin`) está em
`webapp/supabase-functions/`. Para reimplantar: painel supabase.com >
Edge Functions > criar/editar com o conteúdo desses arquivos (`verify_jwt`
desativado — a autenticação é própria) — ou me chame que eu implanto pelo
conector.

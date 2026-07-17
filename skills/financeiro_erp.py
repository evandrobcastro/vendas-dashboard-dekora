"""
Skill: coleta do DRE "Desempenho Financeiro - conf. pagamentos" do ECG.

Fonte: financeiro/relatorios/desempenho_financeiro_pagamento/
rel_desempenho_financeiro_pagamento.php, com:
  - "Considerar apenas pagamentos/recebimentos ja recebidos e pagos" (caixa)
  - Forma de acompanhamento: "Venda baseada no pagamento dos orcamentos e
    custo das op. avulsas de fornecedores" (value 0) — escolha do usuario
  - Uma busca por loja cobre o intervalo inteiro (colunas = meses)

Estrutura da pagina:
  - cabecalho de meses: celulas "Janeiro/26", "Fevereiro/26", ...
  - linha de grupo (bg #03669f): "1- VENDAS", "2- IMPOSTOS", ...
  - linha de classe: nome + um valor por mes + colunas Total e Media
  - linhas TOTAL EM/DESEMPENHO/PROPORCAO/MARGEM/LUCRO: ignoradas (o
    dashboard recalcula os totais a partir das classes)

Granularidade gravada: ano_mes x loja x grupo x classe (valores != 0).
"""
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from download_erp import _build_driver, login

URL_DRE = ("https://ecgsistemas.com/ecg_glass/financeiro/relatorios/"
           "desempenho_financeiro_pagamento/"
           "rel_desempenho_financeiro_pagamento.php?tipo=filtrar")

LOJAS = {"CASA DEKORA": "1", "LACA 108": "8"}
FORMA_ACOMPANHAMENTO = "0"  # custo das op. avulsas de fornecedores

MES_NUM = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5,
           "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
           "novembro": 11, "dezembro": 12}

_IGNORAR = re.compile(
    r"^(TOTAL EM|DESEMPENHO|PROPORÇÃO|MARGEM|LUCRO|PONTO)", re.IGNORECASE)


def _num_br(texto: str) -> float:
    texto = re.sub(r"[^\d,.\-]", "", texto or "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def parse_dre(html: str, loja: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    # cabecalho: celulas "Janeiro/26" definem a ordem dos meses
    meses = []
    for cel in soup.find_all(string=re.compile(r"^[A-Za-zçÇ]+/\d{2}$")):
        m = re.match(r"^([A-Za-zçÇ]+)/(\d{2})$", cel.strip())
        num = MES_NUM.get(m.group(1).lower())
        if num:
            meses.append(f"20{m.group(2)}-{num:02d}")
    # remove duplicatas preservando a ordem (o cabecalho pode repetir)
    meses = list(dict.fromkeys(meses))
    if not meses:
        return []

    linhas = []
    grupo = ""
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        estilo = (tr.get("style") or "").lower()
        textos = [td.get_text(strip=True) for td in tds]
        nome = textos[1] if len(textos) > 1 else textos[0]
        # linha de grupo (azul)
        if "#03669f" in estilo and nome:
            grupo = nome
            continue
        if not grupo or not nome or _IGNORAR.match(nome):
            continue
        valores = [td.get_text(strip=True) for td in tds
                   if "text-end" in (td.get("class") or [])]
        # classe valida: um valor por mes (+ Total e Media no final)
        if len(valores) < len(meses):
            continue
        for am, bruto in zip(meses, valores[:len(meses)]):
            v = _num_br(bruto)
            if v != 0:
                linhas.append({"ano_mes": am, "loja": loja, "grupo": grupo,
                               "classe": nome, "valor": v})
    return linhas


def coletar_dre(driver, loja: str, ano_ini: int, mes_ini: int,
                ano_fim: int, mes_fim: int) -> list[dict]:
    driver.get(URL_DRE)
    time.sleep(3)
    Select(driver.find_element(By.NAME, "mesInicio")).select_by_value(f"{mes_ini:02d}")
    Select(driver.find_element(By.NAME, "anoInicio")).select_by_value(str(ano_ini % 100))
    Select(driver.find_element(By.NAME, "mesFinal")).select_by_value(f"{mes_fim:02d}")
    Select(driver.find_element(By.NAME, "anoFinal")).select_by_value(str(ano_fim % 100))
    Select(driver.find_element(By.NAME, "select_loja")).select_by_value(LOJAS[loja])
    Select(driver.find_element(By.NAME, "select_forma_acompanhamento")) \
        .select_by_value(FORMA_ACOMPANHAMENTO)
    cb = driver.find_element(By.NAME, "checkbox_pagamentos_liquidados")
    if not cb.is_selected():
        driver.execute_script("arguments[0].click();", cb)
    driver.find_element(By.CSS_SELECTOR, "input[value='Buscar']").click()
    time.sleep(12)
    return parse_dre(driver.page_source, loja)


def coletar_dre_lojas(usuario: str, senha: str, ano_ini: int, mes_ini: int,
                      ano_fim: int, mes_fim: int, headless: bool = True) -> list[dict]:
    """Coleta o DRE das duas lojas numa unica sessao de navegador."""
    from pathlib import Path
    driver = _build_driver(Path(__file__).parent.parent / "downloads", headless=headless)
    linhas = []
    try:
        login(driver, usuario, senha)
        for loja in LOJAS:
            linhas.extend(coletar_dre(driver, loja, ano_ini, mes_ini, ano_fim, mes_fim))
    finally:
        driver.quit()
    return linhas

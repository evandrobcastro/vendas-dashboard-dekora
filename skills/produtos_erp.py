"""
Skill: coleta do relatorio "Vendas por Projeto" do ECG (classe/subclasse).

Fonte: financeiro/relatorios/relVendasPorProjeto.php, filtrado por data de
APROVACAO com status padrao (aprovado + fechado) — mesma definicao de venda
do restante do dashboard. A leitura e feita da PROPRIA TELA de resultado
(o Excel junta classe e subclasse numa celula so, o que e ambiguo):

  - linha de classe:    <tr bgcolor #03669F><td colspan=10><b>CLASSE</b></td>
  - linha de subclasse: <tr> com <a onclick="fnc_detalhar_informacao..."> e
                        celulas com title (Quantidade, Metragem vidro, ...)
  - linha de total:     primeiro td comeca com "TOTAL" (ignorada)

Granularidade gravada: mes (ano_mes) x classe x subclasse.
"""
import calendar
import re
import time
from datetime import date

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from download_erp import _build_driver, login, _set_text_field

URL_PROJETO = "https://ecgsistemas.com/ecg_glass/financeiro/relatorios/relVendasPorProjeto.php"

# title da celula -> nome do campo gravado
CAMPOS = {
    "Quantidade": "quantidade",
    "Metragem vidro": "m2_vidro",
    "Metragem mão de obra de instalação": "m2_inst",
    "Peso Perfil": "peso_perfil",
    "Valor de venda": "valor_venda",
    "Valor de custo": "valor_custo",
    "Lucro": "lucro",
}


def _num_br(texto: str) -> float:
    texto = re.sub(r"[^\d,.-]", "", texto or "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def parse_resultado(html: str, ano_mes: str) -> list[dict]:
    """Extrai as linhas classe/subclasse da pagina de resultado."""
    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    classe = ""
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        # cabecalho de classe (linha azul com colspan)
        if len(tds) == 1 and tds[0].get("colspan") and tds[0].find("b"):
            classe = tds[0].get_text(strip=True)
            continue
        primeiro = tds[0].get_text(strip=True)
        if primeiro.upper().startswith("TOTAL"):
            continue
        link = tds[0].find("a", onclick=True)
        if not link or "fnc_detalhar_informacao" not in (link.get("onclick") or ""):
            continue
        registro = {
            "ano_mes": ano_mes,
            "classe": classe,
            "subclasse": link.get_text(strip=True),
        }
        for td in tds[1:]:
            campo = CAMPOS.get(td.get("title"))
            if campo:
                registro[campo] = _num_br(td.get_text(strip=True))
        linhas.append(registro)
    return linhas


def coletar_mes(driver, ano: int, mes: int) -> list[dict]:
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    ini = date(ano, mes, 1).strftime("%d%m%y")
    fim = date(ano, mes, ultimo_dia).strftime("%d%m%y")

    driver.get(URL_PROJETO)
    time.sleep(3)
    _set_text_field(driver, "editDataIni", ini)
    _set_text_field(driver, "editDataFim", fim)
    # fecha o calendario que abre ao focar o campo de data
    driver.find_element(By.TAG_NAME, "body").click()
    driver.find_elements(By.CSS_SELECTOR, "input[value='Buscar']")[-1].click()
    time.sleep(8)
    return parse_resultado(driver.page_source, f"{ano}-{mes:02d}")


def coletar_meses(usuario: str, senha: str, meses: list[str],
                  headless: bool = True) -> list[dict]:
    """Coleta varios meses ('YYYY-MM') numa unica sessao de navegador."""
    from pathlib import Path
    driver = _build_driver(Path(__file__).parent.parent / "downloads", headless=headless)
    linhas = []
    try:
        login(driver, usuario, senha)
        for am in meses:
            ano, mes = int(am[:4]), int(am[5:7])
            do_mes = coletar_mes(driver, ano, mes)
            linhas.extend(do_mes)
    finally:
        driver.quit()
    return linhas

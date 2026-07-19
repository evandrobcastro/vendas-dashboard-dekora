"""
Skill: coleta do "Relatorio de Reposicoes e Manutencoes" do ECG.

Fonte: ordemServico/relatorios/rel_reposicao.php, configurado como na foto
enviada pelo usuario:
  - Tipo = Detalhado (select_tipo_relatorio = 1)
  - Status = Todos (select_status = 0)
  - Data = Cadastro (select_tipo_data = 0), intervalo DDMMYY
  - Resp. reposicao e Motivo = "tudo selecionado" (marca todos os checkboxes
    dos widgets select_tipo_reposicao[] e select_motivo_filtro[])

Estrutura do resultado (por secao/tipo de OS):
  <div class="mt-4 mb-1"><b>SECAO</b></div> seguido de uma <table>.
  Secoes possiveis: MANUTENCAO - MONTADOR, MANUTENCAO - FORNECEDOR,
  REPOSICAO EMPRESA, REPOSICAO CLIENTE, REPOSICAO FORNECEDOR, MANUTENCAO.
  Cada linha de OS tem celulas identificadas por title:
    Identificacao da O.S., Fantasia (cliente), Cidade, Bairro, Data,
    Causador(es) (varios separados por <br>), Motivos (varios <span>),
    Metragem, Custo produtos X + servicos Y, Horas trabalhadas, Status.

Granularidade gravada: uma linha por OS. Motivos e causadores ficam como
texto separado por '|' (o dashboard divide para os rankings).
"""
import calendar
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from download_erp import _build_driver, login, _set_text_field

URL_REPO = "https://ecgsistemas.com/ecg_glass/ordemServico/relatorios/rel_reposicao.php"

_OS_RE = re.compile(r"^\d+(MANU|REPO)")


def _num_br(texto: str) -> float:
    texto = re.sub(r"[^\d,.-]", "", texto or "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def _data_iso(texto: str) -> tuple[str, str]:
    """'06/01/26' -> ('2026-01-06', '2026-01'). Retorna ('','') se invalida."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{2})", texto or "")
    if not m:
        return "", ""
    dia, mes, ano = m.groups()
    return f"20{ano}-{mes}-{dia}", f"20{ano}-{mes}"


def parse_reposicoes(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    linhas = []
    for div in soup.select("div.mt-4.mb-1"):
        b = div.find("b")
        if not b:
            continue
        secao = b.get_text(strip=True)
        tabela = div.find_next("table")
        if not tabela:
            continue
        for tr in tabela.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
            os_cod = tds[0].get_text(strip=True)
            if not _OS_RE.match(os_cod):
                continue
            cel = {td.get("title"): td for td in tds if td.get("title")}

            def txt(titulo):
                td = cel.get(titulo)
                return td.get_text(strip=True) if td else ""

            # motivos: um <span> por motivo; causadores: separados por <br>
            td_mot = cel.get("Motivos")
            motivos = "|".join(
                s.get_text(strip=True) for s in td_mot.find_all("span")
            ) if td_mot else txt("Motivos")
            td_cau = cel.get("Causador(es)")
            causadores = td_cau.get_text("|", strip=True) if td_cau else ""

            # custo = produtos + servicos (o title traz os dois valores)
            td_custo = next((td for t, td in cel.items()
                             if t and t.startswith("Custo")), None)
            custo = _num_br(td_custo.get_text(strip=True)) if td_custo else 0.0

            data_iso, ano_mes = _data_iso(txt("Data"))
            linhas.append({
                "os": os_cod,
                "tipo": secao,
                "identificacao": txt("Identificação da O.S."),
                "cliente": txt("Fantasia"),
                "cidade": txt("Cidade"),
                "bairro": txt("Bairro"),
                "data_cadastro": data_iso,
                "ano_mes": ano_mes,
                "causadores": causadores,
                "motivos": motivos,
                "metragem": _num_br(txt("Metragem")),
                "custo": custo,
                "horas": _num_br(txt("Horas trabalhadas")),
                "status": txt("Status"),
            })
    return linhas


def coletar_mes(driver, ano: int, mes: int) -> list[dict]:
    ultimo = calendar.monthrange(ano, mes)[1]
    ini = f"{1:02d}{mes:02d}{ano % 100:02d}"
    fim = f"{ultimo:02d}{mes:02d}{ano % 100:02d}"

    driver.get(URL_REPO)
    time.sleep(3)
    Select(driver.find_element(By.NAME, "select_tipo_relatorio")).select_by_value("1")  # Detalhado
    time.sleep(1)
    Select(driver.find_element(By.NAME, "select_status")).select_by_value("0")           # Todos
    Select(driver.find_element(By.NAME, "select_tipo_data")).select_by_value("0")        # Cadastro
    _set_text_field(driver, "text_data_inicio", ini)
    _set_text_field(driver, "text_data_final", fim)
    # "tudo selecionado" nos dois widgets multiplos
    for campo in ("select_tipo_reposicao[]", "select_motivo_filtro[]"):
        for cb in driver.find_elements(By.CSS_SELECTOR, f'input.ms_checkbox[name="{campo}"]'):
            if not cb.is_selected():
                driver.execute_script("arguments[0].click();", cb)
    botoes = driver.find_elements(By.XPATH, "//button[normalize-space()='Buscar']")
    driver.execute_script("arguments[0].click();", botoes[-1])
    time.sleep(8)
    return parse_reposicoes(driver.page_source)


def coletar_meses(usuario: str, senha: str, meses: list[str],
                  headless: bool = True) -> list[dict]:
    """Coleta varios meses ('YYYY-MM') numa unica sessao de navegador."""
    from pathlib import Path
    driver = _build_driver(Path(__file__).parent.parent / "downloads", headless=headless)
    linhas = []
    try:
        login(driver, usuario, senha)
        for am in meses:
            linhas.extend(coletar_mes(driver, int(am[:4]), int(am[5:7])))
    finally:
        driver.quit()
    return linhas

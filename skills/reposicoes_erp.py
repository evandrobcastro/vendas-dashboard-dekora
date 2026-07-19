"""
Skill: coleta do "Relatorio de Reposicoes e Manutencoes" do ECG.

Fonte: ordemServico/relatorios/rel_reposicao.php, configurado como na foto
enviada pelo usuario:
  - Tipo = Detalhado (select_tipo_relatorio = 1)
  - Status = Todos (select_status = 0)
  - Data = Cadastro (select_tipo_data = 0), intervalo DDMMYY
  - Resp. reposicao e Motivo = "tudo selecionado" (marca todos os checkboxes
    dos widgets select_tipo_reposicao[] e select_motivo_filtro[])

Estrutura do resultado (por secao):
  <div class="mt-4 mb-1"><b>SECAO</b></div> seguido de uma <table>.
  Ha DOIS tipos de bloco:
  1. MANUTENCAO (montador/fornecedor/producao): tem coluna "Motivos"; a
     categoria e "Manutencao"; codigo da OS termina em "MANU".
  2. REPOSICAO: as OS de reposicao vem agrupadas pelo MOTIVO, que e o
     proprio titulo do bloco (ERRO MEDICAO, ERRO PROJETO, FABRICACAO,
     QUEBRA, RISCO/FALHAS ...). NAO tem coluna "Motivos" (o motivo e a
     secao). Codigo da OS tem outro formato (ex.: "3203/25-2RE").
  Blocos "REPOSICAO EMPRESA/CLIENTE/FORNECEDOR" e "RESUMO DE CUSTO..." podem
  aparecer vazios/de resumo e sao ignorados (nao tem linhas de OS).

  Cada linha de OS tem celulas identificadas por title: Identificacao da
  O.S., Fantasia (cliente), Cidade, Bairro, Data, Causador(es), Metragem,
  Custo produtos X + servicos Y, Horas trabalhadas, Status (+ Motivos nos
  blocos de manutencao).

Granularidade gravada: uma linha por OS, com categoria (Manutencao/
Reposicao), tipo (nome da secao) e motivos separados por '|'.
"""
import calendar
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from download_erp import _build_driver, login, _set_text_field

URL_REPO = "https://ecgsistemas.com/ecg_glass/ordemServico/relatorios/rel_reposicao.php"

# titulos de bloco que sao resumo/agrupamento sem linhas de OS proprias
_BLOCOS_IGNORAR = ("RESUMO DE CUSTO",)

# o sufixo do codigo da OS de reposicao diz QUEM causou/paga (info do usuario):
#   RE = Reposicao Empresa (causada internamente), RC = Reposicao Cliente
#   (gerada pelo cliente), RF = Reposicao Fornecedor (falha de fornecedor).
_RESPONSAVEL = {"RE": "Empresa", "RC": "Cliente", "RF": "Fornecedor"}


def _responsavel(os_cod: str) -> str:
    m = re.search(r"(R[ECF])\s*$", (os_cod or "").upper())
    return _RESPONSAVEL.get(m.group(1), "") if m else ""


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
        if any(secao.upper().startswith(x) for x in _BLOCOS_IGNORAR):
            continue
        # blocos que comecam com MANUTEN sao manutencoes; os demais que tem
        # linhas de OS (ERRO MEDICAO, FABRICACAO, QUEBRA...) sao reposicoes,
        # e o motivo da reposicao e o proprio titulo do bloco.
        categoria = "Manutenção" if secao.upper().startswith("MANUTEN") else "Reposição"
        tabela = div.find_next("table")
        if not tabela:
            continue
        for tr in tabela.find_all("tr"):
            # linha de OS = tem a celula "Identificação da O.S." (o cabecalho nao tem)
            cel = {td.get("title"): td for td in tr.find_all("td") if td.get("title")}
            if "Identificação da O.S." not in cel:
                continue
            tds = tr.find_all("td")
            os_cod = tds[0].get_text(strip=True)

            def txt(titulo):
                td = cel.get(titulo)
                return td.get_text(strip=True) if td else ""

            # motivos: manutencao usa a coluna "Motivos" (um <span> por motivo);
            # reposicao nao tem essa coluna -> motivo = nome da secao.
            td_mot = cel.get("Motivos")
            if td_mot:
                motivos = "|".join(s.get_text(strip=True) for s in td_mot.find_all("span")) \
                          or td_mot.get_text(strip=True)
            else:
                motivos = secao
            td_cau = cel.get("Causador(es)")
            causadores = td_cau.get_text("|", strip=True) if td_cau else ""

            td_custo = next((td for t, td in cel.items()
                             if t and t.startswith("Custo")), None)
            custo = _num_br(td_custo.get_text(strip=True)) if td_custo else 0.0

            data_iso, ano_mes = _data_iso(txt("Data"))
            linhas.append({
                "os": os_cod,
                "categoria": categoria,
                "responsavel": _responsavel(os_cod) if categoria == "Reposição" else "",
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

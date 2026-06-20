"""
Skill: login no ECG Glass + download dos relatorios de Vendas e Orcamentos.

Mapeamento de campos descoberto via inspecao do formulario real em
rel_orcamentos.php (ver logs/rel_orcamentos_page.html):

  select_tipo_data_filtro (select nativo): 0=Atualizacao 1=Cadastro 2=Aprovacao 3=Prev.entrega
  text_data_inicio / text_data_termino (texto, formato DDMMYY)
  select_loja (select nativo): 1=CASA DEKORA
  select_formato (select nativo): detalhado / comparativo_geral / kanban
  select_ordenar (select nativo, sem id): orc_codigo, data_aprovacao, ...
  select_situacao[] (checkboxes): 0=Em edicao 1=Aguardando aprov. 2=Aprovado
                                   3=Cancelado 4=Pre-aprovado 5=Fechado
  select_opcionais[] (checkboxes): considerar_versoes / apenas_desatualizados
  select_mostrar[] (checkboxes): colunas extras do relatorio

Os demais filtros (vendedor, segmento, cidade, comissionado, etc.) ficam
em branco por padrao (= sem filtro = extrai tudo), entao nao precisam
ser tocados.
"""
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

LOGIN_URL = "https://ecgsistemas.com/ecg_glass/login/login.php"
REPORT_URL = "https://ecgsistemas.com/ecg_glass/orcamento/relatorios/rel_orcamentos/rel_orcamentos.php"

LOJA_CASA_DEKORA = "1"

SITUACAO = {
    "em_edicao": "0",
    "aguardando_aprov": "1",
    "aprovado": "2",
    "cancelado": "3",
    "pre_aprovado": "4",
    "fechado": "5",
}

TIPO_DATA = {
    "atualizacao": "0",
    "cadastro": "1",
    "aprovacao": "2",
    "prev_entrega": "3",
}

COLUNAS_MOSTRAR = [
    "identificacao", "situacao", "valor", "vendedor", "desconto",
    "data_cadastro", "data_aprovacao", "dias_para_aprovar_desde_orcado",
    "metragem", "cidade", "email", "valor_sem_desconto", "segmento",
    "comissionado", "forma_divulgacao",
]


@dataclass
class FiltroRelatorio:
    tipo_data: str          # 'cadastro' ou 'aprovacao'
    situacoes: list         # lista de chaves de SITUACAO
    data_inicio: date
    data_fim: date


def _build_driver(download_dir: Path, headless: bool = True) -> webdriver.Chrome:
    download_dir.mkdir(parents=True, exist_ok=True)
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1000")
    prefs = {
        "download.default_directory": str(download_dir.resolve()),
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True,
    }
    opts.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    if headless:
        # Necessario para permitir download automatico em modo headless novo
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {
            "behavior": "allow",
            "downloadPath": str(download_dir.resolve()),
        })
    return driver


def login(driver: webdriver.Chrome, usuario: str, senha: str) -> None:
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 15)
    user_field = wait.until(EC.presence_of_element_located((By.NAME, "text_usuario")))
    pass_field = driver.find_element(By.NAME, "password_senha")
    user_field.clear()
    user_field.send_keys(usuario)
    pass_field.clear()
    pass_field.send_keys(senha)
    driver.find_element(By.CSS_SELECTOR, "input[type=submit]").click()
    wait.until(lambda d: "login.php" not in d.current_url)


def _set_native_select(driver, name_or_id: str, value: str, by_id=False) -> None:
    locator = (By.ID, name_or_id) if by_id else (By.NAME, name_or_id)
    el = driver.find_element(*locator)
    Select(el).select_by_value(value)


def _sync_multiselect(driver, field_name: str, desired_values: list[str]) -> None:
    """Marca/desmarca checkboxes de um widget select_multiplo customizado."""
    checkboxes = driver.find_elements(By.CSS_SELECTOR, f'input.ms_checkbox[name="{field_name}[]"]')
    desired_set = set(desired_values)
    for cb in checkboxes:
        value = cb.get_attribute("value")
        should_check = value in desired_set
        if cb.is_selected() != should_check:
            driver.execute_script("arguments[0].click();", cb)


def _set_text_field(driver, name: str, value: str) -> None:
    el = driver.find_element(By.NAME, name)
    driver.execute_script("arguments[0].value = '';", el)
    el.send_keys(value)


def configurar_filtros(driver: webdriver.Chrome, filtro: FiltroRelatorio) -> None:
    wait = WebDriverWait(driver, 15)
    driver.get(REPORT_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "text_data_inicio")))

    _set_native_select(driver, "select_tipo_data_filtro", TIPO_DATA[filtro.tipo_data], by_id=True)
    _set_text_field(driver, "text_data_inicio", filtro.data_inicio.strftime("%d%m%y"))
    _set_text_field(driver, "text_data_termino", filtro.data_fim.strftime("%d%m%y"))
    _set_native_select(driver, "select_loja", LOJA_CASA_DEKORA, by_id=True)
    _set_native_select(driver, "select_formato", "detalhado", by_id=True)
    _set_native_select(driver, "select_ordenar", "orc_codigo")

    _sync_multiselect(driver, "select_situacao", [SITUACAO[s] for s in filtro.situacoes])
    _sync_multiselect(driver, "select_opcionais", ["considerar_versoes"])
    _sync_multiselect(driver, "select_mostrar", COLUNAS_MOSTRAR)


def _wait_download_complete(download_dir: Path, before: set, timeout: int = 60) -> Path:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = set(download_dir.glob("*.xlsx"))
        novos = current - before
        prontos = [f for f in novos if not (download_dir / (f.name + ".crdownload")).exists()]
        if prontos:
            time.sleep(1)  # garante que o arquivo terminou de ser escrito
            return max(prontos, key=lambda p: p.stat().st_mtime)
        time.sleep(1)
    raise TimeoutError(f"Download nao concluido em {timeout}s")


def baixar_relatorio(driver: webdriver.Chrome, download_dir: Path, filtro: FiltroRelatorio, novo_nome: str) -> Path:
    configurar_filtros(driver, filtro)

    wait = WebDriverWait(driver, 20)
    arquivos_antes = set(download_dir.glob("*.xlsx"))

    buscar = wait.until(EC.element_to_be_clickable((By.ID, "btn_buscar")))
    buscar.click()
    time.sleep(3)

    excel_btn = wait.until(EC.element_to_be_clickable((By.ID, "btn_excel")))
    excel_btn.click()

    arquivo = _wait_download_complete(download_dir, arquivos_antes)
    destino = download_dir / novo_nome
    if destino.exists():
        destino.unlink()
    arquivo.rename(destino)
    return destino


def baixar_vendas_e_orcamentos(usuario: str, senha: str, download_dir: Path,
                                data_inicio: date, data_fim: date,
                                headless: bool = True) -> dict:
    driver = _build_driver(download_dir, headless=headless)
    resultado = {}
    try:
        login(driver, usuario, senha)

        timestamp = date.today().strftime("%Y%m%d")

        filtro_vendas = FiltroRelatorio(
            tipo_data="aprovacao",
            situacoes=["aprovado", "fechado"],
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        resultado["vendas"] = baixar_relatorio(
            driver, download_dir, filtro_vendas, f"vendas_{timestamp}.xlsx"
        )

        filtro_orcamentos = FiltroRelatorio(
            tipo_data="cadastro",
            situacoes=["aguardando_aprov", "cancelado", "pre_aprovado"],
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        resultado["orcamentos"] = baixar_relatorio(
            driver, download_dir, filtro_orcamentos, f"orcamentos_{timestamp}.xlsx"
        )
    finally:
        driver.quit()
    return resultado


if __name__ == "__main__":
    import os
    import sys
    from datetime import timedelta
    from dotenv import load_dotenv

    sys.stdout.reconfigure(encoding="utf-8")
    base = Path(__file__).parent.parent
    load_dotenv(base / ".env")

    hoje = date.today()
    inicio = hoje - timedelta(days=7)

    arquivos = baixar_vendas_e_orcamentos(
        usuario=os.getenv("ECG_USER"),
        senha=os.getenv("ECG_PASSWORD"),
        download_dir=base / "downloads",
        data_inicio=inicio,
        data_fim=hoje,
        headless=True,
    )
    print("Arquivos baixados:")
    for tipo, caminho in arquivos.items():
        print(f"  {tipo}: {caminho}")

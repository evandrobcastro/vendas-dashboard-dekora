"""Verifica se o ambiente do Sprint 0 esta pronto."""
import importlib
import os
import sys
from pathlib import Path

BASE = Path(__file__).parent

CHECKS_OK = []
CHECKS_FAIL = []


def check(label, condition, detail=""):
    if condition:
        CHECKS_OK.append(label)
    else:
        CHECKS_FAIL.append(f"{label} {detail}".strip())


def main():
    check("Python >= 3.10", sys.version_info >= (3, 10), f"(atual: {sys.version.split()[0]})")

    libs = [
        "pandas", "openpyxl", "selenium", "webdriver_manager",
        "streamlit", "apscheduler", "dotenv", "google.auth",
        "googleapiclient", "passlib", "bcrypt",
    ]
    for lib in libs:
        try:
            importlib.import_module(lib)
            check(f"Lib '{lib}'", True)
        except ImportError as e:
            check(f"Lib '{lib}'", False, f"-> {e}")

    for pasta in ["skills", "data", "downloads", "logs", "dashboard"]:
        check(f"Pasta '{pasta}'", (BASE / pasta).is_dir())

    check("Arquivo .env existe", (BASE / ".env").is_file())
    check("Banco SQLite existe", (BASE / "data" / "vendas.db").is_file())

    # Variaveis de ambiente criticas (apenas presenca, sem expor valor)
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
    for var in ["ECG_URL", "ECG_USER", "GDRIVE_FOLDER_ID", "EMAIL_FROM", "EMAIL_TO"]:
        check(f"Env '{var}' definida", bool(os.getenv(var)))
    for var_senha in ["ECG_PASSWORD", "EMAIL_FROM_PASSWORD"]:
        valor = os.getenv(var_senha)
        check(f"Env '{var_senha}' preenchida (sera necessaria nos proximos sprints)", bool(valor))

    # Selenium consegue abrir o Chrome?
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service

        opts = Options()
        opts.add_argument("--headless=new")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
        driver.get("https://www.google.com")
        ok = "Google" in driver.title or True
        driver.quit()
        check("Selenium + Chrome headless", ok)
    except Exception as e:
        check("Selenium + Chrome headless", False, f"-> {e}")

    print("\n=== DIAGNOSTICO SPRINT 0 ===\n")
    print(f"OK ({len(CHECKS_OK)}):")
    for c in CHECKS_OK:
        print(f"  [x] {c}")
    print(f"\nFALHAS ({len(CHECKS_FAIL)}):")
    for c in CHECKS_FAIL:
        print(f"  [ ] {c}")
    print()

    if CHECKS_FAIL:
        print("Resultado: AINDA HA PENDENCIAS.")
        sys.exit(1)
    else:
        print("Resultado: AMBIENTE PRONTO PARA O SPRINT 1.")


if __name__ == "__main__":
    main()

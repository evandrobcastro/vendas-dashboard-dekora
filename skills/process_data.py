"""
Skill: le os Excel baixados do ERP (vendas/orcamentos), normaliza nomes
de coluna para o schema do banco, valida e unifica em um DataFrame unico.
"""
from pathlib import Path

import pandas as pd

# Mapeia o cabecalho exibido no Excel do ECG Glass -> coluna do banco (ver database.py)
COLUNA_EXCEL_PARA_DB = {
    "Código": "codigo",
    "Cliente": "cliente",
    "Identificação": "identificacao",
    "Situação": "situacao",
    "Valor": "valor",
    "Vendedor": "vendedor",
    "Desconto": "desconto",
    "Data cadastro": "data_cadastro",
    "Data aprovação": "data_aprovacao",
    "Dias p/aprovação desde orçado": "dias_aprovacao",
    "Metragem": "metragem",
    "Cidade": "cidade",
    "E-mail": "email",
    "Valor s/desc.": "valor_sem_desc",
    "Segmento": "segmento",
    "Comissionado": "comissionado",
    "Forma de divulgação": "forma_divulgacao",
}

COLUNAS_OBRIGATORIAS = set(COLUNA_EXCEL_PARA_DB.keys())

COLUNAS_NUMERICAS = ["valor", "desconto", "metragem", "valor_sem_desc"]
COLUNAS_DATA = ["data_cadastro", "data_aprovacao"]


class ValidacaoError(Exception):
    pass


def _converter_data(serie: pd.Series) -> pd.Series:
    # Formato de origem: dd/mm/aa
    convertida = pd.to_datetime(serie, format="%d/%m/%y", errors="coerce")
    return convertida.dt.strftime("%Y-%m-%d")


def carregar_planilha(caminho: Path, tipo: str) -> pd.DataFrame:
    """Le um Excel exportado do ECG Glass e retorna DataFrame no schema do banco.

    tipo: 'venda' ou 'orcamento'
    """
    df = pd.read_excel(caminho, header=1)

    faltantes = COLUNAS_OBRIGATORIAS - set(df.columns)
    if faltantes:
        raise ValidacaoError(
            f"{caminho.name}: colunas faltando no Excel: {sorted(faltantes)}"
        )

    df = df[list(COLUNA_EXCEL_PARA_DB.keys())].rename(columns=COLUNA_EXCEL_PARA_DB)

    df["codigo"] = df["codigo"].astype(str).str.strip()
    vazios = df["codigo"].isin(["", "nan", "None"]) | df["codigo"].isna()
    if vazios.any():
        raise ValidacaoError(f"{caminho.name}: {vazios.sum()} linha(s) sem Código (chave unica)")

    duplicados = df["codigo"][df["codigo"].duplicated()]
    if not duplicados.empty:
        raise ValidacaoError(
            f"{caminho.name}: códigos duplicados dentro do proprio arquivo: {duplicados.tolist()}"
        )

    for col in COLUNAS_NUMERICAS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in COLUNAS_DATA:
        df[col] = _converter_data(df[col])

    df["dias_aprovacao"] = pd.to_numeric(df["dias_aprovacao"], errors="coerce").astype("Int64")
    df["tipo"] = tipo

    return df


def unificar(caminho_vendas: Path, caminho_orcamentos: Path) -> pd.DataFrame:
    df_vendas = carregar_planilha(caminho_vendas, tipo="venda")
    df_orcamentos = carregar_planilha(caminho_orcamentos, tipo="orcamento")

    combinado = pd.concat([df_vendas, df_orcamentos], ignore_index=True)

    duplicados_entre_arquivos = combinado["codigo"][combinado["codigo"].duplicated()]
    if not duplicados_entre_arquivos.empty:
        raise ValidacaoError(
            "Códigos presentes em ambos os arquivos (vendas E orçamentos): "
            f"{sorted(set(duplicados_entre_arquivos))}"
        )

    return combinado


if __name__ == "__main__":
    import sys
    from glob import glob

    sys.stdout.reconfigure(encoding="utf-8")
    downloads = Path(__file__).parent.parent / "downloads"

    vendas_files = sorted(downloads.glob("vendas_*.xlsx"), reverse=True)
    orcamentos_files = sorted(downloads.glob("orcamentos_*.xlsx"), reverse=True)

    if not vendas_files or not orcamentos_files:
        print("Nenhum arquivo de vendas/orcamentos encontrado em downloads/. Rode skills/download_erp.py primeiro.")
        sys.exit(1)

    df = unificar(vendas_files[0], orcamentos_files[0])
    print(f"Total unificado: {len(df)} linhas")
    print(f"  vendas: {(df['tipo'] == 'venda').sum()}")
    print(f"  orcamentos: {(df['tipo'] == 'orcamento').sum()}")
    print("\nAmostra:")
    print(df.head(5).to_string())
    print("\nTipos de dados:")
    print(df.dtypes)

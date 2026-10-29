"""Limpa a ANEEL: só pessoa jurídica, CNPJ normalizado e potência numérica, em Parquet.

Entrada: raw/aneel/empreendimento-geracao-distribuida.parquet (ou o .csv extraído do zip).
1 linha = 1 usina (sem duplicatas de CodEmpreendimento). CPF mascarado é descartado.
"""
import duckdb

from common import PQ_ANEEL, RAW_ANEEL

PARQUET = RAW_ANEEL / "empreendimento-geracao-distribuida.parquet"
CSV = RAW_ANEEL / "empreendimento-geracao-distribuida.csv"


def main() -> None:
    PQ_ANEEL.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    if PARQUET.exists():
        origem = f"read_parquet('{PARQUET}')"
    else:  # CSV: UTF-8, ';', aspas, CRLF; 16 linhas têm aspas quebradas no titular
        origem = f"read_csv('{CSV}', delim=';', header=true, all_varchar=true, quote='\"', ignore_errors=true)"
    con.execute(f"CREATE VIEW bruto AS SELECT * FROM {origem}")
    cols = [r[0] for r in con.execute("DESCRIBE bruto").fetchall()]
    print("colunas ANEEL:", cols)
    for c in ("NumCPFCNPJ", "SigTipoConsumidor", "MdaPotenciaInstaladaKW"):
        if c not in cols:
            raise SystemExit(f"Coluna {c} não encontrada.")
    destino = PQ_ANEEL / "aneel_pj.parquet"
    # Potência vem como "32,50" ou ",55" (sem zero antes da vírgula); replace resolve os dois.
    con.execute(f"""
        COPY (
          SELECT * EXCLUDE (cnpj_tmp), cnpj_tmp AS cnpj, left(cnpj_tmp, 8) AS cnpj_raiz,
                 try_cast(replace(CAST(MdaPotenciaInstaladaKW AS VARCHAR), ',', '.') AS DOUBLE) AS potencia_kw
          FROM (
            SELECT *, regexp_replace(CAST(NumCPFCNPJ AS VARCHAR), '[^0-9]', '', 'g') AS cnpj_tmp FROM bruto
            WHERE SigTipoConsumidor = 'PJ' AND CAST(NumCPFCNPJ AS VARCHAR) NOT LIKE '%*%'
          ) WHERE length(cnpj_tmp) = 14
        ) TO '{destino}' (FORMAT parquet, COMPRESSION zstd)""")
    n, ncnpj = con.execute(f"SELECT count(*), count(DISTINCT cnpj) FROM read_parquet('{destino}')").fetchone()
    print(f"usinas PJ: {n} ({ncnpj} CNPJ distintos)")


if __name__ == "__main__":
    main()

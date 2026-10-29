"""Limpa a ANEEL: só pessoa jurídica (CNPJ de 14 dígitos), CNPJ normalizado, em Parquet.

CPFs mascarados (***.218.193-**) viram menos de 14 dígitos e são descartados.
"""
import duckdb

from common import PQ_ANEEL, RAW_ANEEL

ARQ = RAW_ANEEL / "empreendimentos_gd.csv"


def main() -> None:
    PQ_ANEEL.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    # Tudo como texto; encoding latin-1 e ';' são o padrão dos CSVs da ANEEL (ajuste se o arquivo diferir).
    con.execute(f"""
        CREATE VIEW bruto AS
        SELECT * FROM read_csv('{ARQ}', delim=';', header=true, all_varchar=true,
                               encoding='latin-1', sample_size=-1)""")
    cols = [r[0] for r in con.execute("DESCRIBE bruto").fetchall()]
    print("colunas ANEEL:", cols)
    if "NumCPFCNPJ" not in cols:
        raise SystemExit("Coluna NumCPFCNPJ não encontrada; confira delimitador/encoding acima.")
    con.execute(f"""
        COPY (
          SELECT *, regexp_replace(NumCPFCNPJ, '[^0-9]', '', 'g') AS cnpj,
                    left(regexp_replace(NumCPFCNPJ, '[^0-9]', '', 'g'), 8) AS cnpj_raiz
          FROM bruto
          WHERE length(regexp_replace(NumCPFCNPJ, '[^0-9]', '', 'g')) = 14
            AND NumCPFCNPJ NOT LIKE '%*%'
        ) TO '{PQ_ANEEL / "aneel_pj.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{PQ_ANEEL / 'aneel_pj.parquet'}')").fetchone()[0]
    print(f"linhas PJ: {n}")


if __name__ == "__main__":
    main()

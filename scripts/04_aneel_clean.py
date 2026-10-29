"""Limpa a ANEEL: só pessoa jurídica (SigTipoConsumidor=PJ, CNPJ de 14 dígitos), sem duplicatas, em Parquet.

CPFs mascarados (***.218.193-**) são descartados. 1 linha por CodEmpreendimento.
"""
import duckdb

from common import PQ_ANEEL, RAW_ANEEL

ARQ = RAW_ANEEL / "empreendimentos_gd.csv"


def main() -> None:
    PQ_ANEEL.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    # Tudo como texto. Formato real (amostra): ';', aspas, UTF-8, CRLF, decimal com vírgula.
    con.execute(f"""
        CREATE VIEW bruto AS
        SELECT * FROM read_csv('{ARQ}', delim=';', header=true, all_varchar=true,
                               quote='"', sample_size=-1)""")
    cols = [r[0] for r in con.execute("DESCRIBE bruto").fetchall()]
    print("colunas ANEEL:", cols)
    if "NumCPFCNPJ" not in cols:
        raise SystemExit("Coluna NumCPFCNPJ não encontrada; confira delimitador/encoding acima.")
    if "CodEmpreendimento" not in cols:
        raise SystemExit("Coluna CodEmpreendimento não encontrada.")
    # O arquivo repete o mesmo empreendimento em várias linhas: mantém 1 por CodEmpreendimento
    # (a linha mais recente de atualização cadastral).
    con.execute(f"""
        COPY (
          SELECT * EXCLUDE (rn, cnpj_tmp), cnpj_tmp AS cnpj, left(cnpj_tmp, 8) AS cnpj_raiz FROM (
          SELECT *, regexp_replace(NumCPFCNPJ, '[^0-9]', '', 'g') AS cnpj_tmp,
                 row_number() OVER (PARTITION BY CodEmpreendimento
                                    ORDER BY DthAtualizaCadastralEmpreend DESC) AS rn
          FROM bruto
          WHERE SigTipoConsumidor = 'PJ' AND NumCPFCNPJ NOT LIKE '%*%'
          ) WHERE rn = 1 AND length(cnpj_tmp) = 14
        ) TO '{PQ_ANEEL / "aneel_pj.parquet"}' (FORMAT parquet, COMPRESSION zstd)""")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{PQ_ANEEL / 'aneel_pj.parquet'}')").fetchone()[0]
    print(f"linhas PJ: {n}")


if __name__ == "__main__":
    main()

"""Junta consumo CCEE (mensal por CNPJ) com geração distribuída ANEEL.

Gera output/consumo_x_gd_por_cnpj.parquet (+ .csv) e output/consumo_x_gd_por_raiz.parquet (+ .csv).
Potência: soma de MdaPotenciaInstaladaKW se a coluna existir.
"""
import duckdb

from common import OUTPUT, PQ_CCEE_AGG, PQ_ANEEL


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    aneel = PQ_ANEEL / "aneel_pj.parquet"
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{aneel}')").fetchall()}
    pot = (
        "sum(try_cast(replace(MdaPotenciaInstaladaKW, ',', '.') AS DOUBLE))"
        if "MdaPotenciaInstaladaKW" in cols else "NULL"
    )
    con.execute(f"CREATE VIEW ccee AS SELECT * FROM read_parquet('{PQ_CCEE_AGG}/*.parquet')")
    for chave, nome in (("cnpj", "por_cnpj"), ("cnpj_raiz", "por_raiz")):
        ccee_cols = (
            "cnpj, any_value(nome_empresarial) nome_empresarial, any_value(estado) estado, any_value(submercado) submercado,"
            if chave == "cnpj" else "cnpj_raiz, any_value(nome_empresarial) nome_empresarial,"
        )
        con.execute(f"""
            CREATE OR REPLACE TABLE final AS
            WITH c AS (
              SELECT mes_referencia, {ccee_cols}
                     sum(qtd_cargas) qtd_cargas,
                     sum(consumo_ajustado_mwh) consumo_ajustado_mwh,
                     sum(consumo_acl_mwh) consumo_acl_mwh,
                     sum(consumo_ponto_conexao_mwh) consumo_ponto_conexao_mwh
              FROM ccee GROUP BY mes_referencia, {chave}
            ),
            a AS (
              SELECT {chave}, count(*) AS qtd_empreendimentos_gd, {pot} AS potencia_instalada_kw
              FROM read_parquet('{aneel}') GROUP BY {chave}
            )
            SELECT c.*, coalesce(a.qtd_empreendimentos_gd, 0) AS qtd_empreendimentos_gd,
                   a.potencia_instalada_kw, a.{chave} IS NOT NULL AS tem_gd
            FROM c LEFT JOIN a USING ({chave})""")
        base = OUTPUT / f"consumo_x_gd_{nome}"
        con.execute(f"COPY final TO '{base}.parquet' (FORMAT parquet, COMPRESSION zstd)")
        con.execute(f"COPY final TO '{base}.csv' (HEADER, DELIMITER ';')")
        n, g = con.execute("SELECT count(*), count(*) FILTER (WHERE tem_gd) FROM final").fetchone()
        print(f"{nome}: {n} linhas, {g} com GD")


if __name__ == "__main__":
    main()

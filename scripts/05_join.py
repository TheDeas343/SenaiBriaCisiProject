"""Junta consumo CCEE (mensal por CNPJ) com geração distribuída ANEEL.

Gera em output/ (Parquet + CSV):
  consumo_x_gd_por_cnpj  - 1 linha por mês x CNPJ, com GD da unidade (mesmo CNPJ) e GD da empresa (mesma raiz)
  consumo_x_gd_por_raiz  - 1 linha por mês x CNPJ raiz
Distribuidoras ficam de fora por padrão (são ~60% do MWh e não são consumidoras finais): --incluir-distribuidor.
No cruzamento real, CNPJ inteiro casa ~3% e a raiz ~33%: a raiz é o que dá volume.
"""
import argparse

import duckdb

from common import OUTPUT, PQ_ANEEL, PQ_CCEE_AGG


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incluir-distribuidor", action="store_true")
    args = ap.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    aneel = PQ_ANEEL / "aneel_pj.parquet"
    filtro = "" if args.incluir_distribuidor else "WHERE classe_perfil_agente <> 'Distribuidor'"
    con.execute(f"CREATE VIEW ccee AS SELECT * FROM read_parquet('{PQ_CCEE_AGG}/*.parquet') {filtro}")
    for chave in ("cnpj", "cnpj_raiz"):
        con.execute(f"""
            CREATE OR REPLACE VIEW gd_{chave} AS
            SELECT {chave}, count(*) AS qtd_gd, sum(potencia_kw) AS potencia_kw,
                   string_agg(DISTINCT SigTipoGeracao, ', ') AS tipos_geracao,
                   any_value(NomTitularEmpreendimento) AS titular_aneel
            FROM read_parquet('{aneel}') GROUP BY {chave}""")

    # --- por CNPJ: GD da unidade e GD da empresa (raiz)
    con.execute("""
        CREATE OR REPLACE TABLE final AS
        SELECT c.mes_referencia, c.cnpj, c.cnpj_raiz, c.nome_empresarial, c.estado, c.submercado,
               c.classe_perfil_agente, c.qtd_cargas, c.consumo_ajustado_mwh, c.consumo_acl_mwh,
               c.consumo_cativo_mwh, c.consumo_ponto_conexao_mwh,
               coalesce(u.qtd_gd, 0) AS qtd_empreendimentos_gd, u.potencia_kw AS potencia_instalada_kw,
               u.tipos_geracao AS tipos_geracao_gd, u.qtd_gd IS NOT NULL AS tem_gd,
               coalesce(r.qtd_gd, 0) AS qtd_gd_raiz, r.potencia_kw AS potencia_gd_raiz_kw,
               r.titular_aneel AS titular_aneel_raiz, r.qtd_gd IS NOT NULL AS tem_gd_raiz
        FROM ccee c
        LEFT JOIN gd_cnpj u ON u.cnpj = c.cnpj
        LEFT JOIN gd_cnpj_raiz r ON r.cnpj_raiz = c.cnpj_raiz""")
    gravar(con, "consumo_x_gd_por_cnpj")

    # --- por raiz: soma do consumo da empresa toda
    con.execute("""
        CREATE OR REPLACE TABLE final AS
        SELECT c.mes_referencia, c.cnpj_raiz, any_value(c.nome_empresarial) AS nome_empresarial,
               count(DISTINCT c.cnpj) AS qtd_cnpj, sum(c.qtd_cargas) AS qtd_cargas,
               sum(c.consumo_ajustado_mwh) AS consumo_ajustado_mwh, sum(c.consumo_acl_mwh) AS consumo_acl_mwh,
               sum(c.consumo_cativo_mwh) AS consumo_cativo_mwh,
               sum(c.consumo_ponto_conexao_mwh) AS consumo_ponto_conexao_mwh,
               coalesce(any_value(r.qtd_gd), 0) AS qtd_empreendimentos_gd,
               any_value(r.potencia_kw) AS potencia_instalada_kw, any_value(r.tipos_geracao) AS tipos_geracao_gd,
               any_value(r.titular_aneel) AS titular_aneel, any_value(r.qtd_gd) IS NOT NULL AS tem_gd
        FROM ccee c LEFT JOIN gd_cnpj_raiz r ON r.cnpj_raiz = c.cnpj_raiz
        GROUP BY c.mes_referencia, c.cnpj_raiz""")
    gravar(con, "consumo_x_gd_por_raiz")


def gravar(con, nome: str) -> None:
    base = OUTPUT / nome
    con.execute(f"COPY final TO '{base}.parquet' (FORMAT parquet, COMPRESSION zstd)")
    con.execute(f"COPY final TO '{base}.csv' (HEADER, DELIMITER ';')")
    n, g = con.execute("SELECT count(*), count(*) FILTER (WHERE tem_gd) FROM final").fetchone()
    print(f"{nome}: {n} linhas, {g} com GD")


if __name__ == "__main__":
    main()

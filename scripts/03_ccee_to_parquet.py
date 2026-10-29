"""Converte cada .csv.gz da CCEE em Parquet (detalhe) e em agregado mensal por CNPJ.

Pula meses já convertidos. Lê o gz direto no DuckDB.
"""
import duckdb

from common import PQ_CCEE, PQ_CCEE_AGG, RAW_CCEE

COLUNAS = {
    "MES_REFERENCIA": "VARCHAR", "DATA": "DATE", "PERIODO_COMERCIALIZACAO": "INTEGER",
    "CODIGO_CARGA": "VARCHAR", "NOME_CARGA": "VARCHAR", "DATA_MIGRACAO": "DATE",
    "CODIGO_PERFIL_AGENTE": "VARCHAR", "SIGLA_PERFIL_AGENTE": "VARCHAR", "CLASSE_PERFIL_AGENTE": "VARCHAR",
    "NOME_EMPRESARIAL": "VARCHAR", "CNPJ_CARGA": "VARCHAR", "CIDADE_CARGA": "VARCHAR",
    "ESTADO_CARGA": "VARCHAR", "SUBMERCADO": "VARCHAR", "CODIGO_PERFIL_AGENTE_DISTRIBUIDORA": "VARCHAR",
    "SIGLA_PERFIL_AGENTE_DISTRIBUIDORA": "VARCHAR", "CAPACIDADE_CARGA": "DOUBLE",
    "CONSUMO_CARGA_ACL": "DOUBLE", "CONSUMO_CARGA_AJUSTADO_ACL": "DOUBLE",
    "CONSUMO_CARGA_AJUSTADO": "DOUBLE", "CONSUMO_CARGA_PONTO_CONEXAO": "DOUBLE",
}


def main() -> None:
    PQ_CCEE.mkdir(parents=True, exist_ok=True)
    PQ_CCEE_AGG.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    tipos = ", ".join(f"'{k}': '{v}'" for k, v in COLUNAS.items())
    for src in sorted(RAW_CCEE.glob("*.csv.gz")):
        mes = src.name.split("_")[-1].split(".")[0]
        det = PQ_CCEE / f"mes={mes}.parquet"
        agg = PQ_CCEE_AGG / f"mes={mes}.parquet"
        if det.exists() and agg.exists():
            print(f"já convertido: {mes}")
            continue
        print(f"convertendo {mes} ...")
        leitura = f"""read_csv('{src}', delim=';', header=true, dateformat='%d/%m/%Y',
                    types={{{tipos}}}, compression='gzip', ignore_errors=false)"""
        con.execute(f"COPY (SELECT * FROM {leitura}) TO '{det}.tmp' (FORMAT parquet, COMPRESSION zstd)")
        # Normaliza o CNPJ: só dígitos, 14 posições (a origem perde o zero da frente em alguns casos).
        # Unidades: tudo em MWh. AJUSTADO = reconciliado = ACL + cativo (AJUSTADO_ACL é o cativo, apesar do nome).
        con.execute(f"""
            COPY (
              SELECT MES_REFERENCIA AS mes_referencia,
                     lpad(regexp_replace(CNPJ_CARGA, '[^0-9]', '', 'g'), 14, '0') AS cnpj,
                     left(lpad(regexp_replace(CNPJ_CARGA, '[^0-9]', '', 'g'), 14, '0'), 8) AS cnpj_raiz,
                     any_value(NOME_EMPRESARIAL) AS nome_empresarial,
                     any_value(ESTADO_CARGA) AS estado,
                     any_value(SUBMERCADO) AS submercado,
                     any_value(CLASSE_PERFIL_AGENTE) AS classe_perfil_agente,
                     count(DISTINCT CODIGO_CARGA) AS qtd_cargas,
                     sum(CONSUMO_CARGA_AJUSTADO) AS consumo_ajustado_mwh,
                     sum(CONSUMO_CARGA_ACL) AS consumo_acl_mwh,
                     sum(CONSUMO_CARGA_AJUSTADO_ACL) AS consumo_cativo_mwh,
                     sum(CONSUMO_CARGA_PONTO_CONEXAO) AS consumo_ponto_conexao_mwh
              FROM read_parquet('{det}.tmp')
              WHERE CNPJ_CARGA IS NOT NULL  -- 2 cargas de Distribuidor vêm sem CNPJ
              GROUP BY ALL
            ) TO '{agg}' (FORMAT parquet, COMPRESSION zstd)""")
        (PQ_CCEE / f"mes={mes}.parquet.tmp").rename(det)
        print(f"ok: {mes}")


if __name__ == "__main__":
    main()

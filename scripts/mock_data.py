"""Dados falsos no mesmo esquema da tabela final (output/consumo_x_gd_por_cnpj)."""
import numpy as np
import pandas as pd

EMPRESAS = ["Alfa Siderurgia", "Beta Alimentos", "Gama Cimentos", "Delta Papel", "Ômega Química",
            "Sigma Têxtil", "Lambda Mineração", "Kappa Plásticos", "Theta Bebidas", "Zeta Logística",
            "Atlas Fertilizantes", "Nova Varejo", "Prisma Vidros", "Vértice Metais", "Aurora Frigoríficos"]
UF = {"SP": "SUDESTE", "MG": "SUDESTE", "RJ": "SUDESTE", "RS": "SUL", "PR": "SUL", "BA": "NORDESTE", "PE": "NORDESTE", "GO": "SUDESTE"}
CLASSES = ["Consumidor Livre", "Consumidor Especial", "Autoprodutor"]


def gerar(meses: int = 12, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    periodos = pd.period_range(end="2026-08", periods=meses, freq="M").strftime("%Y%m")
    linhas = []
    for i, nome in enumerate(EMPRESAS):
        raiz = f"{10_000_000 + i * 137_001:08d}"
        uf = list(UF)[i % len(UF)]
        for f in range(int(rng.integers(1, 4))):  # filiais
            cnpj = f"{raiz}{f + 1:04d}{rng.integers(10, 99)}"
            base = rng.uniform(300, 9000)
            tem_gd = rng.random() < 0.3
            pot = float(rng.uniform(100, 3000)) if tem_gd else None
            qtd_gd = int(rng.integers(1, 6)) if tem_gd else 0
            classe = CLASSES[int(rng.integers(0, 3))]
            for k, mes in enumerate(periodos):
                sazonal = 1 + 0.15 * np.sin(k / 12 * 2 * np.pi)
                cons = base * sazonal * rng.uniform(0.9, 1.1)
                linhas.append(dict(
                    mes_referencia=mes, cnpj=cnpj, cnpj_raiz=raiz, nome_empresarial=nome, estado=uf,
                    submercado=UF[uf], classe_perfil_agente=classe, qtd_cargas=int(rng.integers(1, 5)),
                    consumo_ajustado_mwh=cons, consumo_acl_mwh=cons, consumo_cativo_mwh=0.0, consumo_ponto_conexao_mwh=cons * 0.98,
                    qtd_empreendimentos_gd=qtd_gd, potencia_instalada_kw=pot, tem_gd=tem_gd))
    df = pd.DataFrame(linhas)
    # GD da empresa toda (mesma raiz), como no cruzamento real
    r = df.drop_duplicates("cnpj").groupby("cnpj_raiz").agg(
        qtd_gd_raiz=("qtd_empreendimentos_gd", "sum"), potencia_gd_raiz_kw=("potencia_instalada_kw", "sum"))
    df = df.merge(r, left_on="cnpj_raiz", right_index=True)
    df["tem_gd_raiz"] = df.qtd_gd_raiz > 0
    df.loc[~df.tem_gd_raiz, "potencia_gd_raiz_kw"] = None
    return df


if __name__ == "__main__":
    from common import OUTPUT
    OUTPUT.mkdir(exist_ok=True)
    gerar().to_parquet(OUTPUT / "consumo_x_gd_por_cnpj.parquet", index=False)
    print("mock gravado em output/")

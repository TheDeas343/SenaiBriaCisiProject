"""UI: consumo CCEE x geração distribuída ANEEL. Rodar: streamlit run app/dashboard.py"""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from mock_data import gerar  # noqa: E402

MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
            "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
AZUL, LARANJA, GRID, INK = "#2a78d6", "#eb6834", "#e4e3df", "#52514e"
PARQUET = ROOT / "output" / "consumo_x_gd_por_cnpj.parquet"

st.set_page_config(page_title="Consumo x Geração Distribuída", layout="wide")


@st.cache_data
def carregar() -> tuple[pd.DataFrame, bool]:
    if PARQUET.exists():
        return duckdb.sql(f"SELECT * FROM read_parquet('{PARQUET}')").df(), False
    return gerar(), True


def estilo(fig: go.Figure, h: int = 340, x_cat: bool = True) -> go.Figure:
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color=INK, size=12),
                      legend=dict(orientation="h", y=1.12, x=0), hoverlabel=dict(font_size=12))
    fig.update_xaxes(showgrid=False, linecolor=GRID, type="category" if x_cat else "linear")
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def br(v: float, casas: int = 0) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


df, mock = carregar()
df["ano"] = df.mes_referencia.str[:4].astype(int)
df["mes_num"] = df.mes_referencia.str[4:].astype(int)
df["mes_label"] = df.mes_num.map(lambda n: MESES_PT[n - 1][:3]) + "/" + df.ano.astype(str)
st.title("Consumo (CCEE) × Geração Distribuída (ANEEL)")
if mock:
    st.warning("Dados FALSOS (mock). Rode o pipeline para gerar output/consumo_x_gd_por_cnpj.parquet.", icon="⚠️")

# ---- filtros (sempre visíveis, na barra lateral) ----
with st.sidebar:
    st.header("Filtros")
    anos = st.multiselect("Ano", sorted(df.ano.unique(), reverse=True), default=sorted(df.ano.unique()))
    meses_sel = st.multiselect("Mês", MESES_PT, default=MESES_PT, help="Tire meses para comparar períodos (ex.: só o verão).")
    estados = st.multiselect("Estado", sorted(df.estado.dropna().unique()))
    subs = st.multiselect("Submercado", sorted(df.submercado.dropna().unique()))
    classes = st.multiselect("Classe", sorted(df.classe_perfil_agente.dropna().unique()))
    visao = st.radio("Agrupar por", ["CNPJ raiz (empresa)", "CNPJ (unidade)"],
                     help="Raiz = matriz + filiais. Pelo CNPJ inteiro casam só ~3% das unidades; pela raiz ~33%.")
    gd = st.radio("Geração distribuída", ["Todos", "Com GD", "Sem GD"], horizontal=True)

unidade = visao.startswith("CNPJ (")
chave = "cnpj" if unidade else "cnpj_raiz"
# GD da unidade (mesmo CNPJ) ou da empresa toda (mesma raiz), conforme o agrupamento
TEM, POT, QTD = (("tem_gd", "potencia_instalada_kw", "qtd_empreendimentos_gd") if unidade
                 else ("tem_gd_raiz", "potencia_gd_raiz_kw", "qtd_gd_raiz"))
f = df[df.ano.isin(anos) & df.mes_num.isin([MESES_PT.index(m) + 1 for m in meses_sel])]
for col, sel in (("estado", estados), ("submercado", subs), ("classe_perfil_agente", classes)):
    if sel:
        f = f[f[col].isin(sel)]
if gd != "Todos":
    f = f[f[TEM] == (gd == "Com GD")]
if f.empty:
    st.info("Nenhum dado para esses filtros.")
    st.stop()

# ---- KPIs ----
un = f.drop_duplicates(chave)
pot = un[POT].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Consumo total (MWh)", br(f.consumo_ajustado_mwh.sum()))
c2.metric("Empresas" if not unidade else "Unidades (CNPJ)", br(f[chave].nunique()))
c3.metric("% com GD", f"{br(100 * un[TEM].mean(), 1)}%")
c4.metric("Potência GD (kW)", br(pot))

# ---- consumo por mês, com x sem GD ----
esq, dir_ = st.columns([3, 2])
with esq:
    st.subheader("Consumo mensal (MWh)")
    m = f.groupby(["mes_referencia", "mes_label", TEM]).consumo_ajustado_mwh.sum().reset_index().sort_values("mes_referencia")
    fig = go.Figure()
    for flag, nome, cor in ((False, "Sem GD", AZUL), (True, "Com GD", LARANJA)):
        d = m[m[TEM] == flag]
        if len(d):
            fig.add_bar(x=d.mes_label, y=d.consumo_ajustado_mwh, name=nome, marker_color=cor,
                        hovertemplate="%{x}<br>" + nome + ": %{y:,.0f} MWh<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_xaxes(categoryorder="array", categoryarray=list(m.mes_label.unique()))
    st.plotly_chart(estilo(fig), width="stretch")
with dir_:
    st.subheader("Top 10 por consumo (MWh)")
    t = (f.groupby([chave, "nome_empresarial"]).consumo_ajustado_mwh.sum().nlargest(10)
         .reset_index().sort_values("consumo_ajustado_mwh"))
    rot = t.nome_empresarial + " · " + t[chave]
    fig = go.Figure(go.Bar(x=t.consumo_ajustado_mwh, y=rot, orientation="h", marker_color=AZUL,
                           hovertemplate="%{y}<br>%{x:,.0f} MWh<extra></extra>"))
    st.plotly_chart(estilo(fig, x_cat=False).update_xaxes(showgrid=True).update_layout(margin=dict(l=0, r=0, t=10, b=0)), width="stretch")

# ---- consumo x potência GD ----
st.subheader("Consumo × potência de GD instalada")
s = (f.groupby([chave, "nome_empresarial"]).agg(consumo=("consumo_ajustado_mwh", "sum"),
     potencia=(POT, "max"), n=(QTD, "max")).reset_index())
s = s[s.potencia.notna()]
fig = go.Figure(go.Scatter(x=s.consumo, y=s.potencia, mode="markers", marker=dict(color=LARANJA, size=10,
                line=dict(color="#fcfcfb", width=2)), text=s.nome_empresarial,
                hovertemplate="%{text}<br>Consumo: %{x:,.0f} MWh<br>GD: %{y:,.0f} kW<extra></extra>"))
fig.update_xaxes(title="Consumo no período (MWh)", showgrid=True)
fig.update_yaxes(title="Potência GD (kW)")
st.plotly_chart(estilo(fig, 300, x_cat=False), width="stretch")

# ---- tabela ----
st.subheader("Tabela")
tab = (f.groupby([chave, "nome_empresarial", "estado", TEM], dropna=False)
       .agg(consumo_mwh=("consumo_ajustado_mwh", "sum"), potencia_gd_kw=(POT, "max"),
            empreendimentos_gd=(QTD, "max")).reset_index()
       .sort_values("consumo_mwh", ascending=False))
st.dataframe(tab, width="stretch", hide_index=True, column_config={
    "consumo_mwh": st.column_config.NumberColumn("Consumo (MWh)", format="%.0f"),
    "potencia_gd_kw": st.column_config.NumberColumn("Potência GD (kW)", format="%.0f")})
st.download_button("Baixar CSV", tab.to_csv(index=False, sep=";").encode("utf-8-sig"), "consumo_x_gd.csv")

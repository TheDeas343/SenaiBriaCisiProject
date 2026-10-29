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
st.title("Consumo (CCEE) × Geração Distribuída (ANEEL)")
if mock:
    st.warning("Dados FALSOS (mock). Rode o pipeline para gerar output/consumo_x_gd_por_cnpj.parquet.", icon="⚠️")

# ---- filtros (sempre visíveis, na barra lateral) ----
meses = sorted(df.mes_referencia.unique())
with st.sidebar:
    st.header("Filtros")
    ini, fim = st.select_slider("Período (mês)", options=meses, value=(meses[0], meses[-1]))
    estados = st.multiselect("Estado", sorted(df.estado.dropna().unique()))
    subs = st.multiselect("Submercado", sorted(df.submercado.dropna().unique()))
    classes = st.multiselect("Classe", sorted(df.classe_perfil_agente.dropna().unique()))
    gd = st.radio("Geração distribuída", ["Todos", "Com GD", "Sem GD"], horizontal=True)
    visao = st.radio("Agrupar por", ["CNPJ (unidade)", "CNPJ raiz (empresa)"])

f = df[(df.mes_referencia >= ini) & (df.mes_referencia <= fim)]
for col, sel in (("estado", estados), ("submercado", subs), ("classe_perfil_agente", classes)):
    if sel:
        f = f[f[col].isin(sel)]
if gd != "Todos":
    f = f[f.tem_gd == (gd == "Com GD")]
chave = "cnpj" if visao.startswith("CNPJ (") else "cnpj_raiz"
if f.empty:
    st.info("Nenhum dado para esses filtros.")
    st.stop()

# ---- KPIs ----
un = f.drop_duplicates(chave)
pot = f.drop_duplicates("cnpj").potencia_instalada_kw.sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Consumo total (MWh)", br(f.consumo_ajustado_mwh.sum()))
c2.metric("Empresas/unidades", br(f[chave].nunique()))
c3.metric("% com GD", f"{br(100 * un.tem_gd.mean(), 1)}%")
c4.metric("Potência GD (kW)", br(pot))

# ---- consumo por mês, com x sem GD ----
esq, dir_ = st.columns([3, 2])
with esq:
    st.subheader("Consumo mensal (MWh)")
    m = f.groupby(["mes_referencia", "tem_gd"]).consumo_ajustado_mwh.sum().reset_index()
    fig = go.Figure()
    for flag, nome, cor in ((False, "Sem GD", AZUL), (True, "Com GD", LARANJA)):
        d = m[m.tem_gd == flag]
        if len(d):
            fig.add_bar(x=d.mes_referencia, y=d.consumo_ajustado_mwh, name=nome, marker_color=cor,
                        hovertemplate="%{x}<br>" + nome + ": %{y:,.0f} MWh<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.35)
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
     potencia=("potencia_instalada_kw", "max"), n=("qtd_empreendimentos_gd", "max")).reset_index())
s = s[s.potencia.notna()]
fig = go.Figure(go.Scatter(x=s.consumo, y=s.potencia, mode="markers", marker=dict(color=LARANJA, size=10,
                line=dict(color="#fcfcfb", width=2)), text=s.nome_empresarial,
                hovertemplate="%{text}<br>Consumo: %{x:,.0f} MWh<br>GD: %{y:,.0f} kW<extra></extra>"))
fig.update_xaxes(title="Consumo no período (MWh)", showgrid=True)
fig.update_yaxes(title="Potência GD (kW)")
st.plotly_chart(estilo(fig, 300, x_cat=False), width="stretch")

# ---- tabela ----
st.subheader("Tabela")
tab = (f.groupby([chave, "nome_empresarial", "estado", "tem_gd"], dropna=False)
       .agg(consumo_mwh=("consumo_ajustado_mwh", "sum"), potencia_gd_kw=("potencia_instalada_kw", "max"),
            empreendimentos_gd=("qtd_empreendimentos_gd", "max")).reset_index()
       .sort_values("consumo_mwh", ascending=False))
st.dataframe(tab, width="stretch", hide_index=True, column_config={
    "consumo_mwh": st.column_config.NumberColumn("Consumo (MWh)", format="%.0f"),
    "potencia_gd_kw": st.column_config.NumberColumn("Potência GD (kW)", format="%.0f")})
st.download_button("Baixar CSV", tab.to_csv(index=False, sep=";").encode("utf-8-sig"), "consumo_x_gd.csv")

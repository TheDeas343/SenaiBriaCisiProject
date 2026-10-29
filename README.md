# Consumo CCEE x Geração Distribuída ANEEL

Pipeline Python + DuckDB + Parquet. Rodar da raiz do repositório, de rede doméstica/escritório (a CCEE bloqueia IPs de nuvem).

```bash
pip install -r requirements.txt
python scripts/01_download_ccee.py --listar   # confira meses/URLs encontrados na API
python scripts/01_download_ccee.py --meses 30 # 1 arquivo por vez, com pausa
python scripts/02_download_aneel.py
python scripts/03_ccee_to_parquet.py
python scripts/04_aneel_clean.py
python scripts/05_join.py                     # gera output/ para o Power BI
```

Fatos confirmados nos dados reais (202608):
- CCEE: 30 meses (202403 a 202608), recursos GZIP; o mês está no nome do recurso. Unidade MWh; `CONSUMO_CARGA_AJUSTADO` é o consumo da empresa
  (`AJUSTADO_ACL` é o cativo). Alguns CNPJ vêm com 13 dígitos (lpad 14); 2 cargas de Distribuidor vêm sem CNPJ.
- ANEEL: usa-se o `.parquet` (o CSV tem 16 linhas com aspas quebradas). 1 linha = 1 usina; potência pode vir como `,55`.
- Cruzamento: pelo CNPJ inteiro casa ~3% das unidades; pela raiz ~33%. A tabela por CNPJ traz as duas visões (GD da unidade e da raiz).
- Distribuidoras ficam fora da tabela final por padrão (`05_join.py --incluir-distribuidor` para incluir).
Se o download da CCEE devolver ~1 KB, é página de bloqueio (o script recusa arquivos < 10 MB).

## UI (Streamlit)
```bash
streamlit run app/dashboard.py
```
Lê `output/consumo_x_gd_por_cnpj.parquet`; se não existir, usa dados FALSOS (`scripts/mock_data.py`) com aviso na tela.
Filtros: período (mês), estado, submercado, classe, com/sem GD. Agrupar por CNPJ raiz (padrão) ou CNPJ usa a GD da empresa ou da unidade.

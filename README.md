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

Pontos a confirmar na 1ª execução real: formato do nome/descrição dos recursos na API da CCEE
(`--listar`), qual CSV do dataset ANEEL é o de empreendimentos, e encoding/delimitador desse CSV.
Se o download da CCEE devolver ~1 KB, é página de bloqueio (o script recusa arquivos < 10 MB).

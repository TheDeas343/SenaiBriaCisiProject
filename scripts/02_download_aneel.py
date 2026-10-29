"""Baixa o .parquet de empreendimentos de geração distribuída da ANEEL para raw/aneel/.

Usa o .parquet (mesmo conteúdo do CSV do zip, mas sem as linhas com aspas quebradas).
"""
import requests

from common import ANEEL_API, ANEEL_DATASET, RAW_ANEEL, download

NOME = "empreendimento-geracao-distribuida.parquet"


def main() -> None:
    r = requests.get(ANEEL_API, params={"id": ANEEL_DATASET}, timeout=60)
    r.raise_for_status()
    recursos = [x for x in r.json()["result"]["resources"] if x.get("name") == NOME]
    if not recursos:
        raise SystemExit(f"Recurso {NOME} não encontrado no dataset.")
    dest = RAW_ANEEL / NOME
    download(recursos[0]["url"], dest, min_bytes=1_000_000)
    print(f"ok: {dest} ({dest.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

"""Baixa o CSV de empreendimentos de geração distribuída da ANEEL para raw/aneel/."""
import requests

from common import ANEEL_API, ANEEL_DATASET, RAW_ANEEL, download


def main() -> None:
    r = requests.get(ANEEL_API, params={"id": ANEEL_DATASET}, timeout=60)
    r.raise_for_status()
    recursos = r.json()["result"]["resources"]
    csvs = [x for x in recursos if x.get("format", "").upper() == "CSV" or x["url"].lower().endswith(".csv")]
    if not csvs:
        raise SystemExit("Nenhum recurso CSV no dataset; recursos: " + ", ".join(x["url"] for x in recursos))
    # Se houver vários CSVs (ex.: dicionário de dados), o de empreendimentos é o mais recente/maior; confira no log.
    for x in csvs:
        print("CSV:", x.get("name"), x["url"])
    rec = csvs[0]
    dest = RAW_ANEEL / "empreendimentos_gd.csv"
    download(rec["url"], dest)
    print(f"ok: {dest} ({dest.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()

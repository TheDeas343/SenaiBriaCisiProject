"""Baixa os .csv.gz mensais da CCEE (1 por vez, com pausa). Pula o que já existe.

Uso: python scripts/01_download_ccee.py [--meses 30] [--pausa 20] [--listar]
Rodar de rede doméstica/escritório: IPs de nuvem são bloqueados.
"""
import argparse
import re
import time

import requests

from common import BROWSER_HEADERS, CCEE_API, CCEE_DATASET, MIN_CCEE_BYTES, RAW_CCEE, download


def listar_recursos() -> list[dict]:
    r = requests.get(CCEE_API, params={"id": CCEE_DATASET}, headers=BROWSER_HEADERS, timeout=60)
    r.raise_for_status()
    recursos = r.json()["result"]["resources"]
    saida = []
    for rec in recursos:
        # name: consumo_horario_perfil_agente_AAAAMM. A description é o dicionário de dados (igual em todos).
        m = re.search(r"_(20\d{2}(?:0[1-9]|1[0-2]))$", rec.get("name", ""))
        if m and rec.get("format", "").upper() == "GZIP":
            saida.append({"mes": m.group(1), "url": rec["url"], "nome": rec["name"]})
    return saida


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meses", type=int, default=30, help="quantos meses mais recentes baixar")
    ap.add_argument("--pausa", type=int, default=20, help="segundos entre downloads")
    ap.add_argument("--listar", action="store_true", help="só lista os recursos encontrados")
    args = ap.parse_args()

    recursos = listar_recursos()
    if args.listar:
        for r in recursos:
            print(r["mes"], r["nome"], r["url"])
        return

    recursos = sorted(recursos, key=lambda r: r["mes"], reverse=True)[: args.meses]

    for r in recursos:
        dest = RAW_CCEE / f"consumo_horario_{r['mes']}.csv.gz"
        if dest.exists():
            print(f"já existe: {dest.name}")
            continue
        print(f"baixando {r['mes']} ...")
        download(r["url"], dest, headers=BROWSER_HEADERS, min_bytes=MIN_CCEE_BYTES)
        print(f"ok: {dest.name} ({dest.stat().st_size / 1e6:.0f} MB)")
        time.sleep(args.pausa)


if __name__ == "__main__":
    main()

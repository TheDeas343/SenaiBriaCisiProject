"""Roda o pipeline completo em sequência. Pensado para cron / agendador de tarefas.

Seguro para repetir: a CCEE só baixa meses novos e a conversão pula meses prontos.
A ANEEL é rebaixada a cada execução (o arquivo é uma foto atual, atualizada todo mês).
Se um passo falha, para e retorna erro (o cron registra no log).
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PASSOS = ["01_download_ccee.py", "02_download_aneel.py", "03_ccee_to_parquet.py", "04_aneel_clean.py", "05_join.py"]


def main() -> None:
    for passo in PASSOS:
        print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {passo}", flush=True)
        r = subprocess.run([sys.executable, str(AQUI / passo), *sys.argv[1:]] if passo.startswith("01") else
                           [sys.executable, str(AQUI / passo)])
        if r.returncode != 0:
            raise SystemExit(f"Falhou em {passo} (código {r.returncode})")
    print("Pipeline concluído.")


if __name__ == "__main__":
    main()

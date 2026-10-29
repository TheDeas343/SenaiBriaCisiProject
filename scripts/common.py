"""Configuração compartilhada entre os scripts do pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_CCEE = ROOT / "raw" / "ccee"
RAW_ANEEL = ROOT / "raw" / "aneel"
PQ_CCEE = ROOT / "parquet" / "ccee"          # detalhe horário, 1 arquivo por mês
PQ_CCEE_AGG = ROOT / "parquet" / "ccee_agg"  # consumo mensal por CNPJ
PQ_ANEEL = ROOT / "parquet" / "aneel"
OUTPUT = ROOT / "output"

CCEE_API = "https://dadosabertos.ccee.org.br/api/3/action/package_show"
CCEE_DATASET = "consumo_horario_perfil_agente"
ANEEL_API = "https://dadosabertos.aneel.gov.br/api/3/action/package_show"
ANEEL_DATASET = "relacao-de-empreendimentos-de-geracao-distribuida"

# Cabeçalhos de navegador: sem eles o firewall da CCEE devolve página de bloqueio.
BROWSER_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="154", "Google Chrome";v="154", "Not A(Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}

# Abaixo disso o arquivo é provavelmente a página de bloqueio (~1 KB).
MIN_CCEE_BYTES = 10 * 1024 * 1024


def download(url: str, dest: Path, headers: dict | None = None, min_bytes: int = 0) -> None:
    """Baixa para dest.part e só renomeia se o tamanho fizer sentido."""
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, headers=headers, stream=True, timeout=(30, 120), allow_redirects=True) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    size = tmp.stat().st_size
    if size < min_bytes:
        tmp.unlink()
        raise RuntimeError(f"{url}: só {size} bytes — provável página de bloqueio (firewall).")
    tmp.rename(dest)

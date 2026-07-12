"""
scripts/fix_legacy_data.py

Script de migração/limpeza única para o histórico já salvo em data/.

O bug: valores ausentes de connectorID / startChargingOn (e afins)
foram gravados como string vazia '' (ou a string literal "None") em
vez de nulo real, deixando colunas como connector_id e start_time com
tipo misto e quebrando a serialização Arrow no dashboard Streamlit.

O que este script faz (sem tocar em nenhuma lógica de negócio):

1. sessions.csv / attempts.csv — troca '' e "None" por nulo nas
   colunas afetadas, força connector_id para inteiro nullable (Int64)
   e as colunas de tempo para datetime, e resalva os CSVs.
2. last_state.json — troca '' por null nos campos dos conectores.
3. snapshots/*/*.jsonl — troca '' por null nos campos do resumo de
   conectores de cada snapshot.

Um backup .bak é criado ao lado de cada arquivo antes de sobrescrever.

Uso:
    python scripts/fix_legacy_data.py
"""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

# permite rodar de qualquer diretório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (  # noqa: E402
    SESSIONS_FILE,
    ATTEMPTS_FILE,
    LAST_STATE_FILE,
    SNAPSHOT_DIR,
)

EMPTY_MARKERS = ["", "None", "nan"]

DATETIME_COLUMNS = ["start_time", "end_time", "prep_start", "prep_end"]


def _backup(path: Path):
    shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def _null_if_empty(value):
    return None if value in ("", "None", "nan") else value


def fix_csv(path: Path):

    if not path.exists() or path.stat().st_size == 0:
        print(f"- {path.name}: não existe ou vazio, pulando.")
        return

    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    df = df.replace(EMPTY_MARKERS, pd.NA)

    if "connector_id" in df.columns:
        df["connector_id"] = pd.to_numeric(
            df["connector_id"], errors="coerce"
        ).astype("Int64")

    for col in DATETIME_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    _backup(path)

    df.to_csv(path, index=False)

    print(f"- {path.name}: {len(df)} linhas limpas e resalvas.")


def fix_last_state(path: Path):

    if not path.exists() or path.stat().st_size == 0:
        print(f"- {path.name}: não existe ou vazio, pulando.")
        return

    state = json.loads(path.read_text(encoding="utf-8"))

    changed = 0

    for station_id, connectors in state.items():
        for conn_id, info in connectors.items():
            for key, value in info.items():
                cleaned = _null_if_empty(value)
                if cleaned is not value:
                    info[key] = cleaned
                    changed += 1

    _backup(path)

    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"- {path.name}: {changed} campos corrigidos.")


def fix_snapshots(snapshot_dir: Path):

    for file in sorted(snapshot_dir.glob("*/*.jsonl")):

        lines_out = []
        changed = 0

        with open(file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue

                payload = json.loads(line)

                for conn in payload.get("connectors", []):
                    for key, value in conn.items():
                        cleaned = _null_if_empty(value)
                        if cleaned is not value:
                            conn[key] = cleaned
                            changed += 1

                lines_out.append(json.dumps(payload, ensure_ascii=False))

        if changed:
            _backup(file)
            file.write_text("\n".join(lines_out) + "\n", encoding="utf-8")

        print(
            f"- snapshots/{file.parent.name}/{file.name}: "
            f"{changed} campos corrigidos."
        )


if __name__ == "__main__":

    print("Corrigindo dados legados ('' -> nulo, tipos corretos)...\n")

    fix_csv(SESSIONS_FILE)
    fix_csv(ATTEMPTS_FILE)
    fix_last_state(LAST_STATE_FILE)
    fix_snapshots(SNAPSHOT_DIR)

    print("\nConcluído. Backups .bak criados ao lado dos arquivos alterados.")

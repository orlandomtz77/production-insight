"""Master lists: lines, products and downtime reasons (data/master/*.csv)."""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MASTER_FILES = {
    "lines": ("lines.csv", "line"),
    "products": ("products.csv", "product"),
    "downtime_reasons": ("downtime_reasons.csv", "downtime_reason"),
}


class MasterDataError(Exception):
    """A master list is missing, unreadable or empty."""


@dataclass(frozen=True)
class MasterLists:
    lines: frozenset[str]
    products: frozenset[str]
    downtime_reasons: frozenset[str]


def load_master_lists(master_dir: Path) -> MasterLists:
    values = {}
    for name, (file_name, column) in MASTER_FILES.items():
        path = Path(master_dir) / file_name
        if not path.exists():
            raise MasterDataError(f"No se encontró la lista maestra '{path}'.")
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as error:
            raise MasterDataError(f"No se pudo leer la lista maestra '{path}': {error}") from error
        if column not in df.columns:
            raise MasterDataError(f"La lista maestra '{path}' no tiene la columna '{column}'.")
        items = frozenset(value.strip() for value in df[column] if value.strip())
        if not items:
            raise MasterDataError(f"La lista maestra '{path}' está vacía.")
        values[name] = items
    return MasterLists(**values)

import re
from typing import Tuple


def norm_title(value: str) -> str:
    """Normalize Oracle/Excel DCB_TITLE keys.

    Examples:
      - "Drawing Authority" -> "drawing authority"
      - "drawing (authority)" -> "drawing authority"
      - "B/L" -> "b l"
    """
    if value is None:
        return ""
    s = str(value).strip().lower()
    # Convert punctuation into spaces ((), /, -, _, etc.)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_dwg_and_sheets(raw: str) -> Tuple[str, str]:
    """Extract drawing number and sheet(s) from a combined value.

    Handles common variants:
      - "DWG123 SHT 2"
      - "DWG123 SHT 2 & 3"
      - "DWG123 Sheet 1, 2"
      - "DWG123 (sheet) 04"
      - "DWG123 sht 1-3"

    Returns: (dwg, sheets_str)
      sheets_str examples: "2", "2,3", "1-3", "" (if none)
    """
    if not raw:
        return "", ""

    s = str(raw).strip()

    # Split on SHT or SHEET (case-insensitive)
    parts = re.split(r"(?i)\b(?:sht|sheet)\b", s, maxsplit=1)
    dwg = parts[0].strip(" :-\t") if parts else s.strip()

    sheets = ""
    if len(parts) == 2:
        tail = parts[1]

        # Range like 1-3
        rng = re.search(r"(\d+)\s*-\s*(\d+)", tail)
        if rng:
            sheets = f"{int(rng.group(1))}-{int(rng.group(2))}"
        else:
            nums = re.findall(r"\d+", tail)
            if nums:
                # Normalize: remove leading zeros via int()
                cleaned = [str(int(n)) for n in nums]

                # Dedup while preserving order
                seen = set()
                uniq = []
                for n in cleaned:
                    if n not in seen:
                        seen.add(n)
                        uniq.append(n)

                sheets = ",".join(uniq)

    return dwg, sheets


# Map normalized titles to requirement types
INSTALLATION_MAP = {
    norm_title("bond reading"): "BOND",
    norm_title("ohms number"): "BOND",
    norm_title("torque value"): "TORQUE",
    norm_title("torque value 2"): "TORQUE",
    norm_title("dcma required? yes/no"): "DCMA",
    norm_title("bms number"): "SEAL",
}

"""Fetch a Lottie animation into remotion/public/lottie/ for the LottieFx composition.

  uv run python -m mce.lottie <url> <name>     → remotion/public/lottie/<name>.json  (prints the src to use)
  uv run python -m mce.lottie --list            what's already there

<url>: a LottieFiles asset (.json, or .lottie — the zipped dotLottie format; the first animation inside is used)
or any direct Lottie JSON link. Animated emoji need no download: LottieFx takes `"emoji": "😂"` (Noto, CC BY 4.0).
Check the licence on the animation's page (LottieFiles free animations: Lottie Simple License).
"""
import io
import json
import sys
import urllib.request
import zipfile

from .config import MCE_HOME

LIB = MCE_HOME / "remotion" / "public" / "lottie"


def fetch(url: str, name: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=30).read()
    if raw[:2] == b"PK":  # dotLottie zip
        z = zipfile.ZipFile(io.BytesIO(raw))
        inner = sorted(n for n in z.namelist() if n.startswith("animations/") and n.endswith(".json"))
        if not inner:
            raise SystemExit("no animation inside this .lottie file")
        raw = z.read(inner[0])
    data = json.loads(raw)
    if not {"v", "layers"} <= data.keys():
        raise SystemExit("not a Lottie animation (missing v/layers)")
    LIB.mkdir(parents=True, exist_ok=True)
    (LIB / f"{name}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    secs = (data.get("op", 0) - data.get("ip", 0)) / (data.get("fr") or 30)
    print(f"{data.get('w')}x{data.get('h')}, {secs:.2f}s @ {data.get('fr')} fps")
    return f"lottie/{name}.json"


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "--list":
        for p in sorted(LIB.glob("*.json")):
            print(f"lottie/{p.name}")
        return
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    print(json.dumps({"src": fetch(sys.argv[1], sys.argv[2])}))


if __name__ == "__main__":
    main()

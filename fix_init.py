"""Fix all __init__.py files that have null bytes (UTF-16 from Windows echo)."""
import pathlib

root = pathlib.Path(__file__).resolve().parent

init_dirs = [
    "src/skyguard/config",
    "src/skyguard/data",
    "src/skyguard/preprocessing",
    "src/skyguard/features",
    "src/skyguard/models",
    "src/skyguard/models/expected",
    "src/skyguard/models/anomaly",
    "src/skyguard/models/decision",
    "src/skyguard/models/faults",
    "src/skyguard/models/health",
    "src/skyguard/evaluation",
    "src/skyguard/explainability",
    "src/skyguard/inference",
    "src/skyguard/pipeline",
    "tests",
    "api",
    "api/routes",
]

for d in init_dirs:
    p = root / d / "__init__.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("")
    raw = p.read_bytes()
    status = "OK" if b"\x00" not in raw else "STILL HAS NULLS"
    print(f"{status}: {p.relative_to(root)}")

print("Done.")

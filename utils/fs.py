import tomllib as toml
from pathlib import Path

def get_configs(): 
  configs: dict[str, dict] = {}
  constants_dir = Path("constants")

  for fname in ("roles.toml", "tickers.toml"):
      p = constants_dir / fname
      try:
          with p.open("rb") as f:
              configs[fname] = toml.load(f)
      except FileNotFoundError:
          print(f"warning: {p} not found")
      except Exception as e:
          print(f"error loading {p}: {e}")

  for p in constants_dir.glob("*.toml"):
      if p.name in configs:
          continue
      try:
          with p.open("rb") as f:
              configs[p.name] = toml.load(f)
      except Exception:
          pass

  return configs

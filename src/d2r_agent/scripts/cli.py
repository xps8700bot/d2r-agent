from __future__ import annotations

# 允许 python -m d2r_agent.scripts.cli 使用
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[3] / "scripts" / "cli.py"), run_name="__main__")

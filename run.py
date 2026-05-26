"""项目入口脚本：python run.py <cmd>。"""
import sys
from pathlib import Path

# 将 src 加入 PYTHONPATH，便于直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from detail2md.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

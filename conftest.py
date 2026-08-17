"""测试路径引导：使 src/ 布局下的 vinf_agent 可直接导入."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
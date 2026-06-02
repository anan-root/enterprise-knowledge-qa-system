# backend/run_api.py
import os
import sys
import uvicorn

# 获取 backend 目录的绝对路径
BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
# 【关键】获取 backend 的父目录（即 code 目录）
ROOT_DIR = os.path.dirname(BACKEND_DIR)

# 将 code 目录加入 PYTHONPATH，确保子进程能找到 backend 包
os.environ["PYTHONPATH"] = ROOT_DIR

# 同时将 code 目录加入当前进程的 sys.path（当前进程导入也需要）
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if __name__ == "__main__":
    uvicorn.run(
        "backend.qa_engine.main_api_with_memory:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[BACKEND_DIR],
        log_level="info"
    )
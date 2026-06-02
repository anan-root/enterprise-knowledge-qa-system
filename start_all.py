import subprocess
import sys
import os

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def run_frontend():
    """启动前端"""
    frontend_dir = os.path.join(BASE_DIR, "frontend1")  # 根据你的前端目录调整
    return subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        shell=True  # Windows 需要
    )


def run_backend():
    """启动后端"""
    backend_dir = os.path.join(BASE_DIR, "backend")
    return subprocess.Popen(
        [sys.executable, "run_api.py"],
        cwd=backend_dir
    )


if __name__ == "__main__":
    print("🚀 启动后端服务...")
    backend_proc = run_backend()

    print("🚀 启动前端服务...")
    frontend_proc = run_frontend()

    print("\n✅ 服务已启动！按 Ctrl+C 停止所有服务\n")

    try:
        # 等待任一进程结束
        while backend_proc.poll() is None and frontend_proc.poll() is None:
            import time

            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        print("✅ 服务已停止")


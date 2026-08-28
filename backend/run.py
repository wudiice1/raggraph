"""启动入口：python run.py 即可运行（PRD 零配置部署要求）。

注意：后台解析线程模型仅支持单进程单 worker 部署（毕设规模），
请勿使用 `uvicorn --workers N`（N>1）或 gunicorn 多进程部署。
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)

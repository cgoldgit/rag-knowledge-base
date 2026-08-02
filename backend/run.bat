@echo off
rem 一键启动后端（RAG 知识库问答系统）
rem 使用 conda 环境 rag-kb 启动
cd /d %~dp0
echo 正在启动后端服务... 访问 http://localhost:8000
call conda activate rag-kb
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

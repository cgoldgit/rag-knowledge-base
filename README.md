# 📚 RAG 企业级知识库问答系统

> 基于 **LangChain** 的检索增强生成（RAG）企业级知识库问答系统，面向电商平台商品问答场景。
> 用户可以在浏览器中管理知识库、与 AI 进行基于知识库内容的智能问答。

## ✨ 功能特性

### 🎯 核心功能

- **知识库问答**：提问后系统先检索知识库，再由大模型基于检索内容生成回答，**回答可追溯、不编造**
- **引用来源展示**：回答底部展示引用的知识库片段，点击可展开查看原文
- **知识库管理**（管理员）：上传文档（PDF / Word / TXT / Markdown / Excel）、自动解析分块向量化、文档列表、删除、统计看板
- **多用户多会话**：每个用户拥有独立会话，互不干扰；支持重命名、清空、删除
- **会话历史持久化**：所有问答记录存入数据库，任何时间登录都能找回历史对话
- **用户系统**：注册、登录、修改密码、个性化设置，JWT 令牌认证

### 🚀 企业级特性

- **混合检索**：向量检索 + 关键词检索（jieba 分词）双路合并，取长补短不漏检
- **重排序（Rerank）**：BGE-reranker 模型对候选片段精排，提高回答准确率
- **流式输出**：回答逐字返回（打字机效果），降低等待感
- **多轮对话理解**：自动结合上下文理解追问（如"那充电呢？"）
- **检索兜底**：知识库无相关信息时明确告知，绝不编造
- **Redis 问答缓存**：热门问题 5 分钟内秒回，不重复调用大模型
- **接口限流**：Redis 原子计数防刷（每用户每分钟 10 次）
- **回答评价**：点赞/点踩，可统计回答质量
- **自动重试**：向量化调用失败自动重试（指数退避）
- **故障降级**：向量服务异常时自动降级为关键词检索，不中断服务
- **权限控制**：知识库管理仅管理员可用
- **密码加密存储**：bcrypt 加密，杜绝明文
- **流中断保护**：流式回答中断时自动保存已生成内容，不丢数据

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────┐
│                    浏览器（用户界面）                   │
│            Vue 3 + Element Plus（前端）               │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP / SSE 流式
┌──────────────────────▼──────────────────────────────┐
│              FastAPI 后端（Python）                   │
│         LangChain RAG 流程 + 业务逻辑                 │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
   ▼          ▼          ▼          ▼
 MySQL      Redis     Chroma     DeepSeek + 硅基流动
 主数据库    缓存      向量库      大模型 + 向量模型
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | **FastAPI** | 高性能异步 Web 框架 |
| AI 框架 | **LangChain** | RAG 流程编排 |
| 前端 | **Vue 3 + Element Plus** | 响应式界面 |
| 主数据库 | **MySQL 8.4** | 用户/会话/消息/文档元数据 |
| 向量数据库 | **Chroma** | 文档片段向量存储与检索 |
| 缓存 | **Redis** | 登录凭证、热门问答缓存、限流 |
| 对话模型 | **DeepSeek** | 回答生成 |
| 向量模型 | **BGE-M3**（硅基流动） | 文本向量化 |
| 重排序模型 | **BGE-reranker**（硅基流动） | 检索结果精排（规划） |
| 认证 | **JWT + bcrypt** | 令牌认证 + 密码加密 |

### RAG 核心流程

```
用户提问
  ↓
问题向量化（BGE-M3 转数字指纹）
  ↓
Chroma 向量库检索最相似片段（Top-K）
  ↓
片段 + 对话历史 + 问题 组装提示词
  ↓
DeepSeek 大模型生成回答（仅依据知识库）
  ↓
回答 + 引用来源 流式返回前端
```

## 🚀 快速启动

### 环境要求

- Python 3.12+
- Node.js 18+
- MySQL 8.4
- Redis
- conda（推荐）

### 1. 配置密钥

在项目根目录创建 `.env` 文件（**切勿提交到 Git**）：

```env
# DeepSeek 大模型
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro

# 硅基流动（向量化 + 重排序）
SILICONFLOW_API_KEY=你的硅基流动密钥
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Pro/BAAI/bge-m3
RERANK_MODEL=BAAI/bge-reranker-v2-m3
```

### 2. 启动后端

```bash
cd backend
conda create -n rag-kb python=3.12 -y
conda activate rag-kb
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 访问系统

浏览器打开 http://localhost:5173

**管理员账号**：admin / 123456（首次启动自动创建）

## 📖 使用说明

### 管理员
1. 登录后进入「知识库管理」上传商品文档（支持 PDF/Word/TXT/Markdown/Excel）
2. 文档上传后自动解析、分块、向量化，状态变为「已就绪」
3. 进入「知识库问答」与 AI 对话，提问基于知识库内容

### 普通用户
1. 注册账号并登录
2. 新建会话，开始提问
3. 回答底部可展开查看引用来源

## 📁 项目结构

```
langchain-RAG/
├── backend/                 # 后端（FastAPI）
│   ├── app/
│   │   ├── main.py          # 应用入口
│   │   ├── config.py        # 配置（.env）
│   │   ├── database.py      # MySQL 连接
│   │   ├── models/          # 数据模型（用户/会话/消息/文档）
│   │   ├── routers/         # 接口路由（认证/会话/知识库/问答）
│   │   ├── schemas/         # 数据格式
│   │   ├── services/        # 业务逻辑（RAG/文档解析/向量化）
│   │   ├── security.py      # 认证安全（JWT/bcrypt）
│   │   └── deps.py          # 权限依赖
│   └── requirements.txt     # Python 依赖
└── frontend/                # 前端（Vue 3）
    └── src/
        ├── views/           # 页面（登录/问答/知识库管理/修改密码）
        ├── api/             # 接口调用
        ├── router/          # 路由
        └── store/           # 状态管理
```

## 🔒 安全说明

- API 密钥仅存于 `.env`（已被 .gitignore 排除）
- 密码使用 bcrypt 加密存储
- 接口使用 JWT 令牌认证，权限分级控制
- 数据库使用专用账号（仅项目数据库权限）

## 📊 版本记录

| 版本 | 说明 |
|------|------|
| v1.1 | 性能优化（混合检索/重排序/缓存/限流）+ 新功能（设置页/会话操作/回答评价/统计看板）+ 代码审查修复 |
| v1.0 | 首个完整版本：注册登录、多会话、知识库管理、RAG 问答、流式输出 |

## 📝 致谢

- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://github.com/fastapi/fastapi)
- [Vue 3](https://github.com/vuejs/core)
- [DeepSeek](https://www.deepseek.com/)
- [硅基流动](https://siliconflow.cn/)

## 📄 License

本项目仅用于学习交流（毕业设计）。

# New Media Growth Agent MVP｜新媒体内容增长 Agent MVP

一个可直接上传 GitHub 的「内容增长 Agent」最小可运行版本。它把热点发现、竞品拆解、选题评分、脚本生成、发布计划和复盘沉淀串成一条自动化内容工作流。

> 设计目标：让非技术团队也能本地跑起来；没有 LLM API Key 时使用规则引擎兜底，有 OpenAI API Key 时自动增强生成质量。

## 功能

- 热点/主题采集：支持手动关键词、RSS 源、内置样例数据
- 多 Agent 协作：Trend Agent、Competitor Agent、Scoring Agent、Script Agent、Calendar Agent、Learning Agent
- 自动产出：爆款选题、评分理由、短视频脚本、标题、封面文案、标签、CTA、发布计划
- SQLite 持久化：保存每次生成结果和复盘数据
- Web 控制台：浏览器直接使用
- API：可被其他系统调用
- CSV 导出：可导出选题表用于团队协作
- CLI：命令行一键生成内容方案

## 快速开始

### 1. 克隆或解压项目

```bash
cd content-growth-agent-mvp
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# Windows: .venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

没有 OpenAI Key 也能跑，系统会使用本地规则引擎。若要开启 LLM 增强，在 `.env` 中填写：

```env
OPENAI_API_KEY=你的key
OPENAI_MODEL=gpt-4o-mini
```

### 5. 启动 Web 服务

```bash
uvicorn app.main:app --reload
```

打开：

```text
http://127.0.0.1:8000
```

## 命令行使用

```bash
python -m app.cli \
  --brand "城市家电卖场" \
  --audience "准备装修、换家电、追求性价比的家庭用户" \
  --platform "抖音" \
  --keywords "空调,冰箱,洗衣机,装修避坑" \
  --count 5
```

## API 示例

```bash
curl -X POST http://127.0.0.1:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "brand_name": "城市家电卖场",
    "brand_positioning": "本地一站式家电采购顾问",
    "audience": "准备装修、换家电、追求性价比的家庭用户",
    "platform": "抖音",
    "goal": "提升同城客户咨询量",
    "keywords": ["空调", "冰箱", "洗衣机", "装修避坑"],
    "competitor_notes": ["同城账号常用门店探访和价格对比", "用户最关心售后、安装和真实价格"],
    "content_count": 5
  }'
```

## 项目结构

```text
content-growth-agent-mvp/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── cli.py               # 命令行入口
│   ├── core/
│   │   ├── agents.py        # 多 Agent 编排和业务逻辑
│   │   ├── config.py        # 配置
│   │   ├── database.py      # SQLite 存储
│   │   ├── llm.py           # LLM 适配层，支持无 Key 兜底
│   │   ├── schemas.py       # Pydantic 数据结构
│   │   └── seed.py          # 内置热点和选题素材
│   └── static/
│       ├── index.html       # Web 页面
│       ├── app.js           # 前端交互
│       └── style.css        # 样式
├── data/
│   └── .gitkeep             # SQLite 数据默认存放目录
├── tests/
│   └── test_agents.py       # 简单测试
├── .env.example
├── .gitignore
├── Dockerfile
├── LICENSE
├── pyproject.toml
└── requirements.txt
```

## Agent 流程

1. **Trend Agent**：根据关键词、RSS、内置热点库生成候选话题。
2. **Competitor Agent**：从竞品笔记中提取常见钩子、用户痛点和内容角度。
3. **Scoring Agent**：按受众匹配、传播潜力、转化价值、差异化程度、制作难度打分。
4. **Script Agent**：生成短视频脚本、标题、封面文案、标签和 CTA。
5. **Calendar Agent**：根据平台和优先级给出发布节奏。
6. **Learning Agent**：结合历史反馈沉淀可复用模板。

## 复盘接口

提交内容表现数据：

```bash
curl -X POST http://127.0.0.1:8000/api/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "run_id": 1,
    "idea_id": "idea_001",
    "views": 12000,
    "likes": 420,
    "comments": 60,
    "shares": 35,
    "leads": 18,
    "notes": "标题里的避坑词带来了较高点击"
  }'
```

## Docker 运行

```bash
docker build -t content-growth-agent .
docker run -p 8000:8000 --env-file .env content-growth-agent
```

## 后续可扩展方向

- 接入抖音、小红书、B 站等公开趋势源
- 接入企业内部知识库和产品库
- 增加自动封面图生成
- 增加发布排期和飞书/企微通知
- 增加基于真实播放数据的选题评分模型

## 免责声明

该项目是 MVP，用于展示 AI Agent 工作流和内部效率提升。平台数据抓取请遵守对应平台服务条款和法律法规。

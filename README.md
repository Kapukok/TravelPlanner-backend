# TravelPlanner

TravelPlanner 是一个用于旅行规划的 Python 项目，包含意图解析、资源搜索、行程规划和文案生成等模块。

## 目录结构
```
TravelPlanner/
├── app/
│   ├── api/
│   │   ├── routes.py          # 前端接口 (对应 main.py 的路由部分)目前还没接入前端所以无效
│   ├── core/
│   │   ├── orchestrator.py   
│   ├── models/
│   │   ├── internal.py        
│   ├── components/            
│   │   ├── client.py          # LLM接口的父类
│   │   ├── parser.py          # 步骤1: 意图解析 (LLM)
│   │   ├── searcher.py        # 步骤2: 资源搜索 (API Tools)
│   │   ├── planner.py         # 步骤3: 核心规划 (Python算法)
│   │   └── writer.py          # 步骤4: 文案生成 (LLM)
│   └── tools/
│       ├── amap_client.py     # 高德地图 API 的底层封装
│       ├── info.py            # Tavily 接口补充景点信息
│       ├── parseInfo.py       # 把字符串时间文本转化为 JSON 格式
├── main.py                    # 启动入口
└── .env                       # API Key 配置
```

## 备注：tmp.py 是一个对比文件
**探究在仅使用同样的 Qwen 大模型的情况下返回的旅行规划是否合理，在 exp 文件夹中是我们获得的答案，发现如果仅使用 LLM 生成，很多地点都是虚假信息。而我们项目获得答案（runningData中），准确度较高，可信度高**

## 目前后端大致完成，可以通过 orchestrator.py 来运行后端代码


## 现在如何把骨架跑起来 (前端未完成，目前只有演示效果)

**第一步：配置环境**

注意.env文件和main文件放在一层，共有五条主要信息。
```
AMAP_API_KEY=
LLM_API_KEY=
TAV_API_KEY=
BASE_URL=
MODEL=
```

**第二步：运行 orchestrator.py**



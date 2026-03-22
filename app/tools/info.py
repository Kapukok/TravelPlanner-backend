import asyncio
import json
import os
import re

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI

from app.models.internal import POI

load_dotenv()

async def web(ques:str):
    api=os.getenv("TAV_API_KEY")
    if not api:
        print("info: API Wrong")
        return None
    url="https://api.tavily.com/search"

    payload={
        "api_key":api,
        "query":ques,
        "search_depth":"advanced",
        "include_answer": True,
        "max_results": 5
    }

    #print("send request ...")

    async with (httpx.AsyncClient(timeout=30.0) as client):
        response = await client.post(url, json=payload)
        if response.status_code == 200:
            data=response.json()
            #print("successful")
            import json

            #print(json.dumps(data,indent=4,ensure_ascii=False))

            summary=data.get("answer",[])
            if not summary:
                results = data.get("results", [])
                if results:
                    summary = results[0].get("content")
            return summary
        else:
              print(f"info: request fail:{response.status_code}-{response.text}")
        return None

client = AsyncOpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"), # ModelScope Token
)

extra_body = {
    "enable_thinking": True,
}

async def filterAttraction(days:int,att:list[POI])-> list[POI] | None:
    system_prompt ="""
你是一个专业的旅游规划与数据清洗专家。你的任务是处理一份候选景点列表(POIs)，根据景点的“优先级(priority)”和其他属性筛选出最终建议的景点列表。

### 输入数据说明
你将收到一个 JSON 格式的景点列表，每个景点包含：
- `name`: 景点名称
- `priority`: 优先级 (3=用户指定/精确搜索，2=模糊搜索结果，1=热门推荐/填充)
- `rating`: 评分
- `id`, `location` 等其他字段

### 筛选与清洗规则 (必须严格遵守)
1. **硬性保留原则 (Priority 3)**: 
   - 所有 `priority=3` 的景点代表用户明确指定或精确匹配的地点，**必须全部保留**，不可删除，不可替换。
  
2. **数量与质量控制**:
   - 目标是为 {days} 天的行程筛选景点。建议通过筛选保留约 {target_count} 个景点（建议每天安排 3-4 个）。
   - 在保留所有 priority=3 的基础上，优先从 priority=2 (模糊搜索) 中选择高评分(rating)的景点。
   - 只有当 total count 不足时，才从 priority=1 (热门推荐) 中补充高分景点。
   - 剔除评分过低(rating < 3.0) 且非 priority=3 的劣质景点。
   - 在同等条件（priority相同，评分相近）下，保留更有名的景点，删除不太知名的小景点

### 输出格式要求
- 必须直接返回一个标准的 **JSON 列表** (`[]`)。
- 列表中的元素必须是**原始输入的 POI 对象**，保持字段完全不变。
- 不要输出任何思考过程、Markdown 标记或额外的文字，只输出 JSON。
"""

    pois_data = [poi.model_dump() for poi in att]
    count = days * 3
    user_prompt=f"""
请处理以下景点列表：
{json.dumps(pois_data, ensure_ascii=False)}

行程天数：{days} 天
建议保留数量：约 {count} 个


请严格执行筛选，确保 Priority=3 的景点全部在结果中。
只返回筛选后的 JSON 列表。
"""

    load_dotenv()
    response = await client.chat.completions.create(
        model=os.getenv("MODEL"),
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        stream=True,
        extra_body={
            "enable_thinking":True
        }
    )
    done_thinking = False
    ans=""
    async for chunk in response:
       if chunk.choices:
          answer_chunk = chunk.choices[0].delta.content
          if answer_chunk != '':
              if not done_thinking:
                  #print('\n\n === Final Answer ===\n')
                  done_thinking = True
              #print(answer_chunk, end='', flush=True)
              ans+=answer_chunk
    try:
        if "```json" in ans:
            text=re.search(r"```json\s*(.*?)\s*```",ans,re.DOTALL).group(1)
        elif "```" in ans:
            text=re.search(r"```\s*(.*?)\s*```",ans,re.DOTALL).group(1)
        else:
            text=ans
        t=json.loads(text)
    except Exception as e:
        print(f"info: JSON Parse Error in filterAttraction: {e}\nContent: {text}")
        return None
    #print(f"{t}")
    return [POI.model_validate(x) for x in t]

async def if_include(att1:str,att2:str)->int:
    response=await web(f"{att1}是否是{att2}的一部分，{att2}是否是{att1}的一部分")
    #print(f"\n{response}")
    system_prompt = """你是一个专业的旅游数据清洗专家。你的任务是根据信息判断两个旅游景点（A 和 B）的语义关系，并决定由于“距离过近”或“包含关系”或“名称重复”是否需要删除其中一个。

请遵循以下判断逻辑，仅返回一个数字（0, 1, 或 2）：

- 返回 1 (删除 A)：
  1. 如果 A 是“大景区”中(within/in)的子景点，且 B 是“大景区”本身（保留 B 以涵盖区域）。
  2. 如果 B 包围或包含 A。
  3. 如果 A 和 B 指同一个地方，但 B 的名称更正式、信息更全或更适合作为行程节点。（返回 1）

- 返回 2 (删除 B)：
  1. 如果 B 是“大景区”中(within/in)的子景点，且 A 是“大景区”本身（保留 A 以涵盖区域）。
  2. 如果 A 包围或包含 B。
  3. 如果 A 和 B 指同一个地方，但 A 的名称更正式、信息更全或更适合作为行程节点。
  4. 你的任务是删除多余的。如果两处完全相同，请删除后者（返回 2）。

- 返回 0 (两个都保留)：
  1. A 和 B 虽然距离近，但是两个独立的景点，门票独立或体验互不干扰（例如“大雁塔”和“大唐芙蓉园”）。
  2. 无法确定它们有包含关系，或者它们就是互不隶属的邻近景点。
  
-**总体要求**：如果一个景点在另一个景点里面，则删除子景点，保留主要更有名的景点。

请只输出数字，不要输出任何解释。"""

    user_prompt=f"""
    景点A：{att1}
    景点B：{att2}
    提供信息：{response}

    请判读（仅返回 0, 1, 或 2）："""

    load_dotenv()
    response = await client.chat.completions.create(
        model=os.getenv("MODEL"),
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        stream=True,
        extra_body={
            "enable_thinking":True
        }
    )
    done_thinking = False
    ans=""
    async for chunk in response:
       if chunk.choices:
          answer_chunk = chunk.choices[0].delta.content
          if answer_chunk != '':
              if not done_thinking:
                  #print('\n\n === Final Answer ===\n')
                  done_thinking = True
              #print(answer_chunk, end='', flush=True)
              ans+=answer_chunk
    #print(f"{int(ans)}")
    return int(ans)

async def chat(ques:str):
    query=f"{ques} 2026年最新 建议游玩时长 推荐参观时长 门票价格"
    ans=await web(query)
    #print("\n")
    #print(f"{ans}")
    if not ans:
        return None
    #print("send request ...")
    system_prompt = """
你是一个专业的旅游数据结构化专家。你的任务是从搜索文本中提取关键的旅行规划数据。

请严格遵守以下提取规则：
1. 【建议游玩时长/游玩时间(duration)】：必须转换为**分钟数(int)**。如"2-3小时"取150。
2. 【门票价格】：寻找成人票价格，如果有淡季和旺季之分，甚至还有优惠票等票价不一致情况，一律按照票价最高的情况计算保留。

【兜底规则】：
- 如果建议游玩时长找不到，请该字段返回120
- 如果门票价格找不到，请该字段返回0
- 必须直接返回纯净的 JSON 格式。
"""

    user_prompt = f"""
        请根据以下搜索结果，提取【{ques}】的建议游玩时长，门票价格：

        ---搜索结果开始---
        {ans}
        ---搜索结果结束---

        返回格式示例：
        {{"duration": 180, "cost":50}}
        """
    load_dotenv()
    ans = ""
    for i in range(5):
        try:
            response = await client.chat.completions.create(
                model=os.getenv("MODEL"),
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                stream=True,
                extra_body={
                    "enable_thinking": True
                }
            )
            done_thinking = False
            async for chunk in response:
                if chunk.choices:
                    answer_chunk = chunk.choices[0].delta.content
                    if answer_chunk != '':
                        if not done_thinking:
                            # print('\n\n === Final Answer ===\n')
                            done_thinking = True
                        # print(answer_chunk, end='', flush=True)
                        ans += answer_chunk
            if ans:
                break
        except Exception as e:
            if i<5:
                await asyncio.sleep(1+i*0.5)

    text=""
    t={}
    try:
        if "```json" in ans:
            text=re.search(r"```json\s*(.*?)\s*```",ans,re.DOTALL).group(1)
        elif "```" in ans:
            text=re.search(r"```\s*(.*?)\s*```",ans,re.DOTALL).group(1)
        else:
            text=ans
        t=json.loads(text)
    except Exception as e:
        print(f"info: JSON Parse Error in chat: {e}\nContent: {text}")
        return None
    # if "open_time" in t:
    #     n=await parseIn(t["open_time"],ques)
    #     if not n:
    #         return t
    #     t.pop("open_time",None)  #"openTime": 510, "closeTime": 1020, "closeday": [1]
    #     t["openTime"]=n["openTime"]
    #     t["closeTime"] = n["closeTime"]
    #     t["closeday"] = n["closeday"]
    #print("\n")
    #print(f"{t}")
    return t

if __name__ == "__main__":
    asyncio.run(if_include("断桥","西湖"))

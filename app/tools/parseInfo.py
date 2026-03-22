import asyncio
import os
import re
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
load_dotenv()

client = AsyncOpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("LLM_API_KEY"), # ModelScope Token
)

extra_body = {
    "enable_thinking": True,
}

async def parseIn(amap_text_data: str, poi_name: str):
    #print("send request ...")
    system_prompt = """
        你是一个时间数据标准化助手。请将非结构化的开放时间文本转换为标准 JSON。

        【处理规则】
        1. openTime/closeTime: 提取所有开放日中**最保守**的时间范围（即涵盖时间最短的交集）。**注意**：必须把openTime和closeTime的时间转化为分钟，格式："openTime": 510, "closeTime": 1020。如果没有openTime，默认为480。如果没有closeTime，默认为1320。
        2. closeday: 提取闭馆的星期数，用列表表示 [1,2...]。1代表周一，7代表周日。如果没有闭馆日，返回 []。

        【示例】
        输入: "周一闭馆，周二至周日 8:30-17:00"
        输出: {"openTime": 510, "closeTime": 1020, "closeday": [1]}
        
        【特殊规则】
        1. 遇到 "全天开放"、"24小时"、"随时" 或无明确围墙的景点（如步行街、广场、海滩）：
       - 返回 "openTime": 0, "closeTime": 1439
        【输出示例】
    输入："南京路步行街全天开放"
    输出：{"openTime": 0, "closeTime": 1439, "closeday": []}
        """
    load_dotenv()
    user_prompt = f"请清洗【{poi_name}】的数据：{amap_text_data}"
    response = await client.chat.completions.create(
        model=os.getenv("MODEL"),
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        stream=True,
        extra_body=extra_body
    )

    full_content = ""
    done_thinking = False
    async for chunk in response:
       if chunk.choices:
          answer_chunk = chunk.choices[0].delta.content
          if answer_chunk:
              if not done_thinking:
                  #print('\n\n === Final Answer ===\n')
                  done_thinking = True
              #print(answer_chunk, end='', flush=True)
              full_content += answer_chunk

    # Cleaning and parsing JSON
    try:
        # Remove code block formatting if present
        if "```json" in full_content:
            text = re.search(r"```json\s*(.*?)\s*```", full_content, re.DOTALL).group(1)
        elif "```" in full_content:
            text = re.search(r"```\s*(.*?)\s*```", full_content, re.DOTALL).group(1)
        else:
            text = full_content

        # Parse JSON
        return json.loads(text)
    except Exception as e:
        print(f"\nJSON Parse Error: {e}")
        return full_content
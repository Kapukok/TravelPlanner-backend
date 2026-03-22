import asyncio
import os
import re
import json
from dotenv import load_dotenv
from os import getenv
from openai import AsyncOpenAI


class Parser:

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=getenv("LLM_API_KEY"),
            base_url=getenv("BASE_URL")
        )
        self.system_prompt ="""
你是一个资深的智能旅行助手。你的任务是分析用户的自然语言要求，并将其“翻译”为标准化的 JSON 格式，以便下游的地图 API 进行精准搜索。

用户将会以自然语言给出一系列要求，而你的输出必须严格遵守以下格式：
{
  "requirements": {
    "KEYWORD": {"type": "TYPE", "is_constraint": 0/1, "is_keyword": 0/1, "is_specific": 0/1}
  }
}

【字段说明】
1. KEYWORD: 最能概括用户请求的**标准搜索词**。
2. TYPE: "attraction"(景点/体验项目)、"food"(食物)、"hotel"(住宿)、"transport"(纯代步交通)、"general"(纯抽象体验要求)。
3. is_constraint: 1(硬性要求，必须满足)；0(软偏好，尽量满足)。
4. is_keyword: 1(正向搜索词)；0(负向排除词，如不要山)。
5. is_specific: 1(具体地点，如"故宫")；0(泛指类别，如"博物馆"、"星级酒店"、"游船")。

【核心翻译与分类规则】（必须严格遵守）
1. **口语化标准转换 (Normalization)**：必须将用户的口语表达转化为高德地图易于识别的**标准行业词汇**，是能搜索出明确地点的提示词。
   - 例1："住好一点的酒店" -> KEYWORD 必须是 "星级酒店" 或 "高档型酒店" (type: hotel)。
   - 例2："随便吃点" -> KEYWORD 必须是 "快餐" 或 "小吃" (type: food)。
   - 例3："看看动物" -> KEYWORD 必须是 "动物园" (type: attraction)。
   **注意**，如果是模糊地点，请在 keyword 字段将其转化为最可能的高德搜索词（例如：用户说：“我想去看看那个人民币背面的风景”，转化为‘桂林山水’或者‘漓江’ 或 ‘人民大会堂’），并且需要区分is_specific。
   
2. **游玩主题与特色体验归类 (Theme & Experience Mapping)**：
   - **文化/风景**：表达对某种文化、风景的偏好时，必须转化为泛指类的 **attraction**。
     - "了解历史文化" -> KEYWORD: "历史古迹" 或 "博物馆" (type: attraction, is_specific: 0)。
   - **特色体验 vs 代步交通**：带有游玩属性的特色交通（如"竹筏"、"游船"、"游艇"、"索道"、"缆车"、"观光巴士"）**必须**归为 **attraction** 并且 is_specific 为 0。只有纯粹的跨城或市内代步工具（如"高铁"、"地铁"、"公交"、"打车"、"飞机"）才能归为 **transport**。

3. **General 类型的严格边界**：只有完全无法映射到物理实体的**纯抽象体验**（行程节奏、体力消耗、同行人员等），才能归入 general。
   - 允许的 general： "轻松", "不累", "行程紧凑", "带老人", "适合小孩", "风景优美"。

4. **负面关键词裂变**：对于负面约束，提取具体且方便匹配的字符串，is_keyword设为0。
   - 例：用户说“带着老人，不要爬山，也别去寺庙”。
        "山": {"type": "attraction", "is_constraint": 1, "is_keyword": 0, "is_specific": 0},
        "峰": {"type": "attraction", "is_constraint": 1, "is_keyword": 0, "is_specific": 0},
        "寺": {"type": "attraction", "is_constraint": 1, "is_keyword": 0, "is_specific": 0}

【示例】
用户输入：“我要去颐和园和故宫。吃的方面食物种类最好丰富一点，不过我海鲜过敏，我想吃北京烤鸭。我希望住的酒店星级高一点。晕车。最好能了解北京的民俗文化。还想坐游船。”
你的输出：
{
    "requirements": {
        "颐和园": {"type":"attraction", "is_constraint": 1, "is_keyword": 1, "is_specific": 1},
        "故宫": {"type":"attraction", "is_constraint": 1, "is_keyword": 1, "is_specific": 1},
        "烤鸭": {"type":"food", "is_constraint": 1, "is_keyword": 1, "is_specific": 0},
        "海鲜": {"type":"food", "is_constraint": 1, "is_keyword": 0, "is_specific": 0},
        "星级酒店": {"type":"hotel", "is_constraint": 0, "is_keyword": 1, "is_specific": 0},
        "公交车": {"type":"transport", "is_constraint": 1, "is_keyword": 0, "is_specific": 0},
        "食物种类丰富": {"type":"general", "is_constraint": 0, "is_keyword": 0, "is_specific": 0},
        "民俗文化": {"type":"attraction", "is_constraint": 0, "is_keyword": 1, "is_specific": 0},
        "游船": {"type":"attraction", "is_constraint": 1, "is_keyword": 1, "is_specific": 0}
    }
}

不要在输出中包括除了JSON以外的任何内容。

请开始吧！
"""

    async def generate(self, prompt: str) -> dict:
        response = await self.client.chat.completions.create(
            model=os.getenv("MODEL"),
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            stream=True,
        )
        content = ""
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
        if "```json" in content:
            content = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL).group(1)
        elif "```" in content:
            content = re.search(r"```\s*(.*?)\s*```", content, re.DOTALL).group(1)
        #print(f"{json.loads(content)}")
        return json.loads(content)


load_dotenv()

parser = Parser()

if __name__ == "__main__":
        user_in = input("请输入您的需求 (输入 q 退出)：")
        print("正在解析...")
        result = asyncio.run(parser.generate(user_in))
        print(json.dumps(result, indent=2, ensure_ascii=False))
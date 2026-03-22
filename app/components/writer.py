import asyncio
import os
import re
import json
from dotenv import load_dotenv
from os import getenv
from openai import AsyncOpenAI
from typing import List
from app.models.internal import DayItinerary, POI


class Writer:

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=getenv("LLM_API_KEY"),
            base_url=getenv("BASE_URL")
        )

    def _format_minutes(self, minutes: int) -> str:
        h = minutes // 60
        m = minutes % 60
        return f"{h:02d}:{m:02d}"

    def _format_poi(self, poi: POI) -> str:
        open_str = self._format_minutes(poi.openTime)
        close_str = self._format_minutes(poi.closeTime)
        level_str = f"{poi.level}A级景区" if poi.level > 0 else ""
        return (
            f"- **{poi.name}** ({' '.join(poi.type[:2])})\n"
            f"  - 评分: {poi.rating}/5.0\n"
            f"  - 建议游玩时长: {poi.duration} 分钟\n"
            f"  - 开放时间: {open_str} - {close_str}\n"
            f"  - 地址: {poi.address}\n"
            f"  {f'- 等级: {level_str}' if level_str else ''}"
        )

    async def generate_itinerary(self, plan_data: List[DayItinerary]):
        plan_context = ""
        for day in plan_data:
            plan_context += f"\n## 第 {day.day_index + 1} 天\n\n"

            plan_context += "### 推荐景点:\n"
            if day.spots:
                for spot in day.spots:
                    plan_context += self._format_poi(spot) + "\n"
            else:
                plan_context += "今日无特定景点安排。\n"

            # Restaurants
            plan_context += "\n### 餐饮推荐:\n"
            if day.restaurants:
                for rest in day.restaurants[:4]:
                    plan_context += self._format_poi(rest) + "\n"
            else:
                plan_context += "探索附近的当地美食。\n"

            # Accommodation
            plan_context += "\n### 住宿安排:\n"
            if day.hotel:
                for hotel in day.hotel[:2]:
                    plan_context += self._format_poi(hotel) + "\n"
            else:
                plan_context += "今日无特定酒店安排。\n"

            plan_context += "-" * 40 + "\n"

        system_prompt = """
你是一位专业的中国旅行规划师和资深的旅游作家。你的目标是将结构化的旅行行程数据转化为一份精美、引人入胜且实用的旅行指南，全文用中文书写。

**语气与风格：**
- 热情、鼓舞人心，同时保持专业。可以适当采用表情。
- 有效使用 Markdown 格式（标题、加粗、列表）。

**指令：**
1. **前言**：基于目的地，以一段简短而令人兴奋的概述开始这次旅行。
2. **每日指南**：为每一天编写叙述性的流程。
   - 不要仅仅列出景点；要逻辑性地连接它们（例如，“早上从……开始”，然后“前往……”），如果景点POI的description不是空语句，需要有效利用景点信息（description）介绍景点，不要犯常识性错误。
   - 利用提供的数据（开放时间、评分、地址）增加价值。提及某个地方是否评分很高或有特定等级（如 5A 级景区）。
   - 如果列出了特定餐厅，将它们融入午餐/晚餐部分。
   - **酒店**：在规划中给用户提供可选择的酒店列表即可。每天行程直接从每日第一个景点开始即可。把所有可能酒店都列出来，优先选评分高的。
   - **行程时间**：如果搜索到的信息可以推断出大致行程时间，可以给用户可以参考的行程时间。
3. **实用贴士**：添加适用于整个行程的贴士部分（例如，穿舒适的鞋子）。
4. **结语**：简短总结，祝愿他们有一段美好的旅程。

**约束条件**：严格忠实于提供的计划数据。不要捏造未列出的新景点，但你可以添加关于所列著名景点的通用描述或已知事实，使其内容更丰富。

示例：
成都是一座非常有生活气息的城市，既有大熊猫的萌趣，又有深厚的三国与历史文化底蕴。针对您的需求，我参考高德地图及其扫街榜的信息，为您规划了一份四天三晚的成都深度游方案，涵盖了您提到的所有核心体验，并为您精选了舒适的住宿和特色街区。
🏨 住宿推荐：舒适与位置兼备
成都的住宿主要集中在春熙路/太古里（繁华热闹）、天府广场/骡马市（交通便利）和锦江/合江亭（江景舒适）区域。为了满足您“住得好一点”的要求，我为您筛选了以下两家不同风格的酒店：
奢华享受：成都华尔道夫酒店
特色：位于市中心，闹中取静。拥有顶级的室内设计和高品质的服务，房间宽敞，设施豪华。
位置：锦江区红星路三段，紧邻太古里，出门即是繁华商圈。
舒适品质：成都瑞吉酒店
特色：国际高端品牌，服务细节到位，客房设计现代典雅，床品舒适。
位置：锦江区红星路三段，靠近天府广场，交通便利。
🗺️ 四天行程规划
Day 1：抵达成都，感受三国文化
上午/下午：抵达成都，办理入住。
下午：前往成都武侯祠博物馆。这里是全国唯一一座君主与臣相合祀的祠庙，也是了解三国文化最核心的地方。您可以看到刘备墓、诸葛亮殿等，感受“三分割据”的历史厚重。
“全国唯一一座将君主刘备与丞相诸葛亮同祀的祠庙，打破了传统礼制，百姓称‘武侯祠’而非‘昭烈庙’，正是对诸葛亮‘功盖三分’的至高致敬。”
晚上：前往锦城万达广场附近用餐，然后逛逛附近的铁像寺水街。这里结合了川西古建和现代元素，晚上灯光亮起后非常有氛围，适合散步消食。
“川西古建错落，小桥流水绕街，老成都的坝坝茶和网红咖啡完美相融。”
Day 2：萌宠时间，大熊猫基地
上午：前往成都大熊猫繁育研究基地。这里是全球最大的大熊猫人工繁育种群基地，可以看到不同年龄段的大熊猫，非常治愈。
下午：在基地内继续观察大熊猫，或者前往附近的天府广场逛逛，感受成都的市中心氛围。
晚上：在春熙路/太古里商圈用餐，体验成都的美食和繁华夜景。
Day 3：探寻历史，品味川菜
上午：前往金沙遗址博物馆（需提前预约，周一闭馆）。这里是古蜀文明的代表，可以看到“太阳神鸟”金饰的出土地，感受3000年前的古蜀辉煌。
下午：前往杜甫草堂。走进“诗圣”的故居，感受“茅屋为秋风所破歌”的诗意与历史。
“走进课本里的‘诗圣故居’，杜甫在此写下《春夜喜雨》《茅屋为秋风所破歌》等240余首传世诗篇，亲身感受语文课本中千年的诗意回响。”
晚上：品尝正宗川菜。推荐选择南堂小馆或观锦餐厅，这两家在交子商圈，环境和服务都很不错，能吃到地道的川菜。
Day 4：休闲购物，特色商业街
上午：睡个懒觉，然后前往成都大熊猫繁育研究基地的周边区域，或者去安仁古镇（距离市区约40分钟车程），那里有保存完好的民国建筑群，非常有特色。
下午：在市区内逛逛SKP或成都大魔方。这两个地方是成都高端商业的代表，汇集了众多国际品牌和特色餐饮，非常适合购物和休闲。
晚上：准备返程。
🍲 美食推荐：地道川菜
成都的美食遍地都是，以下是一些口碑极佳的川菜馆，您可以根据位置和喜好选择：
南堂小馆·川菜馆：主打原创川菜，口味独特，环境雅致。
观锦餐厅：大师豆瓣鱼是必点菜，鱼肉鲜嫩，非常下饭。
悦百味·品质川菜：红米肠是一大特色，口感丰富。
许家菜樽宴：环境高端，适合商务宴请或特殊庆祝。
新蓉庭·新派融合川菜：如果您担心传统川菜太辣，这家是不错的选择，口味相对温和。
烤匠麻辣烤鱼：如果想吃烤鱼，这家非常有名，鱼肉鲜嫩，汤汁浓郁。
🛍️ 特色商业街推荐
铁像寺水街：结合了川西古建和现代商业，晚上氛围最好。
SKP：高端时尚地标，汇集了众多国际品牌。
成都大魔方：位于天府大道，是集购物、餐饮、娱乐于一体的大型综合体。
新街里：美食聚集地，火锅、烤肉等应有尽有。
成都银泰城：综合性商圈，吃喝玩乐一应俱全。
"""

        response = await self.client.chat.completions.create(
            model=os.getenv("MODEL"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"这是旅行规划的原始数据：\n{plan_context}\n\n请你在保证利用这些正确数据的基础上写一份易于用户理解的旅行规划，请开始吧！"}
            ],
            stream=True,
        )
        full_content = ""
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_content += content
        print("\n")
        return full_content


load_dotenv()

writer = Writer()
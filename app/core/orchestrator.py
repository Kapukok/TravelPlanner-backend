# app/core/orchestrator.py

import asyncio
import time
from datetime import datetime

from ..components.parser import Parser
from ..components.planner import CorePlanner
from ..components.searcher import ResourceSearcher
from ..components.writer import Writer


async def generate_plan(city: str, start_date: str, end_date: str,
                        user_in: str):
  current_time = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
  # f = open(f"app/runningData/{current_time}.txt", "w", encoding="utf-8")
  # f.write(f"City: {city}\nStart Date: {start_date}\nEnd Date: {end_date}\n"
  #         f"User Input(requirements): {user_in}\n")
  print(f"[Orchestrator] 开始规划...")
  start_time = time.time()

  LLM = Parser()
  ans = await LLM.generate(user_in)
  day = (datetime.strptime(end_date, "%Y-%m-%d").date()
         - datetime.strptime(start_date, "%Y-%m-%d").date()).days + 1
  print(f"city:{city}\nstart_date:{start_date}\ndays:{day}\nreq:{user_in}")
  require = ans.get("requirements")
  keywords = []
  attractions = []
  forbid = []
  if require:
    for key, value in require.items():
      if value.get("type") != "attraction": continue
      if value.get("is_keyword") == 1:
        if value.get("is_specific") == 1:
          attractions.append(key)
        else:
          keywords.append(key)
      else:
        forbid.append(key)
  search = ResourceSearcher(day)
  res = await search.search_attractions(city, keywords, attractions, forbid)
  # f.write("\n\n\n-----------------------------------------------------------------------------------------------\n\n\n")
  # f.write(f"Attractions by search:\n{chr(10).join([f'  {repr(a)}' for a in res])}\n")
  centerPosX = 0
  centerPosY = 0
  for attraction in res:
    centerPosX += attraction.location[0]
    centerPosY += attraction.location[1]
  if len(res) > 0:
    centerPosY /= len(res)
    centerPosX /= len(res)
  else:
    print("ERROR orchestrator:the num of attraction is zero")
    return
  # 以下是餐馆和酒店模块初始信息收集
  rest = []
  hotel = []
  gen = []
  if require:
    for key, value in require.items():
      if value.get("type") == "food":
        rest.append(key)
      elif value.get("type") == "hotel":
        hotel.append(key)
      elif value.get("type") == "general":
        gen.append(key)
  plan = CorePlanner(40, 15, True, False, 540, 1)
  hotels = await search.search_hotels(city, hotel, (centerPosX, centerPosY))
  temp = await plan.plan_logistics(day, res, hotels)
  final_plan = []
  for t in temp:
    t[0].restaurants += await search.search_restaurants(rest, t[1])
    t[0].restaurants += await search.search_restaurants(rest, t[2])
    final_plan.append(t[0])
  # f.write("\n\n\n-----------------------------------------------------------------------------------------------\n\n\n")
  # f.write(f"Final Plan by planner:\n{chr(10).join([f'  {repr(d)}' for d in final_plan])}\n")
  writer = Writer()
  finalContent = await writer.generate_itinerary(final_plan)
  # f.write("\n\n\n-----------------------------------------------------------------------------------------------\n\n\n")
  # f.write(f"Final Content by writer: {finalContent}\n")
  end_time = time.time()
  print(f"\nTotal Time: {(end_time - start_time) / 60:.2f} min")
  # f.write(f"\n\n\nTotal Time: {(end_time-start_time)/60:.2f} min\n")
  # f.close()
  return finalContent
  # return user_in


if __name__ == "__main__":
  dest = input("请输入你的旅行目的地：")
  start_date = input("请输入你的旅行开始日期 (YYYY-MM-DD)：")
  end_date = input("请输入你的旅行结束日期 (YYYY-MM-DD)：")
  req = input("请输入你的旅行需求：")

  plan = asyncio.run(generate_plan(dest, start_date, end_date, req))

  print(f"输出计划：\n{plan}")

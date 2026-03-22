from ..core.orchestrator import generate_plan


async def generate_travel_plan(city: str, start_date: str, end_date: str,
                               user_in: str):
  """
  调用 orchestrator 生成旅行计划
  """
  result = await generate_plan(
    city=city,
    start_date=start_date,
    end_date=end_date,
    user_in=user_in
  )
  return result

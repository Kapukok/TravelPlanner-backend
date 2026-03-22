from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Tuple


class UserConstraints(BaseModel):
    city: str = Field(..., description="目的地城市")
    days: int = Field(..., description="游玩天数")
    budget: float = Field(..., description="总预算")
    must_visit: List[str] = Field(default=[], description="硬约束：必去景点")
    preferences: List[str] = Field(default=[], description="软偏好：如'喜欢历史', '不吃辣'")
    hotel_pref: str = Field(default="舒适型", description="酒店偏好：如'五星级', '经济型'")

class POI(BaseModel):
    priority:int=0 #增加 POI 特征 用来描述景点的重要性 priority越大说明景点越“重要”（代表用户特别想去）
    id:str
    name:str
    level:int=0 #处理成“几A”级景区
    address:str
    location:Tuple[float,float]
    rating:float=0.0
    cost:float=0.0
    duration:int=120 #规定如果是hotel和restaurant 此项就变成距离
    openTime:int=510
    closeTime:int=1440
    closeday:List[int]=[]
    type:List[str]
    photo:str
    description:str=""
    smallAttraction:str=""
    openTime_str:str = ""
    def __repr__(self) -> str:
        # 构造字段名和值的字符串，保持格式统一且易读
        fields = [
            f"priority={self.priority}",
            f"id={self.id!r}",
            f"name={self.name!r}",
            f"level={self.level}",
            f"address={self.address!r}",
            f"location={self.location}",
            f"rating={self.rating}",
            f"cost={self.cost}",
            f"duration={self.duration}",
            f"openTime={self.openTime}",
            f"closeTime={self.closeTime}",
            f"closeday={self.closeday}",
            f"type={self.type}",
            f"photo={self.photo!r}",
            f"description={self.description!r}",
            f"smallAttraction={self.smallAttraction!r}"
        ]
        # 拼接成规范的 repr 格式
        return f"POI({', '.join(fields)})"

class DayItinerary(BaseModel):
    day_index: int=-1
    hotel: List[POI]=[]
    spots: List[POI]=[]
    restaurants: List[POI]=[]
    transport_time: Dict[str, int] = {}
    def __repr__(self) -> str:
        # 构造各字段的展示字符串，优化列表/字典的可读性
        # 对POI列表，展示每个POI的核心信息（name），避免内容过长；若需完整信息可替换为self.hotel
        hotel_str = f"[{', '.join([f'POI(name={h.name!r})' for h in self.hotel])}]" if self.hotel else "[]"
        spots_str = f"[{', '.join([f'POI(name={s.name!r})' for s in self.spots])}]" if self.spots else "[]"
        restaurants_str = f"[{', '.join([f'POI(name={r.name!r})' for r in self.restaurants])}]" if self.restaurants else "[]"
        
        # 拼接所有字段
        fields = [
            f"day_index={self.day_index}",
            f"hotel={hotel_str}",
            f"spots={spots_str}",
            f"restaurants={restaurants_str}",
            f"transport_time={self.transport_time}"
        ]
        return f"DayItinerary({', '.join(fields)})"

class FinalPlan(BaseModel):
    itineraries: List[DayItinerary]
    total_cost: float
    report: str
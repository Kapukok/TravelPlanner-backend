import asyncio
import copy
from typing import List, Tuple

from urllib3.util.proxy import connection_requires_http_tunnel

from app.models.internal import POI, DayItinerary
from app.tools.amap_client import search,distance,cleanData
from app.tools.amap_client import search_around
from app.tools.info import if_include,filterAttraction
from app.tools.info import web, chat
from app.tools.database import Database
from app.tools.parseInfo import parseIn
class ResourceSearcher:
    #useDatabase表示是否使用数据库，默认为True，如果数据库连接失败则自动降级为False，直接调用高德地图API搜索
    #maxConnectTimes表示尝试连接数据库的最大次数，默认为3次，如果超过这个次数仍然无法连接，则放弃连接数据库，直接使用API搜索
    def __init__(self,day:int,useDatabase:bool=True,maxConnectTimes:int=3):
        self.day=day
        self.useDatabase=useDatabase
        if useDatabase:
            self.db=Database()
            try:
                for i in range(maxConnectTimes):
                    if self.db.is_connected():
                        print("searcher:数据库连接成功！")
                        break
                    else:
                        self.db._connect()
                        print(f"searcher:数据库连接失败，正在重试... ({i+1}/{maxConnectTimes})")
            except Exception as e:
                print(f"searcher:数据库连接失败 ({i+1}/{maxConnectTimes}) 错误信息: {e}")
            if not self.db.is_connected():
                print("searcher:数据库连接失败，已放弃连接数据库，将直接使用API搜索。")
                self.useDatabase = False

    def calculateDistance(self, loc1: Tuple[float,float], loc2: Tuple[float,float]) -> float: #偷偷把 planner 代码拷过来用
        if not loc1 or not loc2:
            print("planner:Warning: Missing location data for distance calculation.")
            return float('inf')
        import math
        lat1, lon1 = loc1
        lat2, lon2 = loc2
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = 6371 * c
        return distance


    async def search_attractions(self, city: str, keywords: List[str],attractions:List[str], forbid: List[str]) -> List[POI]:
        # TODO: 调用 tools/amap_client.py
        filtered_pois = {}
        def add_poi(poi: POI, priority: int):
            if poi.id in filtered_pois:
                if priority > filtered_pois[poi.id].priority:
                    filtered_pois[poi.id].priority = priority
            else:
                poi.priority = priority
                filtered_pois[poi.id] = poi

        async def fillInfo(self, city: str, ans: list[POI]) -> list[POI]:
            # 填充重要信息
            for a in ans:
                inf = await chat(a.name + city)
                des=await web(f"{city}{a.name}的景点介绍和相关游玩路线")
                time=await parseIn(a.openTime_str,a.name)
                if not isinstance(time,dict):
                    time = {}
                openTime= time.get("openTime", 510)
                closeTime= time.get("closeTime", 1440)
                closeday = time.get("closeday", [])
                if not isinstance(inf, dict):
                    inf = {}
                a.cost = inf.get("cost", 0)
                a.duration = inf.get("duration", 120)
                a.description=des
                a.openTime = openTime
                a.closeTime = closeTime
                a.closeday = closeday
            return ans
        async def clean(keyword: str) -> List[POI]:
            ret = await search(keyword, city)
            cleaned = await cleanData(ret)
            if not cleaned: return []
            valid_pois = []
            for att in cleaned:
                if '-' in att.name: continue
                if any(word in att.name for word in forbid): continue
                if any(word in typ for word in forbid for typ in att.type): continue
                valid_pois.append(att)
            return valid_pois
        #TODO: 清洗数据并根据模糊 POI 和精确 POI 搜索
        for kw in attractions:
            candidates = await clean(kw)
            if candidates:
                candidates.sort(key=lambda x: (0.3*x.rating+0.7*x.level), reverse=True)
                add_poi(candidates[0], 3)
        for kw in keywords:
            candidates = await clean(kw)
            if candidates:
                candidates.sort(key=lambda x: (0.9*x.rating+0.1*x.level), reverse=True)
                for i in range(min(len(candidates),3)):
                    if candidates[i].rating>=2:
                        add_poi(candidates[i], 2)

        candidates = await clean(f"{city}热门景点")
        if candidates:
            candidates.sort(key=lambda x: (0.9*x.rating+0.1*x.level), reverse=True)
            for i in range(min(len(candidates),self.day*3)):
                if candidates[i].rating>=3:
                    add_poi(candidates[i], 1)

        if not filtered_pois:
            return []
        ans = []
        dp_pois = []
        for poi in filtered_pois.values():
            if self.useDatabase:
                try:
                    p=self.db.query_data(None,poi.name,city,None)
                    if p:
                        for p2 in p:
                            p2.priority=poi.priority
                        dp_pois+=p
                    else:
                        ans.append(poi)
                except Exception as e:
                    print(f"searcher:数据库查询失败，错误信息: {e}")
            else:
                ans.append(poi)
        ans.sort(key=lambda x: x.rating, reverse=True)
        newAns=ans
        # 对景点进行筛选
        rubbishBin=set()
        # for i in range(0,len(ans)):
        #     if ans[i].id in rubbishBin: continue
        #     for j in range(i+1,len(ans)):
        #         if ans[j].id in rubbishBin: continue
        #         dis=self.calculateDistance(ans[i].location,ans[j].location)
        #         if dis<5:
        #             res=await if_include(ans[i].name,ans[j].name)
        #             if res==1:
        #                 ans[j].smallAttraction=ans[j].smallAttraction+ans[i].smallAttraction+" "
        #                 rubbishBin.add(ans[i].id)
        #                 break
        #             elif res==2:
        #                 ans[i].smallAttraction=ans[i].smallAttraction+ans[j].smallAttraction+" "
        #                 rubbishBin.add(ans[j].id)
        # newAns=[x for x in ans if x.id not in rubbishBin]
        lastAns=await filterAttraction(self.day,newAns)
        res=[]
        if lastAns:
            res=await fillInfo(self,city,lastAns)
        elif newAns:
            res=await fillInfo(self,city,newAns)
        elif ans:
            res=await fillInfo(self,city,ans)
        #print(f"{res}")
        res+=dp_pois
        return res

    async def search_hotels(self, city: str,keyword:list[str],center_point:Tuple[float,float]) -> List[POI]:
        # TODO: 搜酒店
        promp=" ".join(word for word in keyword)
        res=await search_around("100000",city,promp,center_point,5000)
        #考虑一下保留哪些数据吧
        if res is None:
            return []
        ret = []
        pois = res.get("pois", [])
        if not pois:
            return []
        for p in pois:
            id = p.get("id")
            dist=p.get("distance","")
            dist=int(dist)
            name = p.get("name")
            if not id or not name:
                continue
            loc = p.get("location", "")
            if not loc or "," not in loc:
                continue
            num1, num2 = loc.split(",")
            tup = (float(num1), float(num2))
            add = p.get("address")
            if isinstance(add, list):
                add = ""
            phurl = p.get("photos", [])
            url = ""
            if phurl and isinstance(phurl, list) and len(phurl) > 0:
                first = phurl[0]
                if isinstance(first, dict):
                    url = first.get("url", "")
            else:
                ""
            text = p.get("biz_ext")
            if not isinstance(text, dict):
                continue
            rating = text.get("rating")
            if not rating:
                rating = 0.0
            else:
                rating = float(rating)
            cos = text.get("cost", "")
            if cos:
                cos = float(cos)
            else:
                cos = 0.0
            st = p.get("type", "")
            typ = []
            if isinstance(st, str) and st:
                if ";" in st:
                    typ = st.split(";")
                else:
                    typ = [st]
            lev = text.get("level",0)
            ret.append(POI(
                priority=1,
                id=id,
                name=name,
                level=lev,
                address=add,
                location=tup,
                rating=rating,
                cost=cos,
                duration=dist,
                type=typ,
                photo=url
            ))
        ret.sort(key=lambda x: 5 * x.rating - 0.5 * x.duration, reverse=True)
        ans = ret[:5]
        #print("\n")
        #print(f"{ans}")
        return ans

    async def search_restaurants(self, keyword:list[str],center:Tuple[float,float]) -> List[POI]:
        # TODO: 根据每天中午所在的景点位置，搜附近的餐厅
        res=[]
        keyword.append("美食")
        for key in keyword:
            ret=[]
            tmp=await search_around("050000","",key,center,2000)
            if tmp is None:
                continue
            pois = tmp.get("pois",[])
            if not pois:
                continue
            for p in pois:
                id = p.get("id")
                dist = p.get("distance", "")
                dist = int(dist)
                name = p.get("name")
                if not id or not name:
                    continue
                loc = p.get("location", "")
                if not loc or "," not in loc:
                    continue
                num1, num2 = loc.split(",")
                tup = (float(num1), float(num2))
                add = p.get("address")
                if isinstance(add, list):
                    add = ""
                phurl = p.get("photos", [])
                url = ""
                if phurl and isinstance(phurl, list) and len(phurl) > 0:
                    first = phurl[0]
                    if isinstance(first, dict):
                        url = first.get("url", "")
                else:
                    ""
                text = p.get("biz_ext")
                if not isinstance(text, dict):
                    continue
                rating = text.get("rating")
                if not rating:
                    rating = 0.0
                else:
                    rating = float(rating)
                cos = text.get("cost", "")
                if cos:
                    cos = float(cos)
                else:
                    cos = 0.0
                st = p.get("type", "")
                typ = []
                if isinstance(st, str) and st:
                    if ";" in st:
                        typ = st.split(";")
                    else:
                        typ = [st]
                lev = text.get("level", 0)
                if isinstance(lev, list):
                    lev = 0
                else:
                    try:
                        lev = int(lev)
                    except (ValueError, TypeError):
                        lev = 0
                ret.append(POI(
                    priority=1,
                    id=id,
                    name=name,
                    level=lev,
                    address=add,
                    location=tup,
                    rating=rating,
                    cost=cos,
                    duration=dist,
                    type=typ,
                    photo=url
                ))
            ret.sort(key=lambda x: 2 * x.rating - 0.5 * x.duration, reverse=True)
            ret=ret[:2]
            res+=ret
        #print("\n")
        #print(f"{res}")
        return res

if __name__=="__main__":
    r = ResourceSearcher(3)
    asyncio.run(r.search_attractions("成都",["熊猫","商业街"],["三星堆","成都博物馆"],[]))

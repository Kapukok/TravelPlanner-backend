from textwrap import indent
from typing import Dict, List, Any, Tuple, Coroutine
import httpx
import asyncio
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from app.models.internal import POI
from app.tools.info import chat
load_dotenv()

async def _request_with_retry(url: str, params: dict, retries: int = 5):
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(retries):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status")
                    if status == "1":
                        return data
                    elif "CUQPS" in data.get("info", ""):
                        await asyncio.sleep(1.0 + i * 0.5)
                        continue
                    else:
                        print(f"API error: {data.get('info')}")
                        return None
                else:
                    print(f"Request fail: {response.status_code}")
            except Exception as e:
                pass
            await asyncio.sleep(0.5)
    return None

async def search(keyword:str,city:str):
    api=os.getenv("AMAP_API_KEY")
    if not api:
        print("API Wrong")
        return None
    url="https://restapi.amap.com/v3/place/text"

    para={
        "key":api,
        "keywords":keyword,
        "city":city,
        "types":"110000|140100|140200|140300|140400|140500|140600|140700|140800|061000|060100",
        "output":"JSON"
    }

    return await _request_with_retry(url, para)

async def cleanData(data:Dict[str,Any])-> list[Any] | None:
    if data is None:
        return None
    ret=[]
    pois=data.get("pois",[])
    if not pois:
        return None
    for p in pois:
        id=p.get("id")
        name=p.get("name")
        if not id or not name:
            continue
        loc=p.get("location","")
        if not loc or "," not in loc:
            continue
        num1,num2=loc.split(",")
        tup=(float(num1),float(num2))
        add = p.get("address")
        if isinstance(add, list):
            add = ""
        phurl=p.get("photos",[])
        url=""
        if phurl and isinstance(phurl,list) and len(phurl)>0:
            first=phurl[0]
            if isinstance(first,dict):
                url=first.get("url","")
        else:
            ""
        text=p.get("biz_ext")
        if not isinstance(text,dict):
            continue
        rating=text.get("rating")
        # 时间修改
        opentime2=text.get("opentime2")
        if not opentime2:
            opentime2=""
        if not rating:
            rating=0.0
        else: rating=float(rating)
        cos=text.get("cost","")
        if cos:
            cos=float(cos)
        else: cos=0.0
        st = p.get("type", "")
        typ = []
        if isinstance(st, str) and st:
            if ";" in st:
                typ = st.split(";")
            else:
                typ = [st]
        lev=text.get("level","")
        num=0
        if lev:
            num=len(lev)
        ret.append(POI(
        priority=0,
        id=id,
        name=name,
        level=num,
        address=add,
        location=tup,
        rating=rating,
        openTime_str=opentime2,
        cost=cos,
        type=typ,
        photo=url
        ))
    #print(f"{ret}")
    #print("\n")
    return ret

async def distance(origins:list[tuple], destination:tuple[float,float])-> list[Tuple[float, float]] | None:
    api=os.getenv("AMAP_API_KEY")
    if not api:
        print("API Wrong")
        return None
    url="https://restapi.amap.com/v3/distance"
    origins ="|".join([f"{a},{b}" for a,b in origins])
    destination = f"{destination[0]},{destination[1]}"
    params={
        "key":api,
        "origins":origins,
        "destination":destination,
        "output":"JSON"
    }

    data = await _request_with_retry(url, params)
    if data:
        result = data.get("results", [])
        ans=[]
        for t in result:
            ans.append((float(t.get("distance",-1)),float(t.get("duration",-1))))
        return ans
    return None

async def search_around(types:str,city:str,keyword:str,center:Tuple[float,float],radius:int):
    api = os.getenv("AMAP_API_KEY")
    if not api:
        print("API Wrong")
        return None
    url = "https://restapi.amap.com/v3/place/around"
    location=f"{center[0]},{center[1]}"
    params = {
        "key": api,
        "location":location,
        "keywords":keyword,
        "types":types,
        "city":city,
        "radius":radius,
        "output": "JSON"
    }
    return await _request_with_retry(url, params)


if __name__ == "__main__":
    asyncio.run(search("都江堰","成都"))
    #asyncio.run(search_around("100000","成都","酒店",(104.077774,30.655544),10000))

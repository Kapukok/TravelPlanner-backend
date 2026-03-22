from typing import List,Tuple
from app.models.internal import POI, DayItinerary
from app.tools.amap_client import distance
import numpy as np
import asyncio
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
class _UnionFind:
    def __init__(self, POIList: List[POI]):
        self.parent = list(range(len(POIList)))
        self.size = [1] * len(POIList)
        self.pos=[POI.location for POI in POIList]

    def find(self, p: int) -> int:
        if self.parent[p] != p:
            self.parent[p] = self.find(self.parent[p])
        return self.parent[p]

    def union(self, p: int, q: int):
        rootP = self.find(p)
        rootQ = self.find(q)
        if rootP == rootQ:
            return
        if self.size[rootP] > self.size[rootQ]:
            self.parent[rootQ] = rootP
            self.pos[rootP]=(self.pos[rootP][0]*self.size[rootP]+self.pos[rootQ][0]*self.size[rootQ])/(self.size[rootP]+self.size[rootQ]),(self.pos[rootP][1]*self.size[rootP]+self.pos[rootQ][1]*self.size[rootQ])/(self.size[rootP]+self.size[rootQ])
            self.size[rootP] += self.size[rootQ]
        else:
            self.parent[rootP] = rootQ
            self.pos[rootQ]=(self.pos[rootP][0]*self.size[rootP]+self.pos[rootQ][0]*self.size[rootQ])/(self.size[rootP]+self.size[rootQ]),(self.pos[rootP][1]*self.size[rootP]+self.pos[rootQ][1]*self.size[rootQ])/(self.size[rootP]+self.size[rootQ])
            self.size[rootQ] += self.size[rootP]

class _AttractionsUnion:
    def __init__(self,attractions: List[POI]=[], location: Tuple[float,float]=(0.0,0.0)):
        self.attractions=attractions
        self.location=location

class CorePlanner:
    startTime=540
    cityDis=40
    earth_radius=6371
    useKmeans=True
    useDistanceAPI=True
    transportSpeed=1
    lunchPos=(0,0)
    dinnerPos=(0,0)
    lunchTimeBegin=690
    dinnerTimeBegin=1050
    defaultDuration=120
    def __init__(self,cityDis:int = 40, TSPBound:int = 15, useKmeans:bool = True, useDistanceAPI:bool=True, startTime:int=540, transportSpeed:float=1):
        self.cityDis = cityDis
        self.earth_radius = 6371              #地球半径，单位为公里
        self.TSPBound = TSPBound              #根据数据规模大小选择使用 TSP 的算法，超过这个规模就使用贪心算法
        self.useKmeans=useKmeans              #是用Kmeans算法还是我自己整的乱七八糟算法
        self.useDistanceAPI=useDistanceAPI    #是否预处理距离矩阵，距离矩阵的计算可能比较慢，但可以加速后续的TSP计算
        self.startTime=startTime              #默认每天9点开始旅行，单位为分钟，可以根据实际情况调整
        if transportSpeed>0:
            self.transportSpeed=transportSpeed    #默认交通工具平均速度为1km/min，可以根据实际情况调整,用于估算交通时间
        else:
            print("planner:transportSpeed should be bigger than zero.")

    def calculateDistance(self, loc1: Tuple[float,float], loc2: Tuple[float,float]) -> float: #通过经纬度计算两点之间的距离，将地球视为理想球体，使用 Haversine 公式计算距离
        if not loc1 or not loc2:
            print("planner:Warning: Missing location data for distance calculation.")
            return float('inf')  # 如果没有位置信息，返回无穷大表示无法计算距离
        import math
        lat1, lon1 = loc1
        lat2, lon2 = loc2
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = self.earth_radius * c
        return distance
    
    # 以下方法已经成为了时代的眼泪，暂时保留在这里以备不时之需
    '''
    使用时传入的列表中的元素必须包含location属性表示位置（经纬度）
    若使用endPos参数表示旅行结束位置，endPos需要与attractions列表中的元素一致，且包括在attractions列表中
    若使用startPos参数表示旅行开始位置，startPos需要与attractions列表中的元素一致，但不包括在attractions列表中（否则重复计算），同时，返回值也不会包含startPos
    def TSPsolution(self, attractions: List,startPos=None,endPos=None) -> List:
        if not attractions:
            print("planner:No attractions provided for TSP solution.")
            return []
        if len(attractions) <= self.TSPBound:
            lenAttractions = len(attractions)
            dp=[[float('inf')] * lenAttractions for _ in range(1 << lenAttractions)]
            preDis=[[self.calculateDistance(attractions[i].location, attractions[j].location) for i in range(lenAttractions)] for j in range(lenAttractions)]
            if startPos:
                for i in range(lenAttractions):
                    dp[1 << i][i] = self.calculateDistance(startPos.location,attractions[i].location)
            else:
                for i in range(lenAttractions):
                    dp[1 << i][i] = 0
            for mask in range(1 << lenAttractions):
                for i in range(lenAttractions):
                    if mask & (1 << i):
                        for j in range(lenAttractions):
                            if not (mask & (1 << j)):
                                dp[mask | (1 << j)][j] = min(dp[mask | (1 << j)][j], dp[mask][i] + preDis[i][j])
            minCost = float('inf')
            last = -1
            fullMask=(1 << lenAttractions) - 1
            res=[]
            if endPos:
                for i in range(lenAttractions):
                        if attractions[i].location == endPos.location:
                            last = i
                            break
            if last==-1:
                for i in range(lenAttractions):
                    if dp[fullMask][i] < minCost:
                        minCost = dp[(1 << lenAttractions) - 1][i]
                        last = i
            while fullMask!=0:
                res.append(attractions[last])
                for i in range(lenAttractions):
                    if fullMask & (1 << i) and dp[fullMask][last] == dp[fullMask ^ (1 << last)][i] + preDis[i][last]:
                        fullMask ^= (1 << last)
                        last = i
                        break
            if startPos:
                res.append(startPos)
            return res[::-1]
        visited = [False] * len(attractions)
        attraction=None
        res=[]
        if startPos:
            res.append(startPos)
            attraction=startPos
        elif not endPos or attractions[0]!=endPos:
            res.append(attractions[0])
            attraction=attractions[0]
            visited[0]=True
        else:
            if len(attractions)>1:
                res.append(attractions[1])
                attraction=attractions[1]
                visited[1]=True
            else:
                return attractions
        while not all(visited):
            next_index = -1
            min_distance = float('inf')
            for j in range(len(attractions)):
                if not visited[j]:
                    dist = self.calculateDistance(attraction, attractions[j])
                    if dist < min_distance:
                        min_distance = dist
                        next_index = j
            res.append(attractions[next_index])
            attraction=attractions[next_index]
            visited[next_index] = True
        return res
    '''
    
    async def TSPsolutionAttractionsDFS(self, attractions: List[POI],startPos:POI=None,endPos:POI=None,startTime:int=startTime,hasLunch:Tuple[float,float]=None,hasDinner:Tuple[float,float]=None) -> Tuple[List[POI], Tuple[float,float],Tuple[float,float]]:#从左到右依次是：所有景点规划的旅行路线，午饭坐标，晚饭坐标
        if not attractions:
            #print("planner:find TSP solution.")
            # if endPos is not None and startPos is not None:
            #     temp=await distance(list(startPos.location),endPos.location)
            #     if temp is None:
            #         print(f"ERROR planner:distance API responded fail: origins={startPos.location},destination={endPos.location}")
            #         return [], hasLunch, hasDinner
            #     return [endPos], hasLunch, hasDinner
            return [], hasLunch, hasDinner
        bestList=[]
        bestLunchPos=None
        bestDinnerPos=None
        for i in range(len(attractions)):
            arriveTime=startTime
            if startPos:
                if self.useDistanceAPI:
                    temp=await distance([startPos.location],attractions[i].location)
                    if temp is None:
                        print(f"ERROR planner:distance API responded fail: origins={startPos.location},destination={attractions[i].location}")
                        continue
                    arriveTime=temp[0][0]/self.transportSpeed+startTime
                else:
                    arriveTime=self.calculateDistance(startPos.location,attractions[i].location)/self.transportSpeed+startTime
            if startTime>=self.lunchTimeBegin and hasLunch is None: 
                arriveTime+=90
                if(startPos is None):
                    hasLunch=attractions[i].location
                else:
                    hasLunch=startPos.location
            if startTime>=self.dinnerTimeBegin and hasDinner is None: 
                arriveTime+=90
                if(startPos is None):
                    hasDinner=attractions[i].location
                else:
                    hasDinner=startPos.location
            if(arriveTime>=attractions[i].closeTime):
                continue
            res=await self.TSPsolutionAttractionsDFS(attractions[:i] + attractions[i+1:],attractions[i],endPos,min(arriveTime+(self.defaultDuration if attractions[i].duration is None else attractions[i].duration),attractions[i].closeTime),hasLunch,hasDinner)
            if len(res[0])+1>len(bestList):
                bestList=res[0]+[attractions[i]]
                bestLunchPos=res[1]
                bestDinnerPos=res[2]
        return bestList,bestLunchPos,bestDinnerPos
            
            
            

    #单独的kmeans函数，减少关联度
    def KmeansClustering(self, attractions: List[POI], days: int) -> List[Tuple[List[POI], Tuple[float, float]]]:
        if not attractions:
            print("planner:No attractions provided for K-Means clustering.")
            return []
        if days <= 0:
            print("planner:Invalid number of days for K-Means clustering.")
            return []
        X = np.array([poi.location for poi in attractions])
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        kmeans = KMeans(n_clusters=days, random_state=0, n_init=10, init="k-means++", max_iter=300, tol=1e-4)
        labels = kmeans.fit_predict(X_scaled)
        centers_scaled = kmeans.cluster_centers_
        centers_original = scaler.inverse_transform(centers_scaled)
        clusters = [[] for _ in range(days)]
        for i, label in enumerate(labels):
            clusters[label].append(attractions[i])
        return [(clusters[i], tuple(centers_original[i])) for i in range(days)]


    def _checkInfoPOI(self, poi:POI):
        if poi.name is None:
            print("planner:find a poi lacking name")
            return False
        allRight=True
        if poi.closeTime is None:
            print("ERROR planner:a POI's closeTime is none:"+poi.name)
            allRight=False
        if poi.openTime is None:
            print("ERROR planner:a POI's openTime is none:"+poi.name)
            allRight=False
        if poi.location is None:
            print("ERROR planner:a POI's location is none:"+poi.name)
            allRight=False
        return allRight

    #DayItinerary列表的day_index属性从0开始
    async def plan_logistics(self, days: int, attractions: List[POI], hotels: List[POI]) -> List[Tuple[DayItinerary,Tuple[float,float],Tuple[float,float]]]:#后两者为计划的午餐晚餐食用地点，用于传给search进行搜索

        #错误输入检测
        if not attractions or len(attractions) == 0:
            print("ERROR planner:No attractions to plan.")
            return []
        if not hotels or len(hotels) == 0:
            print("planner:No hotels available for planning.")
            #     return []
        if days <= 0:
            print("ERROR planner:Invalid number of days.")
            return []
        if days > len(attractions):
            print("ERROR planner:Number of days exceeds number of attractions.")
            return []
        for poi in attractions:
            if(not self._checkInfoPOI(poi)):
                return []
        for hotel in hotels:
            if(not self._checkInfoPOI(hotel)):
                return []

        #Kmeans聚类
        attractionsUnions=[]
        if self.useKmeans:
            X=np.array([list(poi.location) for poi in attractions])
            scaler = StandardScaler()
            X = scaler.fit_transform(X)
            kmeans=KMeans(
                n_clusters=days,
                random_state=0,
                n_init=10,
                init="k-means++",
                max_iter=300,
                tol=1e-4
            )
            labels=kmeans.fit_predict(X)
            centersScaled = kmeans.cluster_centers_
            centersOriginal = scaler.inverse_transform(centersScaled)
            tempLabelRem=[]
            for i in range(len(attractions)):
                canFind=False
                for j in range(len(tempLabelRem)):
                    if tempLabelRem[j]==labels[i]:
                        attractionsUnions[j].attractions.append(attractions[i])
                        canFind=True
                        break
                if not canFind:
                    attractionsUnions.append(_AttractionsUnion([attractions[i]], centersOriginal[labels[i]]))
                    tempLabelRem.append(labels[i])
        else:
            unionFind=_UnionFind(attractions)
            for i in range(len(attractions)):
                for j in range(i+1, len(attractions)):
                    if self.calculateDistance(unionFind.pos[unionFind.find(i)], unionFind.pos[unionFind.find(j)]) <= self.cityDis:
                        unionFind.union(i, j)
            visited=[False]*len(attractions)
            for i in range(len(attractions)):
                if not visited[i]:
                    group=[]
                    for j in range(len(attractions)):
                        if unionFind.find(i)==unionFind.find(j):
                            group.append(attractions[j])
                            visited[j]=True
                    attractionsUnions.append(_AttractionsUnion(group, unionFind.pos[unionFind.find(i)]))
        #attractionsUnion=self.TSPsolution(attractionsUnion)

        #每日规划
        averageAttractionsPerDay = len(attractions) // days
        res=[]
        unionInd=0
        extraAttractionsNum=len(attractions)-days*averageAttractionsPerDay
        leftDaysNum=days
        for day in range(days):
            dayItinerary=DayItinerary()
            dayItinerary.day_index=day
            todayAttractions=[]
            currentCount=0
            needCount=averageAttractionsPerDay+extraAttractionsNum//leftDaysNum
            leftDaysNum-=1
            extraAttractionsNum-=needCount-averageAttractionsPerDay
            if(extraAttractionsNum<0):
                extraAttractionsNum=0
            while currentCount<needCount:
                todayAttractions.append(attractionsUnions[unionInd].attractions[-1])
                attractionsUnions[unionInd].attractions.pop()
                currentCount=currentCount+1
                if len(attractionsUnions[unionInd].attractions)==0:
                    unionInd+=1
                if unionInd==len(attractionsUnions):
                    if day<days-1:
                        print("planner:please tell changchanggod something bad happens")
                    break
            solution=await self.TSPsolutionAttractionsDFS(todayAttractions,None,None,self.startTime,None,None)
            dayItinerary.spots=list(reversed(solution[0]))
            dayItinerary.hotel=hotels
            dayItinerary.restaurants=[] #wait searcher to find restaurants
            dayItinerary.transport_time={} #TODO
            if solution[1] is None:
                print("planner:lunch position is none:"+str(day))
                res.append((dayItinerary,(34,108),(34,108)))
            elif solution[2] is None:
                print("planner:dinner position is none:"+str(day))
                res.append((dayItinerary,solution[1],solution[1]))
            else:
                res.append((dayItinerary,solution[1],solution[2]))
        return res
    
if __name__ == "__main__":
    POIs=[POI(id="B0FFGM256I", name="白云山风景名胜区", location=(119.453622, 27.146415), openTime=480, closeTime=1050, priority=1, level=0, address="晓阳镇下南溪村", rating=4.4, cost=90, duration=180, closeday=[], type=["风景名胜","风景名胜","国家级景点"], photo="http://store.is.autonavi.com/showpic/7f989120b6d8e5e270aea593330b780a", description="Fu'an White Cloud Mountain is a 4A national scenic area and geological park known for its unique geological formations, including ice caves and cloud sea views. The main attractions include White Cloud Peak, Nine Dragon Cave, and Dragon Pavilion Valley. The best time to visit is from April to December.", smallAttraction=""),

POI(id="B0251023SV", name="天马山风景区", location=(119.657732, 27.074609), openTime=0, closeTime=1439, priority=1, level=0, address="阳泉路248号", rating=4.3, cost=0, duration=1080, closeday=[], type=["风景名胜","风景名胜","风景名胜"], photo="http://store.is.autonavi.com/showpic/cbc5e917989f61db59e31b89026e09d5", description="Tianmashan Scenic Area in Fu'an, Fujian, features natural landscapes, waterfalls, and temples. It's open year-round with no entrance fee. Recommended visit time is spring and autumn.", smallAttraction=""),

POI(id="B0FFH6WT44", name="阳头广场", location=(119.643728, 27.081967), openTime=0, closeTime=1439, priority=1, level=0, address="福州路", rating=4.2, cost=0, duration=150, closeday=[], type=["风景名胜","公园广场","城市广场"], photo="https://aos-comment.amap.com/B0FFH6WT44/comment/EC58810F_BD8F_4050_9503_91695DE59864_L0_001_1170_778_1741343893486_51584576.jpg", description="Yangtou Square in Fujian features cultural activities, traditional crafts, and non-heritage experiences. Popular attractions include the non-heritage festival and local performances. It's a hub for cultural tourism and community engagement.", smallAttraction=" "),

POI(id="B0FFG2DW14", name="福安市溪塔葡萄沟旅游景区", location=(119.529678, 27.082747), openTime=480, closeTime=1320, priority=1, level=2, address="穆云镇溪塔村", rating=4.1, cost=0, duration=120, closeday=[], type=["风景名胜","风景名胜相关","旅游景点"], photo="https://aos-comment.amap.com/B0FFG2DW14/comment/content_media_external_images_media_82805_ss__1727948101474_32123433.jpg", description="Fu'an Xitata Grape Valley is famous for its stunning grape scenery and rich She culture. It's open daily from 8:00 to 17:00. The entrance fee starts at ¥138.", smallAttraction=""),

POI(id="B0251023R1", name="种德禅寺", location=(119.635957, 26.923721), openTime=0, closeTime=1439, priority=1, level=0, address="甘棠镇", rating=4.1, cost=90, duration=120, closeday=[], type=["风景名胜","风景名胜","寺庙道观"], photo="https://store.is.autonavi.com/showpic/fac5433fcc94e8884c3b6bfaf0c7a48f", description="种德禅寺位于福安甘棠镇，是闽东地区规模最大的女众丛林，以其雄伟建筑和丰富的佛教活动著称。寺内有大雄宝殿、玉佛殿等，供奉着白玉释迦佛像。每月初八、二十三举行八关斋戒，吸引众多信众。", smallAttraction=""),

POI(id="B0FFFZ9FBL", name="中山公园", location=(119.728942, 26.977474), openTime=0, closeTime=1439, priority=1, level=0, address="溪柄镇坂垱路", rating=4.0, cost=0, duration=150, closeday=[], type=["风景名胜","公园广场","公园"], photo="https://aos-comment.amap.com/B0FFFZ9FBL/comment/content_media_external_file_100006286_1757351573770_74302978.jpg", description="Fu'an Zhongshan Park is a scenic forest park featuring natural landscapes and historical sites. Key attractions include the ancient trees and the rich cultural history of the area. It's a popular spot for nature lovers and history enthusiasts.", smallAttraction=""),

POI(id="B02510PB8F", name="齐天大圣宫", location=(119.633228, 27.101851), openTime=420, closeTime=960, priority=1, level=0, address="坂中街149号", rating=3.9, cost=300, duration=120, closeday=[], type=["风景名胜","风景名胜","寺庙道观"], photo="http://store.is.autonavi.com/showpic/479e3ef740971eaee06105f98c2c5275", description="The Fuan Temple in Fujian Province is a popular pilgrimage site. It features ancient architecture and vibrant deity statues. Entrance fees start at ¥138.", smallAttraction="")]
    planner=CorePlanner(40,15,True,False,540,1)
    temp=asyncio.run(planner.plan_logistics(1,POIs,POIs))
    print(temp)

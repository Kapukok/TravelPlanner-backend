import mysql.connector
import os
import dotenv
import json
from typing import Optional, List
from mysql.connector import Error
from app.models.internal import POI

# 加载环境变量（放在最外层，确保全局生效）
dotenv.load_dotenv()

class Database:
    def __init__(self):
        self.conn = None  # 初始化连接为None，避免属性未定义
        self._connect()  # 调用连接方法创建连接

    def _connect(self):
        """私有方法：创建/重连数据库连接（核心修复）"""
        # 优先从环境变量读取配置，硬编码仅作为兜底
        config = {
            "host": os.getenv("DATABASE_HOST", "172.25.204.39"),
            "port": int(os.getenv("DATABASE_PORT", 3306)),
            "user": os.getenv("DATABASE_USER", "root"),
            "password": os.getenv("DATABASE_PASSWORD"),
            "database": os.getenv("DATABASE_NAME", "trip_planner"),
            "charset": "utf8mb4"  # 避免中文乱码
        }

        # 校验密码是否配置
        if not config["password"]:
            print("❌ 环境变量 DATABASE_PASSWORD 未配置！")
            return

        try:
            # 若已有连接且未断开，直接返回
            if self.conn and self.conn.is_connected():
                return
            # 创建新连接
            self.conn = mysql.connector.connect(**config)
            if self.conn.is_connected():
                print(f"✅ 数据库连接成功！(host: {config['host']}:{config['port']})")
        except Error as e:
            print(f"❌ 数据库连接失败：{e}")
            self.conn = None  # 连接失败时置为None

    def query_data(
            self,
            id: Optional[str] = None,
            name: Optional[str] = None,
            city: Optional[str] = None,
            type: Optional[str] = None
        ) -> List[POI]:
        """
        查询POI数据（支持多字段组合查询，无参数时查询所有数据）
        :param id: POI的ID（精确匹配）
        :param name: POI名称（精确匹配）
        :param city: 城市名称（模糊匹配）
        :param type: POI类型（JSON包含匹配）
        :return: POI类的列表，查询失败返回空列表
        """
        # 前置检查：连接是否有效，无效则重连
        if not self.is_connected():
            print("⚠️ 数据库连接已断开，尝试重连...")
            self._connect()
            if not self.is_connected():
                print("❌ 重连失败，无法执行查询")
                return []

        cursor = None
        poi_list: List[POI] = []
        try:
            # 基础查询SQL（格式化优化，可读性更高）
            base_sql = """
            SELECT 
                id, name, level, address, city, 
                ST_X(location) as lng, ST_Y(location) as lat,
                rating, cost, duration, openTime, closeTime,
                closeday, type, photo, description
            FROM poi
            """
            query_sql = base_sql
            params = []
            where_conditions = []  # 用列表收集查询条件，避免多WHERE错误

            # 处理查询条件（修复字段校验+拼写+逻辑）
            if id:
                try:
                    where_conditions.append("id = %s")
                    params.append(int(id))  # 校验ID为数字
                except ValueError:
                    print(f"❌ ID必须是数字，输入值：{id}")
                    return poi_list
            
            if name:
                where_conditions.append("name = %s")
                params.append(name.strip())
            
            if city:
                where_conditions.append("city LIKE %s")  # 城市模糊匹配
                params.append(f"%{city.strip()}%")
            
            if type:
                where_conditions.append("JSON_CONTAINS(type, %s)")  # JSON字段匹配
                params.append(json.dumps(type.strip()))  # 修复typr拼写错误

            # 拼接WHERE子句（多条件用AND连接，加空格避免语法错误）
            if where_conditions:
                query_sql += " WHERE " + " AND ".join(where_conditions)

            # 执行查询
            cursor = self.conn.cursor()
            cursor.execute(query_sql, params)
            results = cursor.fetchall()

            # 解析结果（修复日志变量未定义问题）
            conditions = {}
            if id: conditions["id"] = id
            if name: conditions["name"] = name
            if city: conditions["city"] = city
            if type: conditions["type"] = type
            print(f"\n📋 查询结果：共 {len(results)} 条记录 (条件：{conditions or '无'})")
            
            if not results:
                return poi_list

            for row in results:
                # 1. 解析JSON类型字段（修复关键字冲突：type→poi_type）
                try:
                    poi_type = json.loads(row[13]) if row[13] else []
                except (json.JSONDecodeError, TypeError):
                    print(f"⚠️ 类型字段解析失败（ID：{row[0]}），使用空列表")
                    poi_type = []

                # 2. 解析闭馆日（0=周一，6=周日，返回1-7）
                closeday = []
                closeday_bit = row[12]
                if closeday_bit and isinstance(closeday_bit, int):
                    for i in range(7):
                        if closeday_bit & (1 << i):
                            closeday.append(i + 1)

                # 3. 解析数值字段（处理NULL值，避免类型错误）
                def _safe_num(val, default=0):
                    return val if val is not None else default

                # 4. 创建POI对象
                poi = POI(
                    id=str(row[0]),
                    name=row[1] or "",
                    level=_safe_num(row[2]),
                    address=row[3] or "",
                    city=row[4] or "",
                    location=(
                        _safe_num(row[5], 0.0),
                        _safe_num(row[6], 0.0)
                    ),
                    rating=_safe_num(row[7], 0.0),
                    cost=_safe_num(row[8], 0.0),
                    duration=_safe_num(row[9], 120),
                    openTime=_safe_num(row[10], 510),
                    closeTime=_safe_num(row[11], 1440),
                    closeday=closeday,
                    type=poi_type,
                    photo=row[14] or "",
                    description=row[15] or ""
                )
                poi_list.append(poi)

        except Error as e:
            print(f"❌ 查询数据失败：{e}")
        finally:
            # 确保游标关闭，避免资源泄露
            if cursor:
                cursor.close()
        return poi_list

    def is_connected(self) -> bool:
        """检查数据库连接状态（鲁棒性优化）"""
        try:
            return self.conn is not None and self.conn.is_connected()
        except Exception:
            return False

    def close(self):
        """手动关闭连接（推荐显式调用）"""
        try:
            if self.is_connected():
                self.conn.close()
                print("✅ 数据库连接已手动关闭")
                self.conn = None
        except Error as e:
            print(f"❌ 关闭连接失败：{e}")

    def __del__(self):
        """析构函数：程序退出时自动关闭连接"""
        self.close()

# ================== 使用示例 ==================
if __name__ == "__main__":
    # 初始化数据库对象
    db = Database()
    # 测试查询：按名称精确查询
    pois = db.query_data(None,"天坛公园","北京市",None)
    print(f"查询到 {len(pois)} 个POI：")
    for poi in pois:
        print(f"- {poi.name} | 等级：{poi.level} | 闭馆日：{poi.closeday}")
    # 手动关闭连接（可选，析构函数会自动关）
    db.close()
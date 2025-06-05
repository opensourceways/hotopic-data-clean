import psycopg2
from typing import List, Dict, Any
import logging
from config.settings import settings


class DataManager:
    def __init__(self):
        # 数据库配置（请根据实际情况修改）
        self.DB_CONFIG = {
            'dbname': settings.db_name,
            'user': settings.db_user,
            'password': settings.db_password,
            'host': settings.db_host,
            'port': settings.db_port
        }
        self.logger = logging.getLogger(__name__)
        self.table_name = "discussion"

    def fetch_from_pg(self) -> List[Dict[str, Any]]:
        try:
            with psycopg2.connect(**self.DB_CONFIG) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(f"SELECT * FROM {self.table_name};")
                    columns = [desc[0] for desc in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"数据库查询失败: {str(e)}")
            raise

    def update_pg_data(self, data_list: List[Dict[str, Any]]) -> int:
        if not data_list:
            return 0

        conn = None
        try:
            conn = psycopg2.connect(**self.DB_CONFIG)
            cursor = conn.cursor()

            # 获取需要更新的字段（排除id字段）
            fields = [k for k in data_list[0].keys() if k != 'id']

            # 构建参数化查询语句
            set_clause = ", ".join([f"{field} = %s" for field in fields])
            sql = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"

            # 生成参数列表
            params_list = [
                [item[field] for field in fields] + [item['id']]
                for item in data_list
            ]

            # 执行批量更新
            cursor.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount

        except KeyError as e:
            raise ValueError(f"字典中缺少必要字段: {str(e)}")
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"批量更新失败: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

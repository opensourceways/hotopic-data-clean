import psycopg2
from typing import List, Dict, Any
import logging
from config.settings import settings


class DataManager:
    VALID_FIELDS = {"id", "url", "topic_closed", "topic_summary"}

    def __init__(self):
        # 数据库配置（请根据实际情况修改）
        self.DB_CONFIG = {
            "dbname": settings.db_name,
            "user": settings.db_user,
            "password": settings.db_password,
            "host": settings.db_host,
            "port": settings.db_port,
        }
        self.logger = logging.getLogger(__name__)
        self.table_name = "discussion"

    def fetch_paginated_from_pg(self, page=1, page_size=10):
        if page < 1 or page_size < 1:
            raise ValueError("页码和分页大小必须大于0")

        offset = (page - 1) * page_size
        try:
            with psycopg2.connect(**self.DB_CONFIG) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT * FROM {self.table_name} 
                        WHERE topic_closed = FALSE 
                        AND (
                            (topic_summary IS NOT NULL AND topic_summary <> '')
                            OR ((topic_summary IS NULL OR topic_summary = '') AND is_deleted = FALSE)
                        )
                        ORDER BY id 
                        LIMIT %s OFFSET %s;
                        """,
                        (page_size, offset),
                    )
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    for item in results:
                        if "is_deleted" in item:
                            item["source_deleted"] = item.pop("is_deleted")
                    return results
        except Exception as e:
            self.logger.error(f"分页查询失败: {str(e)}")
            raise

    def get_total_count(self):
        try:
            with psycopg2.connect(**self.DB_CONFIG) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {self.table_name} WHERE topic_closed = FALSE AND is_deleted = FALSE;"
                    )
                    return cursor.fetchone()[0]
        except Exception as e:
            self.logger.error(f"总数查询失败: {str(e)}")
            raise

    def validate_update_data(self, data: List[Dict]) -> bool:
        for item in data:
            if "id" not in item:
                return False
            if not all(key in self.VALID_FIELDS for key in item if key != "id"):
                return False
        return True

    def update_pg_data(self, data_list: List[Dict[str, Any]]) -> int:
        if not data_list:
            return 0

        conn = None
        try:
            conn = psycopg2.connect(**self.DB_CONFIG)
            cursor = conn.cursor()

            # 过滤非法字段
            filtered_data = [
                {
                    "id": item["id"],
                    **{k: v for k, v in item.items() if k in self.VALID_FIELDS},
                }
                for item in data_list
            ]

            # 构建参数化查询语句
            set_clause = ", ".join([f"{field} = %s" for field in self.VALID_FIELDS])
            sql = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"

            # 生成参数列表
            params_list = [
                [item.get(field) for field in self.VALID_FIELDS] + [item["id"]]
                for item in filtered_data
            ]

            cursor.executemany(sql, params_list)
            conn.commit()
            return cursor.rowcount

        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error(f"批量更新失败: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

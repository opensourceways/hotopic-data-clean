import psycopg2
import sys
from config.settings import settings


def init_database():
    conn = None
    try:
        # 使用管理员连接创建数据库
        conn = psycopg2.connect(
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            host=settings.db_host,
            port=settings.db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # 创建数据库（带容错）
        cursor.execute(f"CREATE DATABASE {settings.db_name} ENCODING 'UTF8';")

        # 创建角色并授权（带存在性检查）
        cursor.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '{settings.db_user}') THEN
                    CREATE ROLE {settings.db_user} WITH LOGIN PASSWORD '{settings.db_password}';
                END IF;
            END
            $$;
            
            GRANT ALL PRIVILEGES ON DATABASE {settings.db_name} TO {settings.db_user};
        """)

        print("✅ 数据库初始化成功")

    except psycopg2.Error as e:
        print(f"❌ 数据库初始化失败: {str(e)}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

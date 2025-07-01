import asyncio
import json
import logging
from datetime import datetime, timedelta

from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor
from fastapi import FastAPI
from config.settings import settings
from app.data_collect_clean import collector, clean, validator
from app.data_manager import api
from app.db import base, init_db
from sqlalchemy.dialects.postgresql import insert, JSONB
from sqlalchemy import text, cast
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager

scheduler = BackgroundScheduler(
    timezone="UTC",
    executors={
        'default': ThreadPoolExecutor(4),
        'processpool': ProcessPoolExecutor(3)
    },
    job_defaults={
        'max_instances': 1,
        'misfire_grace_time': 120
    }
)

trigger = CronTrigger(
    hour='*/3',
    timezone="UTC",
    jitter=30  # 添加随机抖动，避免定点执行冲突
)


def scheduled_task():
    try:
        auto_process()
    except Exception as e:
        logging.error(f"Scheduled task failed: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    scheduler.add_job(
        scheduled_task,
        trigger=trigger,
        executor='default',
    )
    yield
    scheduler.shutdown()


app = FastAPI(
    lifespan=lifespan,
    title="数据清洗服务",
    description="提供数据清洗处理API",
    version="1.0.0"
)
app.include_router(api.router, prefix="/api/v1", tags=["webhooks"])


@app.get("/health", tags=["监控"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.env}


@app.post("/manual-run")
async def manual_trigger():
    await run_in_process(auto_process)
    return {"status": "manual run completed"}


async def run_in_process(func):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func)


def auto_process():
    """全自动执行采集+清洗"""
    initialize_processing_environment()
    clean_invalid_urls()

    try:
        start_time = calculate_start_time()
        raw_data = collect_data(start_time)
        store_processed_data(raw_data)
    except Exception as e:
        handle_processing_error(e)


def initialize_processing_environment():
    """初始化日志和数据库"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    init_db.init_database()
    base.check_and_create_tables()


def clean_invalid_urls():
    with base.SessionLocal() as session:
        try:
            records = session.query(base.Discussion).filter(
                base.Discussion.is_deleted == False  # 仅处理未删除记录
            )

            # 初始化验证器字典
            validators = {
                "issue": validator.IssueValidator(),
                "forum": validator.GetForumValidator(settings.community),
                "mail": validator.MailValidator()
            }

            update_count = 0
            for record in records:
                validator_for_type = validators.get(record.source_type.lower())
                if not validator_for_type:
                    continue

                if not validator_for_type.validate(record.url):
                    record.is_deleted = True
                    update_count += 1
                    logging.debug(f"标记删除URL: {record.url}")

            if update_count > 0:
                session.commit()
                logging.info(f"已标记 {update_count} 条无效URL记录")
            else:
                logging.info("未找到无效URL记录")

        except Exception as e:
            session.rollback()
            logging.error(f"清理失败: {str(e)}")
        finally:
            session.close()


def calculate_start_time() -> datetime:
    today = datetime.now()
    days_since_friday = (today.weekday() - 4) % 7  # 4代表周五的weekday索引
    last_friday = today - timedelta(days=days_since_friday)
    if days_since_friday == 0:
        last_friday -= timedelta(days=7)
    return last_friday.replace(hour=0, minute=0, second=0, microsecond=0)


def collect_data(start_time: datetime) -> list:
    """
    根据 settings.community 采集对应社区的数据。
    openubmc 采集 forum 和 issue，
    cann 采集 forum 和 mail，
    opengauss 采集 issue。
    """
    data = []
    community_map = {
        "openubmc": [
            ("forum", collector.get_forum_collector, clean.get_forum_cleaner),
            ("issue", lambda c: collector.IssueCollector(c, settings.dws_name), clean.get_issue_cleaner)
        ],
        "cann": [
            ("forum", collector.get_forum_collector, clean.get_forum_cleaner),
            ("issue", lambda c: collector.IssueCollector(c, settings.dws_name), clean.get_issue_cleaner)],
        "opengauss": [
            ("issue", lambda c: collector.IssueCollector(c, settings.dws_name), clean.get_issue_cleaner),
            ("mail", lambda c: collector.MailCollector(c, settings.mail_dws_name), clean.get_mail_cleaner)
        ],
        "mindspore": [
            ("issue", lambda c: collector.IssueCollector(c, settings.dws_name), clean.get_issue_cleaner),
            ("forum", collector.get_forum_collector, clean.get_forum_cleaner)
        ],
    }

    collectors = community_map.get(settings.community)
    if not collectors:
        logging.warning(f"未知的 community 类型: {settings.community}")
        return data

    for source_type, collector_func, cleaner_func in collectors:
        logging.debug(f"开始处理{source_type}数据")
        col = collector_func(settings.community)
        cleaner = cleaner_func(settings.community, col)
        cleaned_data = cleaner.process(start_time)
        data.extend([r.__dict__ for r in cleaned_data])

    return data


def store_processed_data(raw_data: list):
    """批量存储处理后的数据"""
    with base.SessionLocal() as session:
        try:
            BATCH_SIZE = 50
            for i in range(0, len(raw_data), BATCH_SIZE):
                process_batch(session, raw_data[i:i + BATCH_SIZE], i, BATCH_SIZE)
        except Exception as e:
            session.rollback()
            raise e


def process_batch(session, batch: list, index: int, batch_size: int):
    """处理单个数据批次"""
    for record in batch:
        if isinstance(clean_data := record['clean_data'], str) and clean_data.startswith('"'):
            try:
                record['clean_data'] = json.loads(clean_data)
            except json.JSONDecodeError:
                pass

        title, url = record['title'], record['url']
        logging.info(f"正在提交记录: {title} - {url}")
        session.execute(build_upsert_statement(record))

    session.commit()
    logging.info(f"已提交 {min(index + batch_size, len(batch))}/{len(batch)} 条数据")


def build_upsert_statement(record: dict):
    return insert(base.Discussion).values(
        source_id=record['source_id'],
        source_type=record['source_type'],
        title=record['title'],
        body=record['body'],
        url=record['url'],
        topic_summary=record['topic_summary'],
        topic_closed=record['topic_closed'],
        created_at=record['created_at'],
        updated_at=record['updated_at'],
        clean_data=record['clean_data'],
        history=record['history'],
        source_closed=record['source_closed'],
    ).on_conflict_do_update(
        index_elements=['source_id', 'source_type'],
        set_={
            # 'history': text(
            #     "history || jsonb_build_array(jsonb_build_object('title', EXCLUDED.title, 'body', EXCLUDED.body, 'time', NOW()::timestamp))"
            # ),
            'title': record['title'],
            'body': record['body'],
            'url': record['url'],
            'source_closed': record['source_closed'],
            'updated_at': record['updated_at'],
        }
    )


def handle_processing_error(e: Exception):
    """统一错误处理"""
    logging.error(f"执行失败: {str(e)}")

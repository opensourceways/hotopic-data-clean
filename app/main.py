import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI
from config.settings import settings
from app.data_collect_clean import collector, clean
from app.data_manager import api
from app.db import base, init_db
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


app = FastAPI(title="数据清洗服务",
              description="提供数据清洗处理API",
              version="1.0.0")
app.include_router(api.router, prefix="/api/v1", tags=["webhooks"])
scheduler = BackgroundScheduler()


@app.get("/health", tags=["监控"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.env}


@scheduler.scheduled_job(CronTrigger(day="fri", hour=14, minute=0))  # 每周五14:00执行
def scheduled_task():
    auto_process()


@app.on_event("startup")
async def startup_event():
    scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()


@app.post("/manual-run")
async def manual_trigger():
    auto_process()
    return {"status": "manual run completed"}


def auto_process():
    """全自动执行采集+清洗"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    init_db.init_database()
    base.check_and_create_tables()

    try:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7  # 4代表周五的weekday索引
        last_friday = today - timedelta(days=days_since_friday)
        if days_since_friday == 0:
            last_friday -= timedelta(days=7)
        start_time = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)

        # 执行所有采集器
        raw_data = []
        issue_collector = collector.IssueCollector(settings.community, settings.dws_name)
        issue_cleaner = clean.OpenUBMCIssueCleaner(issue_collector)
        cleaned_issue_data = issue_cleaner.process(start_time)

        forum_collector = collector.get_forum_collector(settings.community)
        forum_cleaner = clean.OpenUBMCForumCleaner(forum_collector)
        cleaned_forum_data = forum_cleaner.process(start_time)
        raw_data.extend(cleaned_issue_data)
        raw_data.extend(cleaned_forum_data)

        output_path = Path(__file__).parent.parent / "output" / "data.json"
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)
        logging.info(f"数据已成功导出至 {output_path}")

        with base.SessionLocal() as session:
            for record in raw_data:
                stmt = insert(base.Discussion).values(
                    source_id=record['source_id'],
                    source_type=record['source_type'],
                    title=record['title'],
                    body=record['body'],
                    url=record['url'],
                    topic_summary=record['topic_summary'],
                    topic_closed=record['topic_closed'],
                    created_at=record['created_at'],
                    clean_data=record['clean_data'],
                    history=record['history']
                ).on_conflict_do_update(
                    index_elements=['source_id'],
                    set_={
                        'history': text(
                            "history || jsonb_build_array(jsonb_build_object('title', EXCLUDED.title, 'body', EXCLUDED.body, 'time', NOW()::timestamp))"
                        ),
                        'title': record['title'],
                        'body': record['body'],
                        'time': datetime.now()
                    }
                )
                session.execute(stmt)
            session.commit()
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"执行失败: {str(e)}")

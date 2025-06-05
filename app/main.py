import logging
from datetime import datetime, timedelta
from fastapi import FastAPI
from config.settings import settings
from app.data_collect_clean import collector, clean


app = FastAPI(title="数据清洗服务",
              description="提供数据清洗处理API",
              version="1.0.0")


@app.get("/health", tags=["监控"])
async def health_check():
    return {
        "status": "ok",
        "environment": settings.env}


def main():
    """全自动执行采集+清洗"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    try:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7  # 4代表周五的weekday索引
        last_friday = today - timedelta(days=days_since_friday)
        # 如果是当天周五则取上周五
        if days_since_friday == 0:
            last_friday -= timedelta(days=7)
        start_time = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)

        # 执行所有采集器
        raw_data = []
        # issue_collector = collector.IssueCollector(settings.community, settings.dws_name)
        # issue_cleaner = clean.OpenUBMCIssueCleaner(issue_collector)
        # cleaned_issue_data = issue_cleaner.process(start_time)

        forum_collector = collector.OpenUBMCForumCollector()
        forum_cleaner = clean.OpenUBMCForumCleaner(forum_collector)
        cleaned_forum_data = forum_cleaner.process(start_time)
        # raw_data.extend(cleaned_issue_data)
        raw_data.extend(cleaned_forum_data)
        print(raw_data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logging.error(f"执行失败: {str(e)}")

if __name__ == "__main__":
    main()
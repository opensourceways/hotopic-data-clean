from datetime import datetime, timedelta

from app.data_manager.manager import DataManager
from fastapi import APIRouter, HTTPException, status, Body, Query
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
data_manager = DataManager()


@router.get("/data")
def get_data(
    page: int = Query(1, ge=1, description="分页页码"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量"),
):
    try:
        # 获取分页数据和总数
        result = data_manager.fetch_paginated_from_pg(page=page, page_size=page_size)
        total = data_manager.get_total_count()

        return {
            "status": "success",
            "data": result,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_items": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/latest")
def get_latest(
    page: int = Query(1, ge=1, description="分页页码"),
    page_size: int = Query(100, ge=1, le=500, description="每页数量"),
):
    try:
        today = datetime.now()
        days_since_friday = (today.weekday() - 4) % 7  # 4代表周五的weekday索引
        last_friday = today - timedelta(days=days_since_friday)
        if days_since_friday == 0:
            last_friday -= timedelta(days=7)
        last_friday_start = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)

        posts = data_manager.fetch_posts_created_after(last_friday_start, page, page_size)

        return {
            "status": "success",
            "data": posts,
            "since": last_friday_start.isoformat(),
        }
    except Exception as e:
        logger.error(f"获取上周五之后帖子失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

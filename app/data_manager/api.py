from datetime import datetime

from app.data_manager.manager import DataManager
from fastapi import APIRouter, HTTPException, status, Body, Query
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
data_manager = DataManager()


@router.get("/data")
def get_data(
        page: int = Query(1, ge=1, description="分页页码"),
        page_size: int = Query(100, ge=1, le=500, description="每页数量")
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
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/data")
def update_data(
        data: list = Body(..., embed=True, media_type="application/json"),  # 明确指定媒体类型和嵌入格式
        user: str = "admin"
):
    try:
        logger.info(f"[{datetime.now()}] 用户 {user} 发起更新，数量：{len(data)}")

        if not data_manager.validate_update_data(data):
            raise ValueError("包含非法字段或数据格式错误")

        affected_rows = data_manager.update_pg_data(data)
        return {
            "status": "success",
            "affected_rows": affected_rows,
            "failed_count": len(data) - affected_rows
        }
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"更新失败: {str(e)}")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
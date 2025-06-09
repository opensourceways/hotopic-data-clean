from app.data_manager.manager import DataManager
from fastapi import APIRouter, HTTPException, status
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
data_manager = DataManager()


@router.get("/data")
def get_data():
    try:
        result = data_manager.fetch_from_pg()
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/data")
def update_data(data: list):
    try:
        affected_rows = data_manager.update_pg_data(data)
        return {"status": "success", "affected_rows": affected_rows}
    except Exception as e:
        logger.error(f"更新失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

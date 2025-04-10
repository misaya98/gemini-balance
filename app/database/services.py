"""
数据库服务模块
"""
import datetime
import json
from typing import Dict, List, Optional, Any, Union
from datetime import date, timedelta # Import date and timedelta

from sqlalchemy import select, insert, update, func # Import func for COUNT

from app.database.connection import database
from app.database.models import Settings, ErrorLog
from app.log.logger import get_database_logger

logger = get_database_logger()


async def get_all_settings() -> List[Dict[str, Any]]:
    """
    获取所有设置
    
    Returns:
        List[Dict[str, Any]]: 设置列表
    """
    try:
        query = select(Settings)
        result = await database.fetch_all(query)
        return [dict(row) for row in result]
    except Exception as e:
        logger.error(f"Failed to get all settings: {str(e)}")
        raise


async def get_setting(key: str) -> Optional[Dict[str, Any]]:
    """
    获取指定键的设置
    
    Args:
        key: 设置键名
    
    Returns:
        Optional[Dict[str, Any]]: 设置信息，如果不存在则返回None
    """
    try:
        query = select(Settings).where(Settings.key == key)
        result = await database.fetch_one(query)
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {str(e)}")
        raise


async def update_setting(key: str, value: str, description: Optional[str] = None) -> bool:
    """
    更新设置
    
    Args:
        key: 设置键名
        value: 设置值
        description: 设置描述
    
    Returns:
        bool: 是否更新成功
    """
    try:
        # 检查设置是否存在
        setting = await get_setting(key)
        
        if setting:
            # 更新设置
            query = (
                update(Settings)
                .where(Settings.key == key)
                .values(
                    value=value,
                    description=description if description else setting["description"],
                    updated_at=datetime.datetime.now()
                )
            )
            await database.execute(query)
            logger.info(f"Updated setting: {key}")
            return True
        else:
            # 插入设置
            query = (
                insert(Settings)
                .values(
                    key=key,
                    value=value,
                    description=description,
                    created_at=datetime.datetime.now(),
                    updated_at=datetime.datetime.now()
                )
            )
            await database.execute(query)
            logger.info(f"Inserted setting: {key}")
            return True
    except Exception as e:
        logger.error(f"Failed to update setting {key}: {str(e)}")
        return False


async def add_error_log(
    gemini_key: Optional[str] = None,
    model_name: Optional[str] = None,
    error_type: Optional[str] = None,
    error_log: Optional[str] = None,
    error_code: Optional[int] = None,
    request_msg: Optional[Union[Dict[str, Any], str]] = None
) -> bool:
    """
    添加错误日志
    
    Args:
        gemini_key: Gemini API密钥
        error_log: 错误日志
        error_code: 错误代码 (例如 HTTP 状态码)
        request_msg: 请求消息
    
    Returns:
        bool: 是否添加成功
    """
    try:
        # 如果request_msg是字典，则转换为JSON字符串
        if isinstance(request_msg, dict):
            request_msg_json = request_msg
        elif isinstance(request_msg, str):
            try:
                request_msg_json = json.loads(request_msg)
            except json.JSONDecodeError:
                request_msg_json = {"message": request_msg}
        else:
            request_msg_json = None
        
        # 插入错误日志
        query = (
            insert(ErrorLog)
            .values(
                gemini_key=gemini_key,
                error_type=error_type,
                error_log=error_log,
                model_name=model_name,
                error_code=error_code,
                request_msg=request_msg_json,
                request_time=datetime.datetime.now()
            )
        )
        await database.execute(query)
        logger.info(f"Added error log for key: {gemini_key}")
        return True
    except Exception as e:
        logger.error(f"Failed to add error log: {str(e)}")
        return False


async def get_error_logs(
    limit: int = 20,
    offset: int = 0,
    key_search: Optional[str] = None,
    error_search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    """
    获取错误日志，支持搜索和日期过滤

    Args:
        limit (int): 限制数量
        offset (int): 偏移量
        key_search (Optional[str]): Gemini密钥搜索词 (模糊匹配)
        error_search (Optional[str]): 错误类型或日志内容搜索词 (模糊匹配)
        start_date (Optional[date]): 开始日期
        end_date (Optional[date]): 结束日期

    Returns:
        List[Dict[str, Any]]: 错误日志列表
    """
    try:
        query = select(ErrorLog)
        
        # Apply filters
        if key_search:
            query = query.where(ErrorLog.gemini_key.ilike(f"%{key_search}%"))
        if error_search:
            query = query.where(
                (ErrorLog.error_type.ilike(f"%{error_search}%")) |
                (ErrorLog.error_log.ilike(f"%{error_search}%"))
            )
        if start_date:
            query = query.where(ErrorLog.request_time >= start_date)
        if end_date:
            # Add 1 day to end_date to include the whole day
            query = query.where(ErrorLog.request_time < end_date + timedelta(days=1))

        # Apply ordering, limit, and offset
        query = query.order_by(ErrorLog.request_time.desc()).limit(limit).offset(offset)
        
        result = await database.fetch_all(query)
        return [dict(row) for row in result]
    except Exception as e:
        logger.exception(f"Failed to get error logs with filters: {str(e)}") # Use exception for stack trace
        raise


async def get_error_logs_count(
    key_search: Optional[str] = None,
    error_search: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> int:
    """
    获取符合条件的错误日志总数

    Args:
        key_search (Optional[str]): Gemini密钥搜索词 (模糊匹配)
        error_search (Optional[str]): 错误类型或日志内容搜索词 (模糊匹配)
        start_date (Optional[date]): 开始日期
        end_date (Optional[date]): 结束日期

    Returns:
        int: 日志总数
    """
    try:
        query = select(func.count()).select_from(ErrorLog)

        # Apply the same filters as get_error_logs
        if key_search:
            query = query.where(ErrorLog.gemini_key.ilike(f"%{key_search}%"))
        if error_search:
            query = query.where(
                (ErrorLog.error_type.ilike(f"%{error_search}%")) |
                (ErrorLog.error_log.ilike(f"%{error_search}%"))
            )
        if start_date:
            query = query.where(ErrorLog.request_time >= start_date)
        if end_date:
            query = query.where(ErrorLog.request_time < end_date + timedelta(days=1))

        count_result = await database.fetch_one(query)
        return count_result[0] if count_result else 0
    except Exception as e:
        logger.exception(f"Failed to count error logs with filters: {str(e)}") # Use exception for stack trace
        raise

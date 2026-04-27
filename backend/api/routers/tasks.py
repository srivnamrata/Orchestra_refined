import uuid
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Tasks"])


class TaskCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    subtasks: int = 0
    dependencies: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    subtasks: Optional[int] = None
    dependencies: Optional[str] = None


@router.post("/api/tasks")
async def create_task(task: TaskCreateRequest, user=Depends(get_current_user)):
    from backend.database import create_task_in_db
    try:
        task_id = str(uuid.uuid4())[:8]
        due_date_obj = None
        if task.due_date:
            try:
                due_date_obj = datetime.fromisoformat(task.due_date)
            except Exception:
                pass
        created_task = create_task_in_db(
            task_id=task_id,
            title=task.title,
            description=task.description,
            priority=task.priority,
            due_date=due_date_obj,
            subtasks=task.subtasks,
            dependencies=task.dependencies,
            user_id=user["user_id"],
        )
        logger.info(f"✅ Task created: {task_id}")
        return {
            "status":     "success",
            "task_id":    created_task.task_id,
            "title":      created_task.title,
            "priority":   created_task.priority,
            "created_at": created_task.created_at.isoformat(),
            "message":    "Task created successfully",
        }
    except Exception as e:
        logger.error(f"❌ Error creating task: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating task: {str(e)}")


@router.get("/api/tasks")
async def list_tasks(limit: int = 100, offset: int = 0,
                     status: Optional[str] = None, user=Depends(get_current_user)):
    from backend.database import get_all_tasks
    try:
        tasks = get_all_tasks(limit=limit, offset=offset, status=status,
                              user_id=user["user_id"])
        return {
            "status": "success",
            "count":  len(tasks),
            "tasks": [
                {
                    "task_id":     t.task_id,
                    "title":       t.title,
                    "description": t.description,
                    "priority":    t.priority,
                    "status":      t.status,
                    "due_date":    t.due_date.isoformat() if t.due_date else None,
                    "created_at":  t.created_at.isoformat(),
                    "subtasks":    t.subtasks,
                }
                for t in tasks
            ],
        }
    except Exception as e:
        logger.error(f"❌ Database error retrieving tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str, user=Depends(get_current_user)):
    from backend.database import get_task_by_id
    try:
        task = get_task_by_id(task_id)
        if not task or task.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return {
            "status": "success",
            "task": {
                "task_id":     task.task_id,
                "title":       task.title,
                "description": task.description,
                "priority":    task.priority,
                "status":      task.status,
                "due_date":    task.due_date.isoformat() if task.due_date else None,
                "created_at":  task.created_at.isoformat(),
                "updated_at":  task.updated_at.isoformat(),
                "subtasks":    task.subtasks,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving task: {str(e)}")


@router.put("/api/tasks/{task_id}")
async def update_task(task_id: str, updates: TaskUpdateRequest, user=Depends(get_current_user)):
    from backend.database import get_task_by_id, update_task as db_update_task
    try:
        task = get_task_by_id(task_id)
        if not task or task.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        kwargs = {}
        if updates.title is not None:        kwargs["title"]        = updates.title
        if updates.description is not None:  kwargs["description"]  = updates.description
        if updates.priority is not None:     kwargs["priority"]     = updates.priority
        if updates.status is not None:       kwargs["status"]       = updates.status
        if updates.subtasks is not None:     kwargs["subtasks"]     = updates.subtasks
        if updates.dependencies is not None: kwargs["dependencies"] = updates.dependencies
        if updates.due_date is not None:
            try:
                kwargs["due_date"] = datetime.fromisoformat(updates.due_date)
            except Exception:
                pass
        updated_task = db_update_task(task_id, **kwargs)
        logger.info(f"✅ Task updated: {task_id}")
        return {
            "status":     "success",
            "task_id":    updated_task.task_id,
            "title":      updated_task.title,
            "priority":   updated_task.priority,
            "updated_at": updated_task.updated_at.isoformat(),
            "message":    "Task updated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating task: {str(e)}")


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str, user=Depends(get_current_user)):
    from backend.database import get_task_by_id, delete_task as db_delete_task
    try:
        task = get_task_by_id(task_id)
        if not task or task.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        db_delete_task(task_id)
        logger.info(f"✅ Task deleted: {task_id}")
        return {"status": "success", "message": f"Task {task_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting task: {str(e)}")

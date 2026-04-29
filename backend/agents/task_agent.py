"""
Task Agent - Sub-agent for task management and execution
Handles task creation, assignment, tracking, and execution
"""

import asyncio
from typing import Dict, List, Any
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class TaskAgent:
    """
    Sub-agent specialized in task management operations.
    Handles:
    - Creating tasks
    - Assigning tasks to people
    - Tracking progress
    - Completing tasks
    - Managing dependencies
    """
    
    def __init__(self, knowledge_graph=None):
        self.knowledge_graph = knowledge_graph
        self.tasks = {}  # task_id -> task data
    
    async def execute(self, step: Dict[str, Any], previous_results: Dict) -> Dict[str, Any]:
        """
        Execute a task management step.
        Step types: "create_task", "assign_task", "update_task", "complete_task"
        """
        step_type = step.get("type")
        
        if step_type == "create_task":
            return await self._create_task(step)
        elif step_type == "assign_task":
            return await self._assign_task(step)
        elif step_type == "update_task":
            return await self._update_task(step)
        elif step_type == "complete_task":
            return await self._complete_task(step)
        else:
            raise ValueError(f"Unsupported step type: {step_type}")
    
    async def _create_task(self, step: Dict) -> Dict:
        """Create a new task"""
        
        title = step.get("inputs", {}).get("title")
        description = step.get("inputs", {}).get("description", "")
        priority = step.get("inputs", {}).get("priority", "medium")
        due_date = step.get("inputs", {}).get("due_date")
        depends_on = step.get("inputs", {}).get("depends_on", [])
        
        logger.info(f"Creating task: {title} (priority: {priority})")
        
        task_id = str(uuid.uuid4())[:12]
        
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "priority": priority,
            "due_date": due_date,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "assigned_to": None,
            "depends_on": depends_on,
            "completed_at": None
        }
        
        self.tasks[task_id] = task
        
        # Add to knowledge graph if available
        if self.knowledge_graph:
            await self.knowledge_graph.add_node(
                node_id=f"task-{task_id}",
                node_type="task",
                label=title,
                attributes={
                    "priority": priority,
                    "due_date": due_date,
                    "status": "open"
                }
            )
        
        return {
            "status": "success",
            "task_id": task_id,
            "title": title,
            "message": f"Task created with ID: {task_id}"
        }
    
    async def _assign_task(self, step: Dict) -> Dict:
        """Assign task to a person"""
        
        task_id = step.get("inputs", {}).get("task_id")
        assigned_to = step.get("inputs", {}).get("assigned_to")
        
        if not task_id or task_id not in self.tasks:
            raise ValueError(f"Task '{task_id}' not found")
        
        logger.info(f"Assigning task {task_id} to {assigned_to}")
        
        self.tasks[task_id]["assigned_to"] = assigned_to
        
        return {
            "status": "success",
            "task_id": task_id,
            "assigned_to": assigned_to,
            "message": f"Task assigned to {assigned_to}"
        }
    
    async def _update_task(self, step: Dict) -> Dict:
        """Update task details"""
        
        task_id = step.get("inputs", {}).get("task_id")
        updates = step.get("inputs", {}).get("updates", {})
        
        if not task_id or task_id not in self.tasks:
            raise ValueError(f"Task '{task_id}' not found")
        
        logger.info(f"Updating task {task_id}")
        
        # Update fields
        for key, value in updates.items():
            if key in self.tasks[task_id]:
                self.tasks[task_id][key] = value
        
        return {
            "status": "success",
            "task_id": task_id,
            "updated_fields": list(updates.keys()),
            "message": f"Task {task_id} updated successfully"
        }
    
    async def _complete_task(self, step: Dict) -> Dict:
        """Mark task as complete"""
        
        task_id = step.get("inputs", {}).get("task_id")
        
        if not task_id or task_id not in self.tasks:
            raise ValueError(f"Task '{task_id}' not found")
        
        logger.info(f"Completing task {task_id}")
        
        self.tasks[task_id]["status"] = "completed"
        self.tasks[task_id]["completed_at"] = datetime.now().isoformat()
        
        return {
            "status": "success",
            "task_id": task_id,
            "message": f"Task marked as completed"
        }
    
    def get_task(self, task_id: str) -> Dict:
        """Retrieve a task by ID"""
        return self.tasks.get(task_id)
    
    def get_tasks_by_status(self, status: str) -> List[Dict]:
        """Get all tasks with a specific status"""
        return [t for t in self.tasks.values() if t.get("status") == status]
    
    def get_tasks_by_priority(self, priority: str) -> List[Dict]:
        """Get all tasks with a specific priority"""
        return [t for t in self.tasks.values() if t.get("priority") == priority]

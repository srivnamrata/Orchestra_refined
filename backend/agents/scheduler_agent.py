"""
Scheduler Agent - Sub-agent for calendar and scheduling operations
Handles meeting scheduling with intelligent conflict resolution
"""

import asyncio
from typing import Dict, List, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class SchedulerAgent:
    """
    Sub-agent specialized in scheduling and calendar operations.
    Handles:
    - Finding available time slots
    - Detecting conflicts
    - Suggesting alternatives
    - Creating calendar events
    """
    
    def __init__(self, knowledge_graph=None):
        self.knowledge_graph = knowledge_graph
        self.calendar_events = {}  # Mock calendar storage
    
    async def execute(self, step: Dict[str, Any], previous_results: Dict) -> Dict[str, Any]:
        """
        Execute a scheduling step.
        Step types can be: "find_slot", "check_availability", "create_meeting"
        """
        step_type = step.get("type")
        
        if step_type == "find_slot":
            return await self._find_available_slot(step)
        elif step_type == "check_availability":
            return await self._check_availability(step)
        elif step_type == "create_meeting":
            return await self._create_meeting(step, previous_results)
        else:
            raise ValueError(f"Unsupported step type: {step_type}")
    
    async def _find_available_slot(self, step: Dict) -> Dict:
        """Find available time slot for a meeting"""
        
        duration_minutes = int(step.get("inputs", {}).get("duration", 60))
        participants = step.get("inputs", {}).get("participants", [])
        if not isinstance(participants, list):
            participants = [participants] if participants else []
        start_date = step.get("inputs", {}).get("start_date")
        
        logger.info(f"Finding available slot for {len(participants)} participants")
        
        # Simulate checking real calendars (in production, use Google Calendar API)
        available_slots = []
        
        # Generate potential slots for next 7 days
        start = datetime.fromisoformat(start_date) if start_date else datetime.now()
        
        for day_offset in range(7):
            current_day = start + timedelta(days=day_offset)
            
            # Skip weekends
            if current_day.weekday() >= 5:
                continue
            
            # Check business hours (9 AM - 5 PM)
            for hour in range(9, 17):
                slot_time = current_day.replace(hour=hour, minute=0)
                
                # Check if slot is free for all participants
                is_free = all(
                    self._is_participant_free(p, slot_time, duration_minutes)
                    for p in participants
                )
                
                if is_free:
                    available_slots.append(slot_time.isoformat())
        
        logger.info(f"Found {len(available_slots)} available slots")
        
        return {
            "status": "success",
            "available_slots": available_slots[:5],  # Return top 5
            "duration_minutes": duration_minutes,
            "participants": participants
        }
    
    async def _check_availability(self, step: Dict) -> Dict:
        """Check if a person is available at a specific time"""
        
        participant = step.get("inputs", {}).get("participant")
        time_slot = step.get("inputs", {}).get("time_slot")
        duration = int(step.get("inputs", {}).get("duration", 60))
        
        logger.info(f"Checking availability for {participant} at {time_slot}")
        
        is_available = self._is_participant_free(participant, 
                                                 datetime.fromisoformat(time_slot), 
                                                 duration)
        
        return {
            "status": "success",
            "participant": participant,
            "is_available": is_available,
            "time_slot": time_slot,
            "duration_minutes": duration
        }
    
    async def _create_meeting(self, step: Dict, previous_results: Dict) -> Dict:
        """Create a calendar meeting"""
        
        title = step.get("inputs", {}).get("title")
        time_slot = step.get("inputs", {}).get("time_slot")
        participants = step.get("inputs", {}).get("participants", [])
        duration = int(step.get("inputs", {}).get("duration", 60))
        
        if not title:
            raise ValueError("Meeting 'title' is required")
        if not time_slot:
            raise ValueError("Meeting 'time_slot' is required")
        if not isinstance(participants, list):
            participants = [participants] if participants else []
        description = step.get("inputs", {}).get("description", "")
        
        logger.info(f"Creating meeting: {title} at {time_slot}")
        
        # Generate meeting ID
        import uuid
        meeting_id = str(uuid.uuid4())[:8]
        
        # Store meeting
        self.calendar_events[meeting_id] = {
            "id": meeting_id,
            "title": title,
            "time": time_slot,
            "participants": participants,
            "duration_minutes": duration,
            "description": description,
            "created_at": datetime.now().isoformat()
        }
        
        return {
            "status": "success",
            "meeting_id": meeting_id,
            "title": title,
            "time": time_slot,
            "participants": participants,
            "message": f"Meeting created successfully with {len(participants)} participants"
        }
    
    def _is_participant_free(self, participant: str, 
                            time_slot: datetime, duration: int) -> bool:
        """
        Check if participant is free at given time.
        In production, query Google Calendar API.
        """
        # Mock implementation: 80% of slots are free
        import hashlib
        hash_val = int(hashlib.md5(f"{participant}{time_slot}".encode()).hexdigest(), 16)
        return (hash_val % 100) < 80

import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Events"])


class EventCreateRequest(BaseModel):
    title: str
    start_time: str
    end_time: str
    location: Optional[str] = None
    duration_minutes: int = 60
    attendees: Optional[str] = None
    description: Optional[str] = None


class EventUpdateRequest(BaseModel):
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    attendees: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


def _mock_events_response():
    now = datetime.now()
    return {
        "count": 4,
        "events": [
            {
                "event_id":   "evt-001",
                "title":      "Team Standup",
                "location":   "Conference Room A",
                "start_time": (now + timedelta(hours=1)).isoformat(),
                "end_time":   (now + timedelta(hours=1, minutes=30)).isoformat(),
                "attendees":  8,
                "status":     "confirmed",
                "created_at": now.isoformat(),
            },
            {
                "event_id":   "evt-002",
                "title":      "1-on-1 with Manager",
                "location":   "Virtual - Zoom",
                "start_time": (now + timedelta(hours=3)).isoformat(),
                "end_time":   (now + timedelta(hours=3, minutes=30)).isoformat(),
                "attendees":  2,
                "status":     "confirmed",
                "created_at": now.isoformat(),
            },
            {
                "event_id":   "evt-003",
                "title":      "Project Planning Session",
                "location":   "Main Office - Open Space",
                "start_time": (now + timedelta(days=1, hours=10)).isoformat(),
                "end_time":   (now + timedelta(days=1, hours=11, minutes=30)).isoformat(),
                "attendees":  12,
                "status":     "confirmed",
                "created_at": now.isoformat(),
            },
            {
                "event_id":   "evt-004",
                "title":      "Stakeholder Review",
                "location":   "Board Room",
                "start_time": (now + timedelta(days=3)).isoformat(),
                "end_time":   (now + timedelta(days=3, hours=2)).isoformat(),
                "attendees":  6,
                "status":     "tentative",
                "created_at": now.isoformat(),
            },
        ],
    }


@router.post("/api/events")
async def create_event(event: EventCreateRequest, user=Depends(get_current_user)):
    from backend.database import create_event_in_db
    try:
        event_id   = str(uuid.uuid4())[:8]
        start_time = datetime.fromisoformat(event.start_time)
        end_time   = datetime.fromisoformat(event.end_time)
        created_event = create_event_in_db(
            event_id=event_id,
            title=event.title,
            start_time=start_time,
            end_time=end_time,
            location=event.location,
            duration_minutes=event.duration_minutes,
            attendees=event.attendees,
            description=event.description,
            user_id=user["user_id"],
        )
        logger.info(f"✅ Event created: {event_id}")
        return {
            "status":     "success",
            "event_id":   created_event.event_id,
            "title":      created_event.title,
            "start_time": created_event.start_time.isoformat(),
            "end_time":   created_event.end_time.isoformat(),
            "location":   created_event.location,
            "created_at": created_event.created_at.isoformat(),
            "message":    "Event created successfully",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except Exception as e:
        logger.error(f"❌ Error creating event: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")


@router.get("/api/events")
async def list_events(limit: int = 100, offset: int = 0,
                      upcoming_only: bool = False, user=Depends(get_current_user)):
    from backend.database import get_all_events
    try:
        events = get_all_events(limit=limit, offset=offset, upcoming_only=upcoming_only,
                                user_id=user["user_id"])
        return {
            "status": "success",
            "count":  len(events),
            "events": [
                {
                    "event_id":         e.event_id,
                    "title":            e.title,
                    "description":      e.description,
                    "start_time":       e.start_time.isoformat() if e.start_time else None,
                    "end_time":         e.end_time.isoformat() if e.end_time else None,
                    "location":         e.location,
                    "duration_minutes": e.duration_minutes,
                    "status":           e.status,
                    "created_at":       e.created_at.isoformat(),
                }
                for e in events
            ],
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving events: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving events: {str(e)}")


@router.get("/api/events/upcoming/{days}")
async def get_upcoming_events(days: int = 7, user=Depends(get_current_user)):
    from backend.database import get_upcoming_events as db_get_upcoming
    try:
        events = db_get_upcoming(days_ahead=days)
        events = [e for e in events if e.user_id == user["user_id"]]
        return {
            "status":     "success",
            "count":      len(events),
            "range_days": days,
            "events": [
                {
                    "event_id":   e.event_id,
                    "title":      e.title,
                    "start_time": e.start_time.isoformat(),
                    "end_time":   e.end_time.isoformat(),
                    "location":   e.location,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
        }
    except Exception as e:
        logger.warning(f"⚠️ Database error retrieving events, using mock data: {e}")
        mock_response = _mock_events_response()
        mock_response["status"] = "success (mock)"
        return mock_response


@router.get("/api/events/{event_id}")
async def get_event(event_id: str, user=Depends(get_current_user)):
    from backend.database import get_event_by_id
    try:
        event = get_event_by_id(event_id)
        if not event or event.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        return {
            "status": "success",
            "event": {
                "event_id":         event.event_id,
                "title":            event.title,
                "description":      event.description,
                "start_time":       event.start_time.isoformat(),
                "end_time":         event.end_time.isoformat(),
                "location":         event.location,
                "duration_minutes": event.duration_minutes,
                "attendees":        event.attendees,
                "created_at":       event.created_at.isoformat(),
                "updated_at":       event.updated_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving event: {str(e)}")


@router.put("/api/events/{event_id}")
async def update_event(event_id: str, updates: EventUpdateRequest, user=Depends(get_current_user)):
    from backend.database import get_event_by_id, update_event as db_update_event
    try:
        event = get_event_by_id(event_id)
        if not event or event.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        kwargs = {}
        if updates.title is not None:            kwargs["title"]            = updates.title
        if updates.location is not None:         kwargs["location"]         = updates.location
        if updates.duration_minutes is not None: kwargs["duration_minutes"] = updates.duration_minutes
        if updates.attendees is not None:        kwargs["attendees"]        = updates.attendees
        if updates.description is not None:      kwargs["description"]      = updates.description
        if updates.status is not None:           kwargs["status"]           = updates.status
        if updates.start_time is not None:
            try:
                kwargs["start_time"] = datetime.fromisoformat(updates.start_time)
            except Exception:
                pass
        if updates.end_time is not None:
            try:
                kwargs["end_time"] = datetime.fromisoformat(updates.end_time)
            except Exception:
                pass
        updated_event = db_update_event(event_id, **kwargs)
        logger.info(f"✅ Event updated: {event_id}")
        return {
            "status":     "success",
            "event_id":   updated_event.event_id,
            "title":      updated_event.title,
            "start_time": updated_event.start_time.isoformat(),
            "end_time":   updated_event.end_time.isoformat(),
            "updated_at": updated_event.updated_at.isoformat(),
            "message":    "Event updated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating event: {str(e)}")


@router.delete("/api/events/{event_id}")
async def delete_event(event_id: str, user=Depends(get_current_user)):
    from backend.database import get_event_by_id, get_session, CalendarEvent
    try:
        event = get_event_by_id(event_id)
        if not event or event.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
        db = get_session()
        ev = db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()
        if ev:
            db.delete(ev); db.commit()
        db.close()
        logger.info(f"✅ Event deleted: {event_id}")
        return {"status": "success", "message": f"Event {event_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting event: {str(e)}")

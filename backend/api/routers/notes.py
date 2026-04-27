import uuid
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Notes"])


class NoteCreateRequest(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[str] = None


@router.post("/api/notes")
async def create_note(note: NoteCreateRequest, user=Depends(get_current_user)):
    from backend.database import create_note_in_db
    try:
        note_id = str(uuid.uuid4())[:8]
        created_note = create_note_in_db(
            note_id=note_id,
            title=note.title,
            content=note.content,
            category=note.category,
            tags=note.tags,
            user_id=user["user_id"],
        )
        logger.info(f"✅ Note created: {note_id}")
        return {
            "status":     "success",
            "note_id":    created_note.note_id,
            "title":      created_note.title,
            "category":   created_note.category,
            "created_at": created_note.created_at.isoformat(),
            "message":    "Note created successfully",
        }
    except Exception as e:
        logger.error(f"❌ Error creating note: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating note: {str(e)}")


@router.get("/api/notes")
async def list_notes(limit: int = 100, offset: int = 0,
                     category: Optional[str] = None, user=Depends(get_current_user)):
    from backend.database import get_all_notes
    try:
        notes = get_all_notes(limit=limit, offset=offset, category=category,
                              user_id=user["user_id"])
        return {
            "status": "success",
            "count":  len(notes),
            "notes": [
                {
                    "note_id":    n.note_id,
                    "title":      n.title,
                    "content":    n.content[:100] + "..." if len(n.content) > 100 else n.content,
                    "category":   n.category,
                    "tags":       n.tags,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notes
            ],
        }
    except Exception as e:
        logger.error(f"❌ Error retrieving notes: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving notes: {str(e)}")


@router.get("/api/notes/search/{query}")
async def search_notes(query: str, limit: int = 50, user=Depends(get_current_user)):
    from backend.database import search_notes as db_search_notes
    try:
        notes = db_search_notes(query, limit=limit)
        # Filter by user since search_notes doesn't accept user_id yet
        notes = [n for n in notes if n.user_id == user["user_id"]]
        return {
            "status": "success",
            "count":  len(notes),
            "query":  query,
            "notes": [
                {
                    "note_id":    n.note_id,
                    "title":      n.title,
                    "content":    n.content[:100] + "..." if len(n.content) > 100 else n.content,
                    "category":   n.category,
                    "created_at": n.created_at.isoformat(),
                }
                for n in notes
            ],
        }
    except Exception as e:
        logger.error(f"❌ Error searching notes: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching notes: {str(e)}")


@router.get("/api/notes/{note_id}")
async def get_note(note_id: str, user=Depends(get_current_user)):
    from backend.database import get_note_by_id
    try:
        note = get_note_by_id(note_id)
        if not note or note.user_id != user["user_id"]:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
        return {
            "status": "success",
            "note": {
                "note_id":    note.note_id,
                "title":      note.title,
                "content":    note.content,
                "category":   note.category,
                "tags":       note.tags,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving note {note_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving note: {str(e)}")

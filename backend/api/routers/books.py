import re
import uuid
import logging
from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api import state
from backend.auth.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class BookCreateRequest(BaseModel):
    title: str
    author: str = None
    total_pages: int = 300


@router.get("/api/books", tags=["Veda"])
async def get_books(status: str = None, user=Depends(get_current_user)):
    from backend.database import get_all_books
    books = get_all_books(status=status, user_id=user["user_id"])
    return [
        {
            "id":           b.book_id,
            "title":        b.title,
            "author":       b.author,
            "status":       b.status,
            "current_page": b.current_page,
            "total_pages":  b.total_pages,
            "pct":          int((b.current_page / b.total_pages) * 100) if b.total_pages > 0 else 0,
            "updated_at":   b.updated_at.isoformat(),
        }
        for b in books
    ]


@router.post("/api/books", tags=["Veda"])
async def create_book(data: Dict, user=Depends(get_current_user)):
    from backend.database import create_book_in_db
    b = create_book_in_db(
        book_id=f"book-{uuid.uuid4().hex[:6]}",
        title=data["title"],
        author=data.get("author"),
        total_pages=data.get("total_pages", 300),
        user_id=user["user_id"],
    )
    return {"status": "success", "id": b.book_id}


@router.post("/api/veda", tags=["Veda"])
async def veda_command(data: Dict, user=Depends(get_current_user)):
    """Natural language book management — regex fast-path + LLM fallback."""
    from backend.database import create_book_in_db, get_session, update_book_progress
    from backend.database import Book as BookModel

    text = data.get("text", "").strip()
    if not text:
        return {"status": "error", "message": "No text provided"}

    text_lower = text.lower()
    user_id    = user["user_id"]

    add_match = re.search(
        r"(?:add|reading|started?|begin|track)\s+[\"']?(.+?)[\"']?"
        r"(?:,?\s+(?:i.?m\s+on\s+)?page\s+(\d+))?\.?\s*$",
        text_lower,
    )
    page_match = re.search(
        r"(?:i.?m\s+on|on|page|at)\s+page\s+(\d+)\s+of\s+[\"']?(.+?)[\"']?\.?\s*$",
        text_lower,
    )
    update_match = re.search(
        r"[\"']?(.+?)[\"']?\s*[-,]\s*(?:page|pg\.?)\s+(\d+)",
        text_lower,
    )

    try:
        if add_match:
            raw_title = add_match.group(1).strip().title()
            page      = int(add_match.group(2)) if add_match.group(2) else None
            book_id   = f"book-{uuid.uuid4().hex[:6]}"
            b = create_book_in_db(
                book_id=book_id,
                title=raw_title,
                status="in-progress" if page else "to-read",
                total_pages=300,
                user_id=user_id,
            )
            if page:
                update_book_progress(book_id, page)
            msg = f"Added '{raw_title}' to your library" + (f" at page {page}." if page else ".")
            return {"status": "success", "result": {"message": msg, "book_id": book_id}}

        if page_match or update_match:
            m         = page_match or update_match
            page      = int(m.group(1)) if page_match else int(m.group(2))
            title_raw = (m.group(2) if page_match else m.group(1)).strip()
            db        = get_session()
            book      = db.query(BookModel).filter(
                BookModel.title.ilike(f"%{title_raw}%"),
                BookModel.user_id == user_id,
            ).first()
            db.close()
            if book:
                update_book_progress(book.book_id, page)
                pct = int(page / book.total_pages * 100) if book.total_pages else 0
                return {"status": "success", "result": {"message": f"Updated '{book.title}' to page {page} ({pct}%)."}}
            book_id = f"book-{uuid.uuid4().hex[:6]}"
            create_book_in_db(book_id=book_id, title=title_raw.title(),
                              status="in-progress", total_pages=300, user_id=user_id)
            update_book_progress(book_id, page)
            return {"status": "success", "result": {"message": f"Added '{title_raw.title()}' and set page to {page}."}}

    except Exception as e:
        logger.warning(f"Veda fast-path error: {e}")

    if state.veda_librarian:
        try:
            result = await state.veda_librarian.process_command(text)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Veda LLM error: {e}")

    return {"status": "error", "message": "Could not understand your request. Try: 'Add Atomic Habits, page 80'"}

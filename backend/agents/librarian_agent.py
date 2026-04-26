"""
Alexandria Agent — The Personal Librarian
=========================================
Manages your reading list, tracks page progress, and organizes your digital library.
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from backend.database import create_book_in_db, get_all_books, update_book_progress, Book

logger = logging.getLogger(__name__)

class LibrarianAgent:
    def __init__(self, llm_service):
        self.llm = llm_service

    async def process_command(self, text: str) -> Dict[str, Any]:
        """
        Parses natural language reading updates.
        Example: "Add Autobiography of a Yogi to my list. I am on page 369"
        """
        prompt = f"""You are Alexandria, the Librarian Agent. 
A user said: "{text}"

Extract the following information in JSON format:
{{
  "intent": "add" | "update" | "complete" | "status",
  "book_title": "Title of the book",
  "current_page": number | null,
  "total_pages": number | null,
  "author": "Author name" | null
}}

If the user is telling you their page number, intent is "update".
If they want to add a book, intent is "add".
"""
        try:
            raw = await self.llm.call(prompt)
            # Basic JSON extraction (assuming LLM returns clean JSON or markdown block)
            import json
            data = json.loads(raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip())
            
            return await self.execute_intent(data)
        except Exception as e:
            logger.error(f"Librarian error: {e}")
            return {"error": str(e), "message": "I couldn't quite process that book update."}

    async def execute_intent(self, data: Dict) -> Dict:
        intent = data.get("intent")
        title = data.get("book_title")
        
        if intent == "add":
            book_id = f"book-{uuid.uuid4().hex[:6]}"
            create_book_in_db(
                book_id=book_id,
                title=title,
                author=data.get("author"),
                status="in-progress" if data.get("current_page") else "to-read",
                total_pages=data.get("total_pages") or 300
            )
            if data.get("current_page"):
                update_book_progress(book_id, data.get("current_page"))
            
            return {
                "message": f"Added '{title}' to your library. Happy reading!",
                "book_id": book_id,
                "status": "success"
            }
            
        if intent == "update":
            # Find the book by title (case-insensitive)
            # In a real app, we'd use fuzzy matching or a vector search
            from backend.database import SessionLocal
            db = SessionLocal()
            book = db.query(Book).filter(Book.title.ilike(f"%{title}%")).first()
            db.close()
            
            if book:
                update_book_progress(book.book_id, data.get("current_page"), status="in-progress")
                pct = int((data.get("current_page") / book.total_pages) * 100) if book.total_pages else 0
                return {
                    "message": f"Progress updated for '{book.title}'. You are {pct}% through!",
                    "book_id": book.book_id,
                    "status": "success"
                }
            else:
                # If book not found, add it first
                return await self.execute_intent({**data, "intent": "add"})

        return {"message": "I'm ready to help with your books."}

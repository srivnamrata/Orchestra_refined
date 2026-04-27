import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from backend.agents.librarian_agent import LibrarianAgent

@pytest.mark.asyncio
async def test_process_command_insight_emits_event():
    """
    Tests that the 'insight' intent correctly parses input via LLM,
    fetches wisdom, and publishes the thought trace to the EventBus.
    """
    # 1. Setup mocks
    mock_llm = AsyncMock()
    # The first call parses the command, the second generates the actual insight
    mock_llm.call.side_effect = [
        json.dumps({
            "intent": "insight", 
            "book_title": "Atomic Habits", 
            "query": "habit loops"
        }),
        "The core of Atomic Habits is the 1% improvement compounding effect."
    ]
    
    mock_event_bus = AsyncMock()
    agent = LibrarianAgent(llm_service=mock_llm, event_bus=mock_event_bus)
    
    # 2. Execute the command
    result = await agent.process_command("What's a good insight on habit loops from Atomic Habits?")
    
    # 3. Assertions
    assert result["status"] == "success"
    assert result["intent"] == "insight"
    assert "compounding effect" in result["message"]
    
    # Verify the EventBus published the correct thought trace for the UI
    mock_event_bus.publish.assert_called_once_with("thought", {
        "agent": "knowledge",
        "role": "Veda",
        "message": "Deep-diving into 'Atomic Habits' for wisdom...",
        "type": "thought"
    })

@pytest.mark.asyncio
@patch("backend.agents.librarian_agent.create_book_in_db")
async def test_execute_intent_add(mock_create_db):
    """Verifies that the 'add' intent correctly calls the database creation helper."""
    mock_llm = AsyncMock()
    agent = LibrarianAgent(llm_service=mock_llm)
    
    data = {
        "intent": "add",
        "book_title": "The Alchemist",
        "author": "Paulo Coelho",
        "total_pages": 200
    }
    
    await agent.execute_intent(data)
    mock_create_db.assert_called_once()
    # Check that it passed the right data to the DB layer
    _, kwargs = mock_create_db.call_args
    assert kwargs["title"] == "The Alchemist"
    assert kwargs["author"] == "Paulo Coelho"

@pytest.mark.asyncio
async def test_process_command_failure_handling():
    """Ensures the agent handles LLM parsing errors gracefully."""
    mock_llm = AsyncMock()
    # Simulate an LLM returning garbage that parse_llm_json cannot handle
    mock_llm.call.return_value = "I am sorry Dave, I cannot do that."
    
    agent = LibrarianAgent(llm_service=mock_llm)
    
    # We expect the try/except block in process_command to catch the parsing error
    result = await agent.process_command("Invalid input")
    
    assert "error" in result
    assert result["message"] == "I couldn't quite process that book update."
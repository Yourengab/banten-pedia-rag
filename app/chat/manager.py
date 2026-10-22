"""
Chat session and message management.

Handles:
  - Create chat sessions
  - Store user/assistant messages
  - Retrieve chat history for context
"""

from __future__ import annotations

from typing import Any, cast

from database.supabase import supabase


def create_session() -> str:
    """Create a new chat session. Returns session_id."""
    response = supabase.table("chat_sessions").insert({}).execute()
    session_id: str = cast(dict[str, Any], response.data[0])["id"]
    return session_id


def add_message(session_id: str, role: str, content: str) -> str:
    """Add a message to a session. Returns message_id."""
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'.")

    response = supabase.table("chat_messages").insert({
        "session_id": session_id,
        "role": role,
        "content": content,
    }).execute()

    message_id: str = cast(dict[str, Any], response.data[0])["id"]
    return message_id


def get_session_history(session_id: str) -> list[dict[str, str]]:
    """
    Retrieve all messages in a session, ordered by creation time.
    Returns list of {role, content} dicts.
    """
    response = (
        supabase
        .table("chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def get_session_context(session_id: str, limit: int = 10) -> str:
    """
    Build a context string from recent messages for inclusion in agent prompt.
    Useful for maintaining conversation flow.
    """
    messages = get_session_history(session_id)
    # Keep only last N messages
    recent = messages[-limit:] if len(messages) > limit else messages

    if not recent:
        return ""

    lines = ["[CHAT HISTORY]"]
    for msg in recent:
        role = "👤 User" if msg["role"] == "user" else "🤖 Assistant"
        lines.append(f"{role}: {msg['content']}")
    lines.append("[END CHAT HISTORY]\n")

    return "\n".join(lines)

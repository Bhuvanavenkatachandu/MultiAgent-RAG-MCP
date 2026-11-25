"""Chat Task Lifecycle & Cancellation Manager.

Manages a single-active-chat-task lifecycle scoped per user/session.
Ensures that when a new chat or query begins:
- Previous active tasks for that session are immediately cancelled.
- Cancellation is propagated to streaming generators, LLM calls, and async operations.
- Stale responses, tokens, and background events from invalidated chats are rejected.
- Independent sessions and users are completely isolated and unaffected.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, NamedTuple, Optional

logger = logging.getLogger("mcp_using_langchain.task_manager")


class ActiveTaskRecord(NamedTuple):
    chat_id: str
    task: asyncio.Task
    cancel_event: asyncio.Event


class ChatTaskManager:
    """Thread-safe, async-safe task lifecycle manager for active chat executions."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # session_key -> ActiveTaskRecord
        self._active_tasks: Dict[str, ActiveTaskRecord] = {}
        # session_key -> current_chat_id (the single valid active chat generation for this session)
        self._current_chat_ids: Dict[str, str] = {}

    @staticmethod
    def get_session_key(session_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """Derives a distinct session key per user/session scope to prevent cross-session interference."""
        clean_user = (user_id or "web-user").strip()
        clean_session = (session_id or "web-session-default").strip()
        return f"{clean_user}:{clean_session}"

    async def cancel_active_task(
        self,
        session_key: str,
        new_chat_id: Optional[str] = None,
    ) -> Optional[str]:
        """Cancels any currently running task for the specified session.

        Args:
            session_key: Scoped user/session identifier.
            new_chat_id: Optional new chat ID to immediately activate, invalidating the previous one.

        Returns:
            The old chat ID that was cancelled, or None if no active task was running.
        """
        async with self._lock:
            # Update current active chat ID to invalidate late arrivals
            if new_chat_id:
                self._current_chat_ids[session_key] = new_chat_id
            elif session_key in self._current_chat_ids and not new_chat_id:
                # If explicit cancellation with no new chat ID, clear active chat
                self._current_chat_ids.pop(session_key, None)

            record = self._active_tasks.pop(session_key, None)
            if not record:
                return None

            old_chat_id = record.chat_id
            record.cancel_event.set()

            if record.task and not record.task.done():
                logger.info(
                    "Cancelling active chat task for session '%s' (chat_id: %s)...",
                    session_key,
                    old_chat_id,
                )
                record.task.cancel()
                try:
                    # Allow cancellation to propagate without blocking execution
                    await asyncio.sleep(0)
                except Exception:
                    pass

            return old_chat_id

    async def register_task(
        self,
        session_key: str,
        chat_id: str,
        task: asyncio.Task,
        cancel_event: asyncio.Event,
    ) -> None:
        """Registers a new active task for a session, cancelling any previous active task."""
        async with self._lock:
            old_record = self._active_tasks.get(session_key)
            if old_record:
                old_record.cancel_event.set()
                if old_record.task and not old_record.task.done() and old_record.task is not task:
                    logger.info(
                        "Cancelling superseded active task for session '%s' (old chat_id: %s)...",
                        session_key,
                        old_record.chat_id,
                    )
                    old_record.task.cancel()

            self._active_tasks[session_key] = ActiveTaskRecord(
                chat_id=chat_id,
                task=task,
                cancel_event=cancel_event,
            )
            self._current_chat_ids[session_key] = chat_id
            logger.debug("Registered new active chat task for session '%s' (chat_id: %s)", session_key, chat_id)

    async def unregister_task(self, session_key: str, chat_id: str) -> None:
        """Safely cleans up a completed or cancelled task from active registry."""
        async with self._lock:
            record = self._active_tasks.get(session_key)
            if record and record.chat_id == chat_id:
                self._active_tasks.pop(session_key, None)
                logger.debug("Unregistered active chat task for session '%s' (chat_id: %s)", session_key, chat_id)

    def is_chat_active(self, session_key: str, chat_id: str) -> bool:
        """Verifies whether the given chat_id is still the active, non-cancelled chat for this session."""
        valid_chat_id = self._current_chat_ids.get(session_key)
        if valid_chat_id is not None and valid_chat_id != chat_id:
            return False

        record = self._active_tasks.get(session_key)
        if record and record.chat_id == chat_id and record.cancel_event.is_set():
            return False

        return True

    def get_cancel_event(self, session_key: str, chat_id: str) -> Optional[asyncio.Event]:
        """Retrieves the cancellation event for the given active session task if present."""
        record = self._active_tasks.get(session_key)
        if record and record.chat_id == chat_id:
            return record.cancel_event
        return None


# Global singleton instance for application session task management
chat_task_manager = ChatTaskManager()

# tests/test_nodes.py
# Unit tests for every node in the pipeline.

import pytest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────
# intake_node
# ─────────────────────────────────────────────────────────────

class TestIntakeNode:

    def _state(self, msg: str) -> dict:
        return {"session_id": "test", "user_message": msg, "metadata": {}}

    def test_keyword_sets_retrieve_route(self):
        from nodes.intake_node import intake_node
        result = intake_node(self._state("Show me your LangGraph pipeline architecture"))
        assert result["route"] == "retrieve"

    def test_short_message_sets_direct_route(self):
        from nodes.intake_node import intake_node
        result = intake_node(self._state("Hi there"))
        assert result["route"] == "direct"

    def test_metadata_contains_intake_route(self):
        from nodes.intake_node import intake_node
        result = intake_node(self._state("hello"))
        assert "intake_route" in result["metadata"]

    def test_session_id_preserved(self):
        from nodes.intake_node import intake_node
        result = intake_node(self._state("hello"))
        assert result["session_id"] == "test"


# ─────────────────────────────────────────────────────────────
# context_node
# ─────────────────────────────────────────────────────────────

class TestContextNode:

    def _state(self, msg: str) -> dict:
        return {"session_id": "test", "user_message": msg, "metadata": {}}

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    def test_keyword_sets_needs_tools_true(self, _ctx, _hist):
        from nodes.context_node import context_node
        result = context_node(self._state("Show me your neo4j graph code"))
        assert result["needs_tools"] is True

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    def test_no_keyword_sets_needs_tools_false(self, _ctx, _hist):
        from nodes.context_node import context_node
        result = context_node(self._state("What do you enjoy doing?"))
        assert result["needs_tools"] is False

    @patch("nodes.context_node.load_history", return_value=[
        {"role": "user",      "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ])
    @patch("nodes.context_node.build_memory_context", return_value="You asked: hello")
    def test_history_loaded_into_messages(self, _ctx, _hist):
        from nodes.context_node import context_node
        result = context_node(self._state("follow up"))
        assert len(result["messages"]) == 2
        assert result["memory_context"] == "You asked: hello"

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    def test_metadata_populated(self, _ctx, _hist):
        from nodes.context_node import context_node
        result = context_node(self._state("hi"))
        assert "context_needs_tools" in result["metadata"]
        assert "context_seconds"     in result["metadata"]


# ─────────────────────────────────────────────────────────────
# bchat_node
# ─────────────────────────────────────────────────────────────

class TestBchatNode:

    def _mock_response(self, text: str):
        usage = MagicMock()
        usage.__iter__ = lambda _: iter({})
        r = MagicMock()
        r.content = [MagicMock(text=text)]
        r.usage   = usage
        return r

    def _state(self, msg="hi", memory="", code="", messages=None):
        return {
            "session_id":     "test",
            "user_message":   msg,
            "memory_context": memory,
            "code_context":   code,
            "messages":       messages or [],
            "metadata":       {},
        }

    @patch("nodes.bchat_node.build_system_prompt", return_value="sys")
    @patch("nodes.bchat_node._claude")
    def test_response_populated(self, mock_claude, _sys):
        mock_claude.messages.create.return_value = self._mock_response("I'm Bavish!")
        from nodes.bchat_node import bchat_node
        result = bchat_node(self._state())
        assert result["response"] == "I'm Bavish!"

    @patch("nodes.bchat_node.build_system_prompt", return_value="sys")
    @patch("nodes.bchat_node._claude")
    def test_used_tools_true_when_code_context_present(self, mock_claude, _sys):
        mock_claude.messages.create.return_value = self._mock_response("answer")
        from nodes.bchat_node import bchat_node
        result = bchat_node(self._state(code="some_snippet"))
        assert result["metadata"]["bchat_node_used_tools"] is True

    @patch("nodes.bchat_node.build_system_prompt", return_value="sys")
    @patch("nodes.bchat_node._claude")
    def test_used_tools_false_when_no_code_context(self, mock_claude, _sys):
        mock_claude.messages.create.return_value = self._mock_response("answer")
        from nodes.bchat_node import bchat_node
        result = bchat_node(self._state())
        assert result["metadata"]["bchat_node_used_tools"] is False

    @patch("nodes.bchat_node.build_system_prompt", return_value="sys")
    @patch("nodes.bchat_node._claude")
    def test_timing_in_metadata(self, mock_claude, _sys):
        mock_claude.messages.create.return_value = self._mock_response("ok")
        from nodes.bchat_node import bchat_node
        result = bchat_node(self._state())
        assert "bchat_node_seconds" in result["metadata"]


# ─────────────────────────────────────────────────────────────
# retrieval_node
# ─────────────────────────────────────────────────────────────

class TestRetrievalNode:

    def test_neo4j_disabled_returns_empty_context(self):
        from nodes.retrieval_node import retrieval_node
        state  = {"session_id": "s", "user_message": "show code", "metadata": {}}
        result = retrieval_node(state)
        assert result["code_context"] == ""
        assert result["tools_output"] == ""

    def test_metadata_populated(self):
        from nodes.retrieval_node import retrieval_node
        state  = {"session_id": "s", "user_message": "hi", "metadata": {}}
        result = retrieval_node(state)
        assert "retrieval_seconds" in result["metadata"]


# ─────────────────────────────────────────────────────────────
# persist_node
# ─────────────────────────────────────────────────────────────

class TestPersistNode:

    @patch("nodes.persist_node.save_turn")
    def test_saves_both_turns(self, mock_save):
        from nodes.persist_node import persist_node
        state = {
            "session_id":   "s",
            "user_message": "question",
            "response":     "answer",
            "metadata":     {},
        }
        persist_node(state)
        assert mock_save.call_count == 2

    @patch("nodes.persist_node.save_turn")
    def test_finalized_at_stamped(self, _save):
        from nodes.persist_node import persist_node
        state  = {"session_id": "s", "user_message": "q", "response": "a", "metadata": {}}
        result = persist_node(state)
        assert "finalized_at" in result["metadata"]

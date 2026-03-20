# tests/test_graph.py
# Integration tests for the full pipeline:
#   intake → context → (retrieval →) bchat → persist

import pytest
from unittest.mock import MagicMock, patch


def _mock_claude(text: str = "mocked answer"):
    usage = MagicMock()
    usage.__iter__ = lambda _: iter({})
    r = MagicMock()
    r.content = [MagicMock(text=text)]
    r.usage   = usage
    return r


def _base_state(msg: str, session: str = "test-session") -> dict:
    return {
        "session_id":   session,
        "user_message": msg,
        "messages":     [],
        "metadata":     {},
    }


# ─────────────────────────────────────────────────────────────
# Graph compilation
# ─────────────────────────────────────────────────────────────

class TestGraphBuild:

    def test_graph_compiles(self):
        from graph import compiled_graph
        assert compiled_graph is not None

    def test_graph_has_invoke(self):
        from graph import compiled_graph
        assert hasattr(compiled_graph, "invoke")


# ─────────────────────────────────────────────────────────────
# Direct path (no retrieval)
# ─────────────────────────────────────────────────────────────

class TestDirectPath:

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_simple_message_runs_end_to_end(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("Hi, I'm Bavish!")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("Hello"))
        assert result["response"] == "Hi, I'm Bavish!"

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_no_retrieval_flag_on_direct_path(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("answer")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("What is your name?"))
        assert result["metadata"].get("bchat_node_used_tools") is False


# ─────────────────────────────────────────────────────────────
# Retrieval path
# ─────────────────────────────────────────────────────────────

class TestRetrievalPath:

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_keyword_message_runs_end_to_end(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("Here is my pipeline")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("Show me your LangGraph pipeline architecture"))
        assert result["response"] == "Here is my pipeline"

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_metadata_has_all_node_timings(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("answer")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("Show me your neo4j code"))
        meta = result["metadata"]
        assert "context_seconds"    in meta
        assert "bchat_node_seconds" in meta
        assert "finalized_at"       in meta


# ─────────────────────────────────────────────────────────────
# State propagation
# ─────────────────────────────────────────────────────────────

class TestStatePropagation:

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_session_id_preserved(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("ok")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("hi", session="my-unique-id"))
        assert result["session_id"] == "my-unique-id"

    @patch("nodes.context_node.load_history",        return_value=[])
    @patch("nodes.context_node.build_memory_context", return_value="")
    @patch("nodes.bchat_node.build_system_prompt",     return_value="sys")
    @patch("nodes.bchat_node._claude")
    @patch("nodes.persist_node.save_turn")
    def test_user_message_preserved(self, _save, mock_claude, *_):
        mock_claude.messages.create.return_value = _mock_claude("ok")
        from graph import compiled_graph
        result = compiled_graph.invoke(_base_state("remember this question"))
        assert result["user_message"] == "remember this question"

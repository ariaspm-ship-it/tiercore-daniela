# tests/test_claude_agent.py
# Tests para el agente Claude (con mocks, sin llamadas reales)

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.claude_agent import DanielaAgent
from ai.context_builder import ContextBuilder


class TestClaudeAgent(unittest.TestCase):
    """Tests para el agente Claude - sin llamadas reales a API"""

    def setUp(self):
        self.patcher_anthropic = patch('ai.claude_agent.Anthropic')
        self.mock_anthropic = self.patcher_anthropic.start()

        self.mock_client = MagicMock()
        self.mock_anthropic.return_value = self.mock_client

        self.mock_response = MagicMock()
        self.mock_response.content = [MagicMock()]
        self.mock_response.content[0].text = "Respuesta de prueba de Claude"
        self.mock_client.messages.create.return_value = self.mock_response

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            self.agent = DanielaAgent()

    def tearDown(self):
        self.patcher_anthropic.stop()

    def test_initialization_with_api_key(self):
        self.assertIsNotNone(self.agent.client)
        self.assertTrue(self.agent.model.startswith("claude-sonnet"))

    def test_initialization_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            agent_no_key = DanielaAgent()
            self.assertIsNone(agent_no_key.client)

    def test_build_messages_structure(self):
        messages = self.agent._build_messages("consulta de prueba", include_realtime=True)

        self.assertGreaterEqual(len(messages), 1)
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], "consulta de prueba")

    def test_build_messages_without_context(self):
        messages = self.agent._build_messages("consulta de prueba", include_realtime=False)

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "consulta de prueba")

    def test_chat_successful(self):
        response = self.agent.chat("como estan los chillers?")

        self.mock_client.messages.create.assert_called_once()

        call_kwargs = self.mock_client.messages.create.call_args[1]
        self.assertEqual(call_kwargs["max_tokens"], 1000)
        self.assertEqual(call_kwargs["temperature"], 0.3)
        self.assertIn("messages", call_kwargs)
        self.assertIn("system", call_kwargs)

        self.assertEqual(response, "Respuesta de prueba de Claude")

    def test_chat_rate_limit(self):
        self.mock_client.messages.create.side_effect = Exception("RateLimit")
        response = self.agent.chat("consulta con rate limit")
        self.assertIsInstance(response, str)

    def test_mock_response_generation(self):
        agent_mock = DanielaAgent()
        agent_mock.client = None

        response = agent_mock.chat("como estan los chillers")
        self.assertIsInstance(response, str)
        self.assertIn("chiller", response.lower())

    def test_get_capabilities(self):
        caps = self.agent.get_capabilities()

        self.assertIn("model", caps)
        self.assertIn("capabilities", caps)
        self.assertIn("max_tokens", caps)

    def test_context_builder_integration(self):
        self.assertIsNotNone(self.agent.context_builder)
        self.assertIsInstance(self.agent.context_builder, ContextBuilder)


class TestContextBuilder(unittest.TestCase):
    """Tests para el constructor de contexto"""

    def setUp(self):
        self.cb = ContextBuilder()

    def test_get_realtime_context(self):
        context = self.cb.get_realtime_context(force_refresh=True)

        self.assertIn("timestamp", context)
        self.assertIn("property", context)

    def test_get_realtime_context_cache(self):
        context_1 = self.cb.get_realtime_context()
        context_2 = self.cb.get_realtime_context()

        self.assertIs(context_1, context_2)

    def test_get_formatted_context(self):
        formatted = self.cb.get_formatted_context()

        self.assertIsInstance(formatted, str)
        self.assertIn("RESORT STATUS", formatted)
        self.assertIn("Property:", formatted)


if __name__ == '__main__':
    unittest.main()

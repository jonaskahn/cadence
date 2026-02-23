"""API tests for the chat controller.

Verifies that the synchronous chat endpoint accepts valid requests, validates
input, delegates to OrchestratorService, and returns correctly shaped responses.
Authentication and org context are handled by the conftest dependency override.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

VALID_CHAT_PAYLOAD = {
    "instance_id": "inst_test",
    "message": "Hello",
    "conversation_id": None,
}

CHAT_SYNC_URL = "/api/orgs/org_test/completion/chat"


# ---------------------------------------------------------------------------
# POST /api/orgs/{org_id}/completion/chat
# ---------------------------------------------------------------------------


class TestChatSyncEndpoint:
    """Tests for POST /api/orgs/{org_id}/completion/chat (non-streaming chat)."""

    def test_returns_200_for_valid_request(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat returns HTTP 200 when all required fields are provided."""
        response = client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        assert response.status_code == 200

    def test_response_contains_session_id(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat response body includes a 'session_id' field."""
        response = client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        assert "session_id" in response.json()

    def test_response_contains_response_field(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat response body includes a 'response' field with the AI reply."""
        response = client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        assert "response" in response.json()

    def test_response_contains_agent_hops(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat response body includes 'agent_hops' from the orchestrator."""
        response = client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        assert "agent_hops" in response.json()

    def test_delegates_to_orchestrator_service(
        self, client: TestClient, mock_orchestrator_service: MagicMock
    ) -> None:
        """POST /api/orgs/{org_id}/completion/chat invokes OrchestratorService.process_chat once per request."""
        client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        mock_orchestrator_service.process_chat.assert_awaited_once()

    def test_passes_instance_id_from_request_body(
        self, client: TestClient, mock_orchestrator_service: MagicMock
    ) -> None:
        """POST /api/orgs/{org_id}/completion/chat forwards instance_id from the request body to the service."""
        client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        call_kwargs = mock_orchestrator_service.process_chat.call_args.kwargs
        assert call_kwargs["instance_id"] == "inst_test"

    def test_passes_message_from_request_body(
        self, client: TestClient, mock_orchestrator_service: MagicMock
    ) -> None:
        """POST /api/orgs/{org_id}/completion/chat forwards the user message to the service."""
        client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        call_kwargs = mock_orchestrator_service.process_chat.call_args.kwargs
        assert call_kwargs["message"] == "Hello"

    def test_passes_org_id_from_tenant_context(
        self, client: TestClient, mock_orchestrator_service: MagicMock
    ) -> None:
        """POST /api/orgs/{org_id}/completion/chat extracts org_id from the tenant context and passes it."""
        client.post(CHAT_SYNC_URL, json=VALID_CHAT_PAYLOAD)

        call_kwargs = mock_orchestrator_service.process_chat.call_args.kwargs
        assert call_kwargs["org_id"] == "org_test"

    def test_forwards_existing_conversation_id(
        self, client: TestClient, mock_orchestrator_service: MagicMock
    ) -> None:
        """POST /api/orgs/{org_id}/completion/chat passes an existing conversation_id to resume the conversation."""
        payload = {**VALID_CHAT_PAYLOAD, "conversation_id": "conv_existing"}

        client.post(CHAT_SYNC_URL, json=payload)

        call_kwargs = mock_orchestrator_service.process_chat.call_args.kwargs
        assert call_kwargs["conversation_id"] == "conv_existing"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


class TestChatSyncValidation:
    """Tests for POST /api/orgs/{org_id}/completion/chat request body validation."""

    def test_returns_422_when_message_is_missing(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat returns HTTP 422 when the 'message' field is absent."""
        payload = {"instance_id": "inst_test"}

        response = client.post(CHAT_SYNC_URL, json=payload)

        assert response.status_code == 422

    def test_returns_422_when_instance_id_is_missing(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat returns HTTP 422 when the 'instance_id' field is absent."""
        payload = {"message": "Hello"}

        response = client.post(CHAT_SYNC_URL, json=payload)

        assert response.status_code == 422

    def test_returns_422_for_empty_body(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat returns HTTP 422 when an empty JSON body is submitted."""
        response = client.post(CHAT_SYNC_URL, json={})

        assert response.status_code == 422

    def test_accepts_null_conversation_id(self, client: TestClient) -> None:
        """POST /api/orgs/{org_id}/completion/chat accepts null as a valid value for the optional conversation_id."""
        payload = {
            "instance_id": "inst_test",
            "message": "Hi",
            "conversation_id": None,
        }

        response = client.post(CHAT_SYNC_URL, json=payload)

        assert response.status_code == 200

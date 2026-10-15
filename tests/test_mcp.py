import unittest
from unittest.mock import patch

from ship_a_big_mac.mcp import MCPClient, MCPError


class MCPDecodeTests(unittest.TestCase):
    def test_json_response(self) -> None:
        parsed = MCPClient._decode(b'{"jsonrpc":"2.0","result":{"ok":true}}', "application/json")
        self.assertTrue(parsed["result"]["ok"])

    def test_sse_response(self) -> None:
        body = b'event: message\ndata: {"jsonrpc":"2.0","result":{"tools":[]}}\n\n'
        parsed = MCPClient._decode(body, "text/event-stream")
        self.assertEqual(parsed["result"]["tools"], [])

    def test_empty_sse_rejected(self) -> None:
        with self.assertRaises(MCPError):
            MCPClient._decode(b"event: ping\n\n", "text/event-stream")

    def test_sse_multiline_data_and_matching_response(self) -> None:
        body = (
            b': keepalive\r\n\r\n'
            b'data: {"jsonrpc":"2.0","method":"notifications/progress"}\r\n\r\n'
            b'data: {"jsonrpc":"2.0","id":9,"result":{}}\r\n\r\n'
            b'event: message\r\ndata: {"jsonrpc":"2.0",\r\n'
            b'data: "id":1,"result":{"tools":[]}}\r\n\r\n'
        )
        parsed = MCPClient._decode(body, "text/event-stream", 1)
        self.assertEqual(parsed["result"], {"tools": []})

    def test_json_response_must_match_request_id(self) -> None:
        for response_id in (b'2', b'"1"', b'true', b'null'):
            with self.subTest(response_id=response_id), self.assertRaisesRegex(MCPError, "id"):
                MCPClient._decode(
                    b'{"jsonrpc":"2.0","id":' + response_id + b',"result":{}}',
                    "application/json",
                    1,
                )

    def test_sse_missing_matching_response_rejected(self) -> None:
        with self.assertRaisesRegex(MCPError, "matching response"):
            MCPClient._decode(b'data: {"id":2,"result":{}}\n\n', "text/event-stream", 1)


class OpenStream:
    """A stream that must be closed before reading beyond its response event."""

    def __init__(self, lines: list[bytes]) -> None:
        self.headers = {"Content-Type": "text/event-stream", "Mcp-Session-Id": "session"}
        self.lines = lines
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def __iter__(self):
        yield from self.lines
        raise AssertionError("Client waited for EOF after the response was available")

    def read(self):
        raise AssertionError("Client tried to read a live event stream to EOF")


class MCPClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MCPClient(token="private-token")

    @patch("ship_a_big_mac.mcp.urlopen")
    def test_post_returns_matching_sse_response_before_eof(self, urlopen) -> None:
        response = OpenStream([
            b'data: {"id":7,"result":{"ignored":true}}\n', b'\n',
            b'data: {"method":"notifications/progress"}\n', b'\n',
            b'data: {"id":1,\n', b'data: "result":{"tools":[]}}\n', b'\n',
        ])
        urlopen.return_value = response
        self.assertEqual(self.client.list_tools(), [])
        self.assertTrue(response.closed)
        self.assertEqual(self.client.session_id, "session")

    @patch("ship_a_big_mac.mcp.urlopen")
    def test_notification_does_not_wait_for_a_response_body(self, urlopen) -> None:
        response = OpenStream([])
        urlopen.return_value = response
        self.assertIsNone(self.client._post({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertTrue(response.closed)

    def test_list_tools_follows_pagination(self) -> None:
        with patch.object(self.client, "_post", side_effect=[
            {"result": {"tools": [{"name": "first"}], "nextCursor": "page-2"}},
            {"result": {"tools": [{"name": "second"}]}},
        ]) as post:
            self.assertEqual(self.client.list_tools(), [{"name": "first"}, {"name": "second"}])
        first, second = (call.args[0] for call in post.call_args_list)
        self.assertEqual(first["params"], {})
        self.assertEqual(second["params"], {"cursor": "page-2"})
        self.assertNotEqual(first["id"], second["id"])

    def test_list_tools_rejects_repeated_cursor(self) -> None:
        with patch.object(self.client, "_post", return_value={
            "result": {"tools": [], "nextCursor": "same-page"}
        }) as post:
            with self.assertRaisesRegex(MCPError, "repeated cursor"):
                self.client.list_tools()
        self.assertEqual(post.call_count, 2)

    def test_tool_error_does_not_echo_sensitive_content(self) -> None:
        with patch.object(self.client, "_post", return_value={
            "result": {"isError": True, "content": [{"type": "text", "text": "private-token customer-data"}]}
        }):
            with self.assertRaisesRegex(MCPError, "tool reported an error: calculate-price") as error:
                self.client.call_tool("calculate-price", {})
        self.assertNotIn("private-token", str(error.exception))
        self.assertNotIn("customer-data", str(error.exception))

    def test_tool_success_preserves_result(self) -> None:
        result = {"isError": False, "content": [{"type": "text", "text": "quote"}]}
        with patch.object(self.client, "_post", return_value={"result": result}):
            self.assertEqual(self.client.call_tool("calculate-price", {}), result)

    def test_invalid_tool_result_rejected(self) -> None:
        with patch.object(self.client, "_post", return_value={"result": ["private-token"]}):
            with self.assertRaisesRegex(MCPError, "invalid result"):
                self.client.call_tool("calculate-price", {})


if __name__ == "__main__":
    unittest.main()

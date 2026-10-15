import unittest

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


if __name__ == "__main__":
    unittest.main()

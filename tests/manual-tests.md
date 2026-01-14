# initialize

```json
{"jsonrpc": "2.0","id": 1,"method": "initialize","params": {"protocolVersion": "2025-06-18","capabilities": {},"clientInfo": {"name": "test-client", "version": "0.1"}}}
```

# get_verse_by_caption (after initialize)

```json
{"jsonrpc": "2.0","id": 1,"method": "initialize","params": {"protocolVersion": "2025-06-18","capabilities": {},"clientInfo": {"name": "test-client", "version": "0.1"}}}
{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_verse_by_caption","arguments":{"caption": "Jn 1:1"}}}
```

# get_notion_by_id (after initialize)

```json
{"jsonrpc": "2.0","id": 1,"method": "initialize","params": {"protocolVersion": "2025-06-18","capabilities": {},"clientInfo": {"name": "test-client", "version": "0.1"}}}
{"jsonrpc":"2.0","id":"1","method":"tools/call","params":{"name":"get_notion_by_id","arguments":{"id": 40964128}}}
```
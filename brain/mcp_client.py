
import asyncio
import json
import logging
import os
import sys

logger = logging.getLogger("shell_mcp_client")

class MCPClient:
    """
    A generic MCP Client that communicates with MCP Servers over Stdio.
    Supports JSON-RPC 2.0.
    """
    def __init__(self, command: list[str], name: str = "generic_mcp"):
        self.command = command
        self.name = name
        self.process = None
        self.request_id = 1
        self.pending_requests = {}
        self.tools = []

    async def connect(self):
        """Starts the MCP Server process."""
        try:
            logger.info(f"🔌 Connecting to MCP Server [{self.name}] via {self.command}...")
            
            # Using asyncio subprocess for non-blocking I/O
            self.process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Start reader loop
            asyncio.create_task(self._reader_loop())
            
            # Initialize handshake
            await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ShellLogic", "version": "1.0"}
            })
            
            # Wait for initialized notification (optional depending on strictness)
            await self._send_notification("notifications/initialized", {})
            
            logger.info(f"✅ Connected to {self.name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection Failed to {self.name}: {e}")
            return False

    async def list_tools(self):
        """Fetches available tools from the server."""
        try:
            response = await self._send_request("tools/list", {})
            if response and "tools" in response:
                self.tools = response["tools"]
                logger.info(f"🛠️ {self.name} offers {len(self.tools)} tools.")
                return self.tools
            return []
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict):
        """Calls a tool on the server."""
        try:
            logger.info(f"🔧 Calling Tool {tool_name} on {self.name}...")
            response = await self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            return response
        except Exception as e:
            logger.error(f"Tool Call Error: {e}")
            return {"error": str(e)}

    async def _send_request(self, method: str, params: dict):
        """Sends a JSON-RPC Request."""
        if not self.process:
            raise Exception("MCP Client not connected")
            
        rid = self.request_id
        self.request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params
        }
        
        future = asyncio.Future()
        self.pending_requests[rid] = future
        
        line = json.dumps(payload) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()
        
        # Wait for response
        return await future

    async def _send_notification(self, method: str, params: dict):
        """Sends a JSON-RPC Notification (no ID)."""
        if not self.process: return
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }
        
        line = json.dumps(payload) + "\n"
        self.process.stdin.write(line.encode())
        await self.process.stdin.drain()

    async def _reader_loop(self):
        """Reads stdout from the MCP server."""
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    logger.warning(f"⚠️ {self.name} process closed stdout.")
                    break
                    
                line_str = line.decode().strip()
                if not line_str: continue
                
                # Parse JSON-RPC
                try:
                    msg = json.loads(line_str)
                    
                    # Handle Response
                    if "id" in msg and msg["id"] in self.pending_requests:
                        future = self.pending_requests.pop(msg["id"])
                        if "error" in msg:
                            future.set_exception(Exception(msg["error"]))
                        else:
                            future.set_result(msg.get("result"))
                            
                    # Handle Notifications (Log for now)
                    elif "method" in msg:
                        # notifications/log
                        pass
                        
                except json.JSONDecodeError:
                    pass # Ignore non-JSON logs from stderr mixed in (rare)
                    
            except Exception as e:
                logger.error(f"Reader Loop Error: {e}")
                break

"""Prueba real de initialize/tools/list/tools/call sobre stdio (SDK opcional)."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Instalar extra [mcp] para probar protocolo')
class McpProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_initialization_and_tools(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        root = Path(__file__).resolve().parents[1]
        parameters = StdioServerParameters(command=sys.executable,
            args=['-m','egobits.mcp_server'], cwd=str(root),
            env={**os.environ, 'PYTHONPATH':str(root), 'EGB_LIBRARY_XML':str(root/'examples/library.xml'),
                 'EGB_ENERGIES_JSON':str(root/'examples/energies.json')})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                self.assertEqual(len(names), 15)
                self.assertIn('collection.execute',names)
                result=await client.call_tool('collection.execute',{'name':'collection.query','arguments':{'limit':2}})
                self.assertFalse(result.isError)
                result=await client.call_tool('collection.execute',{'name':'playlist.apply_native','arguments':{}})
                self.assertTrue(result.isError)
                self.assertNotIn('playlist.apply_native', names)
                result = await client.call_tool('playlist.list', {})
                self.assertFalse(result.isError)
                result = await client.call_tool('playlist.plan', {'playlists':['ROOT/X','ROOT/Y'],'count':4})
                self.assertFalse(result.isError)
                result = await client.call_tool('playlist.plan', {'playlists':['no existe'],'count':4})
                self.assertTrue(result.isError)

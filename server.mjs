import express from 'express';
import { StreamableHttpServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { spawn } from 'child_process';

const app = express();
app.use(express.json());

// 1. Health check for Claude auto-discovery
app.get('/', (req, res) => {
  res.status(200).send('MCP Server Active');
});

// 2. Streamable HTTP endpoint for Claude Web
app.all('/mcp', async (req, res) => {
  const mcpProcess = spawn('mcp-server-github', [], {
    env: process.env,
    stdio: ['pipe', 'pipe', 'inherit']
  });

  const transport = new StreamableHttpServerTransport(req, res);
  
  // Connect MCP SDK transport to GitHub binary stdio
  mcpProcess.stdout.pipe(transport.outboundStream);
  transport.inboundStream.pipe(mcpProcess.stdin);

  req.on('close', () => mcpProcess.kill());
});

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`MCP HTTP Bridge running on port ${PORT}`);
});

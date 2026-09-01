FROM node:20-alpine

WORKDIR /app

# Install proxy and GitHub MCP server
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Map the proxy endpoint to root '/' for both Streamable HTTP and SSE
CMD ["mcp-proxy", "--port", "8080", "--endpoint", "/", "--command", "mcp-server-github"]

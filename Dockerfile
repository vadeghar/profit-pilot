FROM node:22-alpine

WORKDIR /app

# Install mcp-proxy and official GitHub MCP server globally
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Execute the mcp-server-github binary
CMD ["mcp-proxy", "--port", "8080", "--server", "stream", "--command", "mcp-server-github"]
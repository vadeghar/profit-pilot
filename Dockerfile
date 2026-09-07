FROM node:20-alpine

WORKDIR /app

# Install mcp-proxy and GitHub MCP server globally
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Expose Streamable HTTP transport natively via mcp-proxy
CMD ["mcp-proxy", "--port", "8080", "--server", "stream", "--command", "mcp-server-github"]
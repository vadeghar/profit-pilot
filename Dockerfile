FROM node:22-alpine

WORKDIR /app

# Install mcp-proxy and official GitHub MCP server globally
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github-official

EXPOSE 8080
ENV PORT=8080

# Execute the updated binary mcp-server-github-official
CMD ["mcp-proxy", "--port", "8080", "--server", "stream", "--command", "mcp-server-github-official"]
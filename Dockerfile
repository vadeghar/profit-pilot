FROM node:20-alpine

WORKDIR /app

# Install the proxy and official GitHub MCP server globally
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Run mcp-proxy directly against the installed binary target
CMD ["mcp-proxy", "--port", "8080", "--command", "mcp-server-github"]

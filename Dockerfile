FROM node:20-alpine

WORKDIR /app

# Install proxy and GitHub MCP server
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Configure mcp-proxy with explicit port binding
CMD ["mcp-proxy", "--port", "8080", "--command", "mcp-server-github"]

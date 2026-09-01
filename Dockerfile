FROM node:20-alpine

WORKDIR /app

# Install the proxy and official GitHub MCP server globally
RUN npm install -g mcp-proxy @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Execute mcp-proxy using individual argument flags
CMD ["mcp-proxy", "--port", "8080", "--command", "npx", "--args", "-y", "--args", "@modelcontextprotocol/server-github"]

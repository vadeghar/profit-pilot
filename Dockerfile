FROM node:18-alpine

WORKDIR /app

# Install the official GitHub server AND an SSE proxy adapter
RUN npm install -g @modelcontextprotocol/server-github mcp-proxy

EXPOSE 8080
ENV PORT=8080

# Run mcp-proxy to translate SSE HTTP connections on port 8080 to stdio
CMD ["mcp-proxy", "--port", "8080", "--command", "npx", "--args", "@modelcontextprotocol/server-github"]

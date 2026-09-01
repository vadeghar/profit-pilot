FROM node:20-alpine

WORKDIR /app

# Install the official GitHub MCP server globally
RUN npm install -g @modelcontextprotocol/server-github

EXPOSE 8080
ENV PORT=8080

# Execute the official GitHub MCP server directly over SSE transport
CMD ["npx", "@modelcontextprotocol/server-github", "--transport", "sse", "--port", "8080"]

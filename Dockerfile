FROM node:20-alpine

WORKDIR /app

# Install dependencies & github MCP server binary
RUN npm install express @modelcontextprotocol/sdk @modelcontextprotocol/server-github -g
ENV NODE_PATH=/usr/local/lib/node_modules

COPY server.mjs ./

EXPOSE 8080
ENV PORT=8080

CMD ["node", "server.mjs"]

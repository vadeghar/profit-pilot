FROM node:20-alpine

WORKDIR /app

# Create package.json and install packages locally
RUN npm init -y && \
    npm install express @modelcontextprotocol/sdk @modelcontextprotocol/server-github

# Expose globally installed binaries (like mcp-server-github) to PATH
ENV PATH="/app/node_modules/.bin:${PATH}"

COPY server.mjs ./

EXPOSE 8080
ENV PORT=8080

CMD ["node", "server.mjs"]

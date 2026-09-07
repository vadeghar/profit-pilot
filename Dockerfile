FROM node:20-alpine

WORKDIR /app

# Create package.json to enable module resolution
RUN npm init -y && \
    npm pkg set type="module" && \
    npm install express @modelcontextprotocol/sdk @modelcontextprotocol/server-github

COPY server.mjs ./

EXPOSE 8080
ENV PORT=8080

CMD ["node", "server.mjs"]
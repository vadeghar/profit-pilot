FROM node:18-alpine
WORKDIR /app
RUN npm install -g @modelcontextprotocol/server-github
EXPOSE 8080
ENV PORT=8080
CMD ["npx", "@modelcontextprotocol/server-github", "--transport", "sse"]

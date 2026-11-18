FROM node:22-alpine

ENV HOST=0.0.0.0 PORT=8000 BROWSER=none
WORKDIR /app

COPY --chown=node:node . .
RUN chown node:node /app
USER node
RUN npm ci --no-audit --no-fund

EXPOSE 8000
CMD ["npm", "start"]

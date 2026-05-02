FROM node:20-slim

WORKDIR /app

COPY desktopApp/package.json /app/package.json
RUN npm install

COPY desktopApp/ /app/
# Same markdown bundle HITL loads from assets/includes/ (Gemini preamble + desktop stack mirror)
COPY trade-blotter-hitl-agent/assets/includes/ /app/hitl-policy/

EXPOSE 5173

CMD ["npm", "start"]

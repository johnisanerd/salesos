FROM node:20-alpine

WORKDIR /app

COPY apps/dashboard/package.json ./package.json
RUN npm install

CMD ["npm", "run", "dev"]

FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json .
RUN npm ci
COPY index.html .
COPY postcss.config.js tailwind.config.js ./
COPY src ./src

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

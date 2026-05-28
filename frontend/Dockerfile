FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
ENV PORT=80 \
    BACKEND_URL=http://backend:8000

COPY --from=build /app/dist /usr/share/nginx/html
# nginx:alpine's entrypoint runs envsubst on /etc/nginx/templates/*.template at
# container start and writes the rendered file to /etc/nginx/conf.d/, overriding
# the bundled default.conf.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

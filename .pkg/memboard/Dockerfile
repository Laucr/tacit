FROM node:22-alpine AS build

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN VITE_BASE_PATH=/memboard/ npm run build

FROM nginx:alpine
COPY --from=build /build/dist /usr/share/nginx/html/memboard
RUN printf 'server {\n\
    listen 80;\n\
    location /memboard/ {\n\
        alias /usr/share/nginx/html/memboard/;\n\
        try_files $uri $uri/ /memboard/index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80

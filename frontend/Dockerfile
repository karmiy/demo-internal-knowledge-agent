FROM docker.m.daocloud.io/library/node:22-alpine AS build

WORKDIR /app
COPY package.json ./
ARG NPM_REGISTRY=https://nexus-xmn02.int.rclabenv.com/nexus/content/groups/npm-all/
ENV npm_config_registry=${NPM_REGISTRY}
RUN npm config get registry && npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

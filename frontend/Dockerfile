FROM docker.m.daocloud.io/library/node:22-alpine AS build

WORKDIR /app
ARG NPM_REGISTRY=https://nexus-xmn02.int.rclabenv.com/nexus/content/groups/npm-all/
ENV npm_config_registry=${NPM_REGISTRY}
RUN npm install --global pnpm@11.3.0 --no-audit --no-fund
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm config set registry "${NPM_REGISTRY}" && pnpm install --frozen-lockfile
COPY . .
RUN pnpm run build

FROM docker.m.daocloud.io/library/nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

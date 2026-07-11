# 新手友好 README 改版设计

## 目标

让不了解 Docker 的读者能够只看 README 完成 Demo 的首次启动、状态确认、日志查看、停止和再次启动，同时理解这些命令是否会删除数据。

## 内容结构

保留现有项目介绍、能力、安全设计、验证方法和公司网络说明。重写“快速启动”区域，并按实际操作顺序组织：

1. 说明 Docker Compose 会根据 `docker-compose.yml` 统一管理前端、后端、Ingest Worker 和 PostgreSQL。
2. 创建并填写 `.env`。
3. 使用 `docker compose up -d --build` 完成首次构建和后台启动。
4. 使用 `docker compose ps` 检查服务，并打开前端与 API 文档。
5. 使用 `docker compose logs -f` 查看日志，并说明如何退出日志查看。
6. 使用 `docker compose stop` 暂停服务，使用 `docker compose start` 恢复。
7. 说明 `docker compose down` 会移除容器和网络但保留数据库卷。
8. 明确警告 `docker compose down -v` 会删除本地数据库数据。

## 表达原则

- 操作优先，每条命令紧跟一句通俗解释。
- 首次启动与日常启动分开，避免每次都误以为必须重新构建。
- 避免把 README 扩写成完整 Docker 教程，只解释完成 Demo 所需概念。
- 保留端口冲突处理和公司网络镜像说明。

## 验收标准

- 新用户可以通过一个命令启动全部四项服务。
- README 明确写出停止、恢复、查看状态和查看日志的命令。
- README 清楚区分 `stop`、`down` 和 `down -v` 对容器及数据的影响。
- 所有 Markdown 代码块和链接保持有效，Compose 命令与当前配置一致。

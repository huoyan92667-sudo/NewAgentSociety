# 会话数据库

这一层保存会话、每轮问答、必要的执行事实、当前工作记忆、旧话题摘要、
模型消耗和大结果索引。评论向量不放在这里。

本地数据库由独立项目自己的启动文件管理：

```powershell
docker compose -f infra/docker-compose.yml up -d postgres
```

默认地址是 `localhost:5434`。连接信息写在项目根目录 `.env`，不要写进代码。

建表或升级：

```powershell
python -m alembic `
  -c src/new_agent/persistence/alembic.ini `
  upgrade head
```

当前共有八张业务表：会话、轮次、过程事实、业务状态版本、大结果索引、
模型调用、当前工作记忆和旧话题摘要。表的具体用途与保留规则见
`docs/development-log.md`。

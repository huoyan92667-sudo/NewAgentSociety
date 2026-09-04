# 运行入口

这里放可以直接执行的入口。正式业务实现必须留在 `src/new_agent`，这里的文件只负责
读取参数并调用正式入口。

- `chat.py`：发起真实单轮或多轮对话；
- `migrate_runtime_data.py`：从旧工程复制在线需要的数据，逐文件校验；
- `verify_runtime_data.py`：核对新目录已有数据的文件摘要和记录数；
- `import_review_index.py`：用已校验的评论片段与向量建立新 Qdrant 评论库。

Qdrant 的数据库目录不能在服务运行时直接复制。先迁评论索引，再通过导入程序重建，
这样比热复制一个 7GB 以上的数据库目录更安全。

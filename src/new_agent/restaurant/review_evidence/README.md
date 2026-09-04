# 评论证据能力

这个目录对上层只提供两种完整能力：

1. 根据当前软要求给硬筛后的餐厅重排，并返回前五证据；
2. 根据餐厅编号和用户想查证的意思，寻找具体评论证据。

上层不需要知道内部用了按意思查找、按关键词查找、两路名次合并、评论去重
还是离线 14 项画像。以后替换检索办法，不需要改 Agent 的工具调用方式。

固定 14 项优先读取 `data/runtime/restaurants/aspect_profiles/v1` 中的离线结果；
固定项以外的自由要求才会延迟启动本地向量模型和 Qdrant。自由要求的正反
查找说法由模型一次生成，检索只在指定餐厅编号范围内进行。

正式运行数据位于：

```text
data/runtime/reviews/reviews.parquet       完整评论
data/runtime/reviews/index/                评论片段和本地向量
data/runtime/qdrant/                       Qdrant 数据
configs/review_retrieval.yaml              检索配置
```

大文件不提交 Git。如何迁移、怎样验证、历次召回与速度对比统一记录在
`docs/development-log.md` 和 `docs/experiments/`。

当前自由要求的初始参数是：粗召回门槛 0.55、接受门槛 0.60、正反差值 0.05、
时间减半周期 730 天、每侧最终保留 5 条证据。这些是实验起点，不是假定的真理。

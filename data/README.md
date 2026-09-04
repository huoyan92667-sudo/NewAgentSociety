# 数据目录

`runtime` 只放在线 Agent 真正读取的数据；`training` 放教师数据、学生数据和离线打分
过程；`benchmarks` 放召回与回答测试集；`raw` 放可选的 Yelp 原始数据。

大文件不会提交 Git。迁移程序必须校验文件大小、摘要值和记录数量，不能只看到文件存在
就认为迁移成功。

```text
data/
├─ runtime/
│  ├─ restaurants/       商家事实、类别表、500 家固定特征
│  ├─ reviews/           完整评论、片段和本地向量
│  ├─ users/             长期画像
│  ├─ postgres/          会话数据库，不进 Git
│  └─ qdrant/            评论检索数据库，不进 Git
├─ training/
│  └─ review_judge/      教师标注、学生训练集和共同输入规范
├─ benchmarks/
│  └─ review_retrieval/  召回标准答案、逐条标签和方法对比
└─ experiments/          尚未成为正式测评集的中间实验数据
```

`runtime/verification_manifest.json` 记录当前在线文件的摘要和记录数。大文件本身即使
不进入 Git，也必须能通过 `run/migrate_runtime_data.py` 迁移并用
`run/verify_runtime_data.py` 复查。

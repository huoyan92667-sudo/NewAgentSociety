# 500 家餐厅的固定 14 项软偏好画像

这一层保存离线算好的商家程度、证据充分程度、争议程度和代表性评论。
正式推荐只通过 `BusinessAspectProfileCatalog` 读取，不直接依赖数据库表结构。

运行数据放在：

```text
data/runtime/restaurants/aspect_profiles/v1/
├─ business_aspect_profiles.sqlite3
├─ aspect_directions.json
├─ supported_businesses.json
└─ manifest.json
```

`strength=0` 表示该特征客观程度最低，`strength=4` 表示最高。例如安静程度越大
越安静，拥挤程度越大越拥挤，等位时间越大等得越久。用户想要相反方向时，
程序使用 `1 - degree` 转换，不重复训练另一套方向。

正式排序不能只看程度。证据越少，结果越要向“未知”收缩：

```text
用于排序的满足程度
= 0.5 +（按用户方向转换后的程度 - 0.5）× 证据充分程度
```

`usable_for_ranking=false` 时按未知处理；争议程度留给最终回答说明风险。
数据库如何从服务器结果生成属于离线数据工程，迁移记录放在
`docs/development-log.md`，不混进在线启动流程。

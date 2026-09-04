"""不依赖任何业务的基础数据结构。

这里只保留所有模块确实共同需要的内容，避免把旧项目整份模型文件复制进来。
"""

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """拒绝未声明字段，防止模型输出或工具参数被悄悄忽略。"""

    model_config = ConfigDict(extra="forbid")


class LocationCenter(StrictModel):
    """用户长期活动中心或一次搜索使用的经纬度。"""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


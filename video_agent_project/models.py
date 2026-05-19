"""

组内 JSON 协议：发布任务（Pydantic 校验）。

"""

from datetime import datetime, timezone

from enum import Enum

from pathlib import Path

from typing import Optional



from pydantic import BaseModel, Field, field_validator



import config





def utc_now() -> str:

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")





class TaskStatus(str, Enum):

    PENDING = "pending"

    RUNNING = "running"

    SUCCESS = "success"

    FAILED = "failed"





class PublishTask(BaseModel):

    """current_task.json 结构"""



    video_path: str = Field(..., description="相对项目根的路径，如 ready_to_publish/foo.mp4")

    title: str

    tags: str = ""

    status: TaskStatus = TaskStatus.PENDING

    updated_at: str = Field(default_factory=utc_now)

    error: Optional[str] = None

    video_url: Optional[str] = None

    video_id: Optional[str] = None

    platform: Optional[str] = None



    @field_validator("video_path")

    @classmethod

    def normalize_path(cls, v: str) -> str:

        p = Path(v)

        if p.is_absolute():

            try:

                return p.resolve().relative_to(config.PROJECT_ROOT.resolve()).as_posix()

            except ValueError:

                return str(p.resolve()).replace("\\", "/")

        return v.replace("\\", "/")



    def resolve_video_path(self) -> Path:

        p = Path(self.video_path)

        if p.is_absolute():

            return p

        return (config.PROJECT_ROOT / p).resolve()



    def touch(self, **kwargs) -> "PublishTask":

        data = self.model_dump()

        data.update(kwargs)

        data["updated_at"] = utc_now()

        return PublishTask(**data)





class PublishedVideoRecord(BaseModel):

    """

    第一组 -> 第二组 交接记录（写入 outbox/published_videos.jsonl）。

    第二组请只处理 video_url 非空的行；按 published_at 排序消费。

    """



    platform: str = Field(..., description="平台标识，如 douyin")

    video_url: str = Field(..., description="作品页 URL，第二组抓评论入口")

    video_id: Optional[str] = Field(None, description="从 URL 解析的平台作品 ID")

    title: str

    tags: str = ""

    local_stem: str = Field(..., description="本地素材文件名（无扩展名）")

    published_at: str = Field(..., description="UTC ISO8601")

    source: str = Field(default="group1_publish")

    monitor_status: str = Field(

        default="pending",

        description="第二组回填：pending | monitoring | done",

    )



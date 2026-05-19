"""第一组异常类型（学生 2 数据层 + 学生 1 发布层共用）。"""


class PublisherBaseError(Exception):
    """发布模块基础异常。"""


class ScanError(PublisherBaseError):
    """扫描 / 读取本地素材失败。"""


class ValidationError(PublisherBaseError):
    """素材或任务 JSON 校验失败。"""


class PublishError(PublisherBaseError):
    """浏览器发布流程失败。"""

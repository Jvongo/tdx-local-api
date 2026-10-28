"""tdx_service 统一错误体系：所有业务错误携带 code/http_status/message 三要素。"""


class AppError(Exception):
    """应用错误基类：携带错误码 code、HTTP 状态码 http_status 与消息 message。"""

    def __init__(self, message, code, http_status):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status


class ParamError(AppError):
    """参数校验失败错误：code=40001，HTTP 400。"""

    def __init__(self, message="参数校验失败"):
        super().__init__(message, code=40001, http_status=400)


class SecurityNotFound(AppError):
    """证券不存在或无数据错误：code=40401，HTTP 404。"""

    def __init__(self, message="证券不存在或无数据"):
        super().__init__(message, code=40401, http_status=404)


class NoDataInRange(AppError):
    """日期范围内无数据错误：code=40402，HTTP 404。"""

    def __init__(self, message="日期范围内无数据"):
        super().__init__(message, code=40402, http_status=404)


class DataFileError(AppError):
    """行情数据文件不存在或读取失败错误：code=50001，HTTP 500。"""

    def __init__(self, message):
        super().__init__(message, code=50001, http_status=500)


class DataRootUnavailable(AppError):
    """行情数据目录不可用错误：code=50301，HTTP 503。"""

    def __init__(self, message="行情数据目录不可用"):
        super().__init__(message, code=50301, http_status=503)

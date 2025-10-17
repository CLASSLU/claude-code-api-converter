"""
专业日志管理系统
支持开发和生产环境的不同日志级别
确保日志输出不会导致异常
"""

import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime
from typing import Any, Dict, Optional, Union
from pathlib import Path


class SafeLogger:
    """安全的日志记录器，防止日志输出导致异常"""

    def __init__(self, name: str = "api_server", config: Dict = None):
        self.name = name
        self.config = config or {}
        self.level = self._get_log_level()
        self.log_to_file = self._get_log_to_file()
        self.logger = self._setup_logger()

    def _get_log_level(self) -> str:
        """从配置获取日志级别"""
        if 'level' in self.config:
            return self.config['level']
        return os.getenv('LOG_LEVEL', 'DEBUG' if os.getenv('FLASK_ENV') == 'development' else 'INFO')

    def _get_log_to_file(self) -> bool:
        """从配置获取是否记录到文件"""
        if 'log_to_file' in self.config:
            return bool(self.config['log_to_file'])
        return os.getenv('FLASK_ENV') == 'development' or os.getenv('LOG_TO_FILE', 'false').lower() == 'true'

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(self.name)
        logger.setLevel(getattr(logging, self.level.upper(), logging.INFO))

        # 清除现有的处理器
        logger.handlers.clear()

        # 创建格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台处理器（强制UTF-8编码，尽量避免GBK乱码）
        console_handler = logging.StreamHandler(sys.stdout)
        try:
            # Windows系统特殊处理
            if sys.platform == 'win32':
                # 尝试设置控制台编码为UTF-8
                import locale
                try:
                    # 保存原来的编码设置
                    original_encoding = locale.getencoding()
                    # 设置为UTF-8
                    locale.setlocale(locale.LC_ALL, 'UTF-8')
                except locale.Error:
                    pass
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # 如果reconfigure失败，尝试直接设置编码
            try:
                if hasattr(console_handler.stream, 'encoding'):
                    console_handler.stream.encoding = 'utf-8'
            except Exception:
                pass
        console_handler.setLevel(getattr(logging, self.level.upper(), logging.INFO))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件处理器（仅在开发环境或明确启用时）
        if self._should_log_to_file():
            file_handler = self._create_file_handler(formatter)
            if file_handler:
                logger.addHandler(file_handler)

        return logger

    def _should_log_to_file(self) -> bool:
        """判断是否应该输出到文件"""
        return self.log_to_file

    def _create_file_handler(self, formatter: logging.Formatter) -> Optional[logging.Handler]:
        """创建文件处理器"""
        try:
            # 确保日志目录存在
            log_dir = Path('logs')
            log_dir.mkdir(exist_ok=True)

            # 按日期创建日志文件
            today = datetime.now().strftime('%Y-%m-%d')
            log_file = log_dir / f'api_server_{today}.log'

            # 使用配置的文件大小和备份数量
            max_size = self.config.get('max_file_size', 10*1024*1024)  # 默认10MB
            backup_count = self.config.get('backup_count', 5)  # 默认5个备份

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
            file_handler.setFormatter(formatter)

            return file_handler

        except Exception as e:
            # 如果创建文件处理器失败，记录到控制台但不中断程序
            print(f"Warning: Failed to create file handler: {e}")
            return None

    def _safe_format(self, message: Any, *args, **kwargs) -> str:
        """安全格式化消息，防止格式化异常 - 使用UTF-8编码支持中文"""
        try:
            if isinstance(message, (dict, list)):
                # 使用UTF-8编码，支持中文字符正常显示
                message = json.dumps(message, ensure_ascii=False, default=str)
            elif not isinstance(message, str):
                message = str(message)

            if args or kwargs:
                return message.format(*args, **kwargs)
            return message

        except Exception:
            # 格式化失败时返回原始消息
            return str(message)

    def debug(self, message: Any, *args, **kwargs):
        """记录调试信息"""
        try:
            formatted_msg = self._safe_format(message, *args, **kwargs)
            self.logger.debug(formatted_msg)
        except Exception:
            pass  # 静默处理日志异常

    def info(self, message: Any, *args, **kwargs):
        """记录一般信息"""
        try:
            formatted_msg = self._safe_format(message, *args, **kwargs)
            self.logger.info(formatted_msg)
        except Exception:
            pass

    def warning(self, message: Any, *args, **kwargs):
        """记录警告信息"""
        try:
            formatted_msg = self._safe_format(message, *args, **kwargs)
            self.logger.warning(formatted_msg)
        except Exception:
            pass

    def error(self, message: Any, *args, **kwargs):
        """记录错误信息"""
        try:
            formatted_msg = self._safe_format(message, *args, **kwargs)
            self.logger.error(formatted_msg)
        except Exception:
            pass

    def critical(self, message: Any, *args, **kwargs):
        """记录严重错误信息"""
        try:
            formatted_msg = self._safe_format(message, *args, **kwargs)
            self.logger.critical(formatted_msg)
        except Exception:
            pass

    def log_request(self, method: str, path: str, client_ip: str,
                   headers: Optional[Dict] = None, body: Optional[Any] = None, request_id: str = None):
        """记录HTTP请求"""
        try:
            # 基础请求信息在INFO级别记录
            prefix = f"[{request_id}] " if request_id else ""
            self.info(
                "{}HTTP Request - Method: {}, Path: {}, Client: {}".format(prefix, method, path, client_ip)
            )

            # 详细信息在DEBUG级别记录
            if headers:
                safe_headers = {k: v for k, v in headers.items()
                              if k.lower() not in ['authorization', 'cookie', 'x-api-key']}
                self.debug("{}Request Headers: {}", prefix, json.dumps(safe_headers, ensure_ascii=False))

            if body:
                try:
                    if isinstance(body, dict):
                        safe_body = {k: v for k, v in body.items()
                                   if k not in ['password', 'token', 'api_key']}
                        self.debug("{}Request Body: {}", prefix, json.dumps(safe_body, ensure_ascii=False))
                    else:
                        self.debug("{}Request Body: {}", prefix, str(body)[:500])
                except Exception:
                    self.debug("{}Request Body: [Unable to serialize]", prefix)

        except Exception:
            pass

    def log_response(self, status_code: int, response_data: Optional[Any] = None):
        """记录HTTP响应"""
        try:
            self.info("HTTP Response - Status: {}", status_code)

            if response_data:
                try:
                    if isinstance(response_data, (dict, list)):
                        safe_response = json.dumps(response_data, ensure_ascii=False, default=str)
                        self.debug("Response Body: {}", safe_response[:1000])
                    else:
                        self.debug("Response Body: {}", str(response_data)[:500])
                except Exception:
                    self.debug("Response Body: [Unable to serialize]")

        except Exception:
            pass

    def log_api_call(self, api_name: str, request_data: Any, response_data: Any,
                    duration_ms: Optional[float] = None, request_id: str = None):
        """记录API调用详情"""
        try:
            prefix = f"[{request_id}] " if request_id else ""
            
            # 基础API调用信息在INFO级别记录
            self.info("{}API Call - {}, Duration: {:.2f}ms".format(prefix, api_name, duration_ms or 0))
            
            # 详细信息只在DEBUG级别记录
            if self.logger.isEnabledFor(logging.DEBUG):
                log_data = {
                    "api": api_name,
                    "duration_ms": duration_ms,
                    "request_size": len(str(request_data)) if request_data else 0,
                    "response_size": len(str(response_data)) if response_data else 0
                }
                self.debug("{}API Call Details - {}", prefix, json.dumps(log_data, ensure_ascii=False))
                
                # 记录请求和响应的详细内容
                if request_data:
                    self.debug("{}API Request - {}", prefix, json.dumps(request_data, ensure_ascii=False, default=str))
                if response_data:
                    self.debug("{}API Response - {}", prefix, json.dumps(response_data, ensure_ascii=False, default=str))

        except Exception:
            pass

    def log_anthropic_request(self, anthropic_request: Any, request_id: str = None):
        """记录Anthropic格式请求"""
        try:
            prefix = f"[{request_id}] " if request_id else ""
            if self.logger.isEnabledFor(logging.DEBUG):
                self.debug("{}Anthropic Request - {}", prefix, json.dumps(anthropic_request, ensure_ascii=False, default=str))
        except Exception:
            pass

    def log_openai_request(self, openai_request: Any, request_id: str = None):
        """记录OpenAI格式请求"""
        try:
            prefix = f"[{request_id}] " if request_id else ""
            if self.logger.isEnabledFor(logging.DEBUG):
                self.debug("{}OpenAI Request - {}", prefix, json.dumps(openai_request, ensure_ascii=False, default=str))
        except Exception:
            pass

    def log_openai_response(self, openai_response: Any, request_id: str = None):
        """记录OpenAI原始响应"""
        try:
            prefix = f"[{request_id}] " if request_id else ""
            if self.logger.isEnabledFor(logging.DEBUG):
                self.debug("{}OpenAI Response - {}", prefix, json.dumps(openai_response, ensure_ascii=False, default=str))
        except Exception:
            pass

    def log_anthropic_response(self, anthropic_response: Any, request_id: str = None):
        """记录Anthropic格式响应"""
        try:
            prefix = f"[{request_id}] " if request_id else ""
            if self.logger.isEnabledFor(logging.DEBUG):
                self.debug("{}Anthropic Response - {}", prefix, json.dumps(anthropic_response, ensure_ascii=False, default=str))
        except Exception:
            pass

    def log_exception(self, exception: Exception, context: str = ""):
        """记录异常信息"""
        try:
            import traceback

            error_info = {
                "exception_type": type(exception).__name__,
                "message": str(exception),
                "context": context,
                "traceback": traceback.format_exc() if self.level == 'DEBUG' else None
            }

            self.error(
                "Exception - {}",
                json.dumps(error_info, ensure_ascii=False, default=str)
            )

        except Exception:
            self.error("Exception occurred but failed to log details: {} - {}",
                      type(exception).__name__, str(exception))


# 全局日志实例
logger = SafeLogger()


def get_logger(name: str = None, config: Dict = None) -> SafeLogger:
    """获取日志实例"""
    if name:
        return SafeLogger(name, config)
    if config:
        return SafeLogger('api_server', config)
    return logger


def setup_logging(level: str = None, log_to_file: bool = False):
    """设置全局日志配置"""
    global logger

    if level:
        os.environ['LOG_LEVEL'] = level

    if log_to_file:
        os.environ['LOG_TO_FILE'] = 'true'

    logger = SafeLogger()
    return logger

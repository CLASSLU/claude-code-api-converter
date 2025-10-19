"""
HTTP客户端工具
提供连接池、重试、异步支持等高级功能
"""

import asyncio
import aiohttp
import requests
import time
from typing import Optional, Dict, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.logger_setup import get_logger
from app.core.exceptions import UpstreamAPIError, TimeoutError


class OptimizedHTTPClient:
    """
    优化的HTTP客户端
    支持连接池、重试、超时控制
    """

    def __init__(self, pool_connections=100, pool_maxsize=100, max_retries=3, backoff_factor=0.3):
        """
        初始化HTTP客户端

        Args:
            pool_connections: 连接池大小
            pool_maxsize: 最大连接数
            max_retries: 最大重试次数
            backoff_factor: 重试退避因子
        """
        self.logger = get_logger('http_client', {})
        self.session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )

        # 配置HTTP适配器
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )

        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置默认超时
        self.default_timeout = 30

    def get(self, url: str, headers: Optional[Dict[str, str]] = None,
            timeout: Optional[int] = None, **kwargs) -> requests.Response:
        """
        GET请求
        """
        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=timeout or self.default_timeout,
                **kwargs
            )
            self.logger.debug(f"GET {url} - Status: {response.status_code}")
            return response
        except requests.exceptions.Timeout:
            raise TimeoutError(f"GET request timeout: {url}", timeout or self.default_timeout)
        except requests.exceptions.RequestException as e:
            raise UpstreamAPIError(f"GET request failed: {str(e)}")

    def post(self, url: str, json: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None, timeout: Optional[int] = None,
             **kwargs) -> requests.Response:
        """
        POST请求
        """
        try:
            response = self.session.post(
                url,
                json=json,
                headers=headers,
                timeout=timeout or self.default_timeout,
                **kwargs
            )
            self.logger.debug(f"POST {url} - Status: {response.status_code}")
            return response
        except requests.exceptions.Timeout:
            raise TimeoutError(f"POST request timeout: {url}", timeout or self.default_timeout)
        except requests.exceptions.RequestException as e:
            raise UpstreamAPIError(f"POST request failed: {str(e)}")

    def close(self):
        """关闭会话"""
        if self.session:
            self.session.close()


class AsyncHTTPClient:
    """
    异步HTTP客户端
    支持高并发请求处理
    """

    def __init__(self, connector_limit: int = 100, timeout: aiohttp.ClientTimeout = None):
        """
        初始化异步HTTP客户端

        Args:
            connector_limit: 连接器限制
            timeout: 默认超时设置
        """
        self.logger = get_logger('async_http_client', {})
        self.timeout = timeout or aiohttp.ClientTimeout(total=30)
        self.connector_limit = connector_limit

    async def get_session(self) -> aiohttp.ClientSession:
        """
        获取aiohttp会话
        """
        connector = aiohttp.TCPConnector(limit=self.connector_limit)
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={'User-Agent': 'claude-code-api-converter/2.0'}
        )
        return session

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None,
                  session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        异步GET请求
        """
        close_session = False
        if session is None:
            session = await self.get_session()
            close_session = True

        try:
            async with session.get(url, headers=headers) as response:
                data = await response.json()
                self.logger.debug(f"Async GET {url} - Status: {response.status}")
                return {
                    'status': response.status,
                    'data': data,
                    'headers': dict(response.headers)
                }
        except asyncio.TimeoutError:
            raise TimeoutError(f"Async GET request timeout: {url}")
        except aiohttp.ClientError as e:
            raise UpstreamAPIError(f"Async GET request failed: {str(e)}")
        finally:
            if close_session:
                await session.close()

    async def post(self, url: str, json: Optional[Dict[str, Any]] = None,
                   headers: Optional[Dict[str, str]] = None,
                   session: Optional[aiohttp.ClientSession] = None) -> Dict[str, Any]:
        """
        异步POST请求
        """
        close_session = False
        if session is None:
            session = await self.get_session()
            close_session = True

        try:
            async with session.post(url, json=json, headers=headers) as response:
                data = await response.json()
                self.logger.debug(f"Async POST {url} - Status: {response.status}")
                return {
                    'status': response.status,
                    'data': data,
                    'headers': dict(response.headers)
                }
        except asyncio.TimeoutError:
            raise TimeoutError(f"Async POST request timeout: {url}")
        except aiohttp.ClientError as e:
            raise UpstreamAPIError(f"Async POST request failed: {str(e)}")
        finally:
            if close_session:
                await session.close()

    async def close(self, session: aiohttp.ClientSession):
        """关闭会话"""
        if session and not session.closed:
            await session.close()


# 全局客户端实例
_sync_client = None
_async_client = None


def get_sync_client() -> OptimizedHTTPClient:
    """
    获取同步HTTP客户端实例
    """
    global _sync_client
    if _sync_client is None:
        _sync_client = OptimizedHTTPClient()
    return _sync_client


def get_async_client() -> AsyncHTTPClient:
    """
    获取异步HTTP客户端实例
    """
    global _async_client
    if _async_client is None:
        _async_client = AsyncHTTPClient()
    return _async_client


def cleanup_clients():
    """
    清理客户端资源
    """
    global _sync_client, _async_client
    if _sync_client:
        _sync_client.close()
        _sync_client = None
    # 异步客户端通过session管理，不需要全局清理


# 上下文管理器支持
class HTTPClientManager:
    """
    HTTP客户端管理器
    提供上下文管理功能
    """

    def __init__(self):
        self.clients = []

    def get_client(self, **kwargs) -> OptimizedHTTPClient:
        """
        创建新的客户端实例
        """
        client = OptimizedHTTPClient(**kwargs)
        self.clients.append(client)
        return client

    def cleanup(self):
        """
        清理所有客户端
        """
        for client in self.clients:
            client.close()
        self.clients.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


async def async_health_check(url: str, timeout: int = 5) -> bool:
    """
    异步健康检查
    """
    client = get_async_client()
    try:
        result = await client.get(url, timeout=aiohttp.ClientTimeout(total=timeout))
        return result['status'] == 200
    except Exception:
        return False


def benchmark_request(url: str, method: str = 'GET', **kwargs) -> Dict[str, Any]:
    """
    请求性能基准测试
    """
    client = get_sync_client()
    start_time = time.time()

    try:
        if method.upper() == 'GET':
            response = client.get(url, **kwargs)
        else:
            response = client.post(url, **kwargs)

        end_time = time.time()
        duration = (end_time - start_time) * 1000

        return {
            'url': url,
            'method': method,
            'status_code': response.status_code,
            'duration_ms': duration,
            'response_size': len(response.content),
            'success': response.status_code < 400
        }
    except Exception as e:
        end_time = time.time()
        duration = (end_time - start_time) * 1000

        return {
            'url': url,
            'method': method,
            'status_code': None,
            'duration_ms': duration,
            'response_size': 0,
            'success': False,
            'error': str(e)
        }
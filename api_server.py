from flask import Flask, request, jsonify
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from converter_class import AnthropicToOpenAIConverter
# from smart_converter_fix import SmartConverter  # 已禁用智能修复
from config_manager import ConfigManager
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import random
import socket
import sys
import psutil
import uuid
import hashlib
import json
from threading import Lock

# Windows兼容性处理
if sys.platform == 'win32':
    import msvcrt
else:
    import fcntl

# 单实例保护机制
class SingleInstanceChecker:
    """确保只有一个实例运行"""
    
    def __init__(self, port=8080):
        self.port = port
        self.lock_file = f"api_server_{port}.lock"
        self.lock_fd = None
        
    def check_port_occupied(self):
        """检查端口是否被占用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', self.port))
                return result == 0
        except:
            return False
    
    def get_existing_processes(self):
        """获取现有的api_server进程"""
        current_pid = os.getpid()
        existing_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                    
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('api_server.py' in str(arg) for arg in cmdline):
                    existing_processes.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return existing_processes
    
    def create_lock_file(self):
        """创建锁文件"""
        try:
            self.lock_fd = open(self.lock_file, 'w')
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            
            # 在Windows上使用文件锁定
            if sys.platform == 'win32':
                import msvcrt
                msvcrt.locking(self.lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
            return True
        except (IOError, OSError):
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False
    
    def cleanup_lock_file(self):
        """清理锁文件"""
        try:
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass
    
    def check_single_instance(self):
        """检查是否为单一实例"""
        # 检查端口占用
        if self.check_port_occupied():
            print(f"端口 {self.port} 已被占用！")
            existing_processes = self.get_existing_processes()
            if existing_processes:
                print(f"发现现有的API服务器进程: {existing_processes}")
                print("请先终止现有进程后再启动新实例")
            return False
        
        # 检查现有进程
        existing_processes = self.get_existing_processes()
        if existing_processes:
            print(f"发现现有的API服务器进程: {existing_processes}")
            print("正在终止现有进程...")
            
            for pid in existing_processes:
                try:
                    os.kill(pid, 9)  # 强制终止
                    print(f"已终止进程 {pid}")
                except:
                    try:
                        proc = psutil.Process(pid)
                        proc.terminate()
                        print(f"已终止进程 {pid}")
                    except:
                        print(f"无法终止进程 {pid}")
            
            # 等待进程完全退出
            time.sleep(2)
            
            # 再次检查
            remaining = self.get_existing_processes()
            if remaining:
                print(f"仍有进程运行: {remaining}")
                return False
        
        # 创建锁文件
        if not self.create_lock_file():
            print("无法创建锁文件，可能已有实例在运行")
            return False
        
        print("单实例检查通过")
        return True

# 全局单实例检查器
instance_checker = None

def cleanup_on_exit():
    """程序退出时清理资源"""
    global instance_checker
    if instance_checker:
        instance_checker.cleanup_lock_file()

import atexit
atexit.register(cleanup_on_exit)

# 配置日志
def setup_logging():
    """设置日志配置"""
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 文件处理器（带轮转，最大10MB，保留5个备份）
    file_handler = RotatingFileHandler(
        'api_server.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # 添加处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

# 设置日志
logger = setup_logging()

# 初始化配置管理器
config_manager = ConfigManager()
app = Flask(__name__)
converter = AnthropicToOpenAIConverter(config_manager)

# 从配置管理器获取配置并缓存
_openai_config = config_manager.get_openai_config()
_server_config = config_manager.get_server_config()

def get_openai_config():
    """获取OpenAI配置（缓存版本）"""
    return _openai_config

def get_server_config():
    """获取服务器配置（缓存版本）"""
    return _server_config

def refresh_configs():
    """刷新配置缓存"""
    global _openai_config, _server_config
    _openai_config = config_manager.get_openai_config()
    _server_config = config_manager.get_server_config()

# 创建带重试机制的session
def create_session_with_retry():
    session = requests.Session()
    
    # 配置重试策略
    retry_strategy = Retry(
        total=0,  # 总重试次数
        status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
        allowed_methods=["HEAD", "GET", "POST"],  # 允许重试的方法 (新版本参数名)
        backoff_factor=1,  # 重试间隔递增因子
        raise_on_status=False  # 重试后仍然失败时不抛出异常
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# 创建全局session
http_session = create_session_with_retry()

# 请求去重机制
class RequestDeduplicator:
    """请求去重器，防止Claude Code重复请求"""
    
    def __init__(self, cache_duration=30):
        self.cache = {}
        self.cache_duration = cache_duration  # 缓存持续时间（秒）
        self.lock = Lock()
        
    def _generate_request_hash(self, request_data):
        """生成更智能的请求哈希值"""
        # 🔥 关键修复：提取消息的主要文本内容，去除动态字段
        messages = request_data.get('messages', [])
        processed_messages = []

        for msg in messages:
            if msg.get('role') == 'user':
                # 只保留文本内容，去除动态字段
                content = msg.get('content', '')
                if isinstance(content, list):
                    text_parts = []
                    for item in content:
                        if item.get('type') == 'text':
                            text_parts.append(item.get('text', ''))
                    processed_messages.append({
                        'role': 'user',
                        'content': ''.join(text_parts)
                    })
                else:
                    processed_messages.append({
                        'role': 'user',
                        'content': content
                    })

        # 使用更精简的关键字段
        key_fields = {
            'model': request_data.get('model'),
            'messages': processed_messages,
            'tools': request_data.get('tools')  # 工具定义也影响响应
        }

        # 转换为JSON字符串并生成哈希
        request_str = json.dumps(key_fields, sort_keys=True, separators=(',', ':'))
        request_hash = hashlib.md5(request_str.encode()).hexdigest()

        # 🔥 调试日志：监控哈希生成
        logger.debug(f"🔍 生成请求哈希: {request_hash[:8]}... (消息数: {len(processed_messages)})")

        return request_hash
    
    def is_duplicate_request(self, request_data):
        """检查是否为重复请求"""
        request_hash = self._generate_request_hash(request_data)
        current_time = time.time()

        with self.lock:
            if request_hash in self.cache:
                cached_time, cached_response = self.cache[request_hash]

                # 检查缓存是否过期
                if current_time - cached_time < self.cache_duration:
                    cache_age = current_time - cached_time
                    logger.info(f"🔄 检测到重复请求，使用缓存响应 (哈希: {request_hash[:8]}..., 缓存年龄: {cache_age:.1f}秒)")
                    return True, cached_response
                else:
                    # 缓存过期，删除
                    logger.debug(f"🕐 缓存已过期，删除旧缓存 (哈希: {request_hash[:8]}...)")
                    del self.cache[request_hash]
                    logger.info(f"🔍 当前缓存条目数: {len(self.cache)}")

        # 🔥 监控新增请求
        logger.info(f"🆕 新请求检测 (哈希: {request_hash[:8]}..., 当前缓存: {len(self.cache)} 条)")

        return False, None
    
    def cache_response(self, request_data, response):
        """缓存响应"""
        request_hash = self._generate_request_hash(request_data)
        current_time = time.time()
        
        with self.lock:
            self.cache[request_hash] = (current_time, response)
            
            # 清理过期缓存
            expired_hashes = []
            for hash_key, (cached_time, _) in self.cache.items():
                if current_time - cached_time >= self.cache_duration:
                    expired_hashes.append(hash_key)
            
            for hash_key in expired_hashes:
                del self.cache[hash_key]
    
    def clear_cache(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
        logger.info("🔄 请求去重缓存已清空")

# 全局请求去重器 - 🔥 增加缓存时间到5分钟
request_deduplicator = RequestDeduplicator(cache_duration=300)

def is_rate_limit_error(response):
    """检测是否为限流错误"""
    if response.status_code == 429:
        return True
    
    response_text = response.text.lower()
    rate_limit_indicators = [
        'tpm', 'rpm', 'rate limit', 'too many requests',
        'rate_limit_exceeded', 'rate limited', 'quota exceeded'
    ]
    
    return any(indicator in response_text for indicator in rate_limit_indicators)

def handle_rate_limit_with_backoff(api_call_func, max_retries=3, request_id=None):
    """
    智能限流处理：使用指数退避算法自动重试
    
    Args:
        api_call_func: API调用函数
        max_retries: 最大重试次数
        request_id: 请求ID用于日志跟踪
    
    Returns:
        API响应或错误响应
    """
    req_prefix = f"[REQ:{request_id}]" if request_id else "[RETRY]"
    
    for attempt in range(max_retries + 1):
        try:
            response = api_call_func()
            
            # 如果成功或不是限流错误，直接返回
            if response.status_code == 200 or not is_rate_limit_error(response):
                if attempt > 0:
                    logger.info(f"🔥 {req_prefix} 重试成功 (第{attempt + 1}次)")
                return response
            
            # 检测到限流错误
            if attempt < max_retries:
                # 指数退避：2^attempt 秒，加上随机抖动
                base_wait = 2 ** attempt
                jitter = random.uniform(0.1, 0.5)  # 随机抖动避免同时重试
                wait_time = min(base_wait + jitter, 30)  # 最大等待30秒
                
                logger.warning(f"🔥 {req_prefix} 检测到限流 (第{attempt + 1}次)，等待 {wait_time:.1f} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"🔥 {req_prefix} 限流重试次数已达上限 ({max_retries} 次)")
                
        except Exception as e:
            if attempt < max_retries:
                wait_time = 2 ** attempt
                logger.warning(f"🔥 {req_prefix} API调用异常 (第{attempt + 1}次): {str(e)}，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"🔥 {req_prefix} API调用重试次数已达上限: {str(e)}")
                raise
    
    # 如果所有重试都失败，返回最后一次的响应
    return response

@app.route('/v1/messages', methods=['POST'])
def messages():
    """处理Anthropic格式的消息请求（兼容Claude API）"""
    # 生成唯一请求ID
    request_id = str(uuid.uuid4())[:8]
    request_start_time = time.time()
    
    try:
        # 获取Anthropic格式的请求
        anthropic_request = request.get_json()
        model = anthropic_request.get('model', 'claude-3-sonnet-20240229')
        
        logger.info(f"🔥 [REQ:{request_id}] 新HTTP请求开始 - 模型: {model}")
        logger.info(f"🔥 [REQ:{request_id}] 客户端IP: {request.remote_addr}")
        logger.info(f"🔥 [REQ:{request_id}] User-Agent: {request.headers.get('User-Agent', 'Unknown')}")
        
        # 🔥 请求去重检查 - 防止Claude Code重复请求
        is_duplicate, cached_response = request_deduplicator.is_duplicate_request(anthropic_request)
        if is_duplicate and cached_response:
            logger.info(f"🔄 [REQ:{request_id}] 返回缓存响应，避免重复处理")
            # 计算缓存响应时间
            request_duration = time.time() - request_start_time
            logger.info(f"🔄 [REQ:{request_id}] ✅ 缓存请求完成 - 总耗时: {request_duration:.2f}秒")
            return jsonify(cached_response)
        
        logger.info(f"🔥 [REQ:{request_id}] 请求详情: {anthropic_request}")
        
        # 验证必需字段
        if 'messages' not in anthropic_request:
            logger.warning("请求缺少messages字段")
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: messages'
                }
            }), 400
        
        # 转换为OpenAI格式
        logger.info(f"🔥 [REQ:{request_id}] 转换请求格式为OpenAI格式")
        openai_request = converter.convert_request(anthropic_request)
        
        # 调用OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_openai_config()["api_key"]}'
        }
        
        logger.info(f"🔥 [REQ:{request_id}] 调用OpenAI API: {get_openai_config()['base_url']}/chat/completions")
        
        # 使用智能限流处理
        def make_api_call():
            logger.info(f"🔥 [REQ:{request_id}] 发起OpenAI API调用")
            return http_session.post(
                f'{get_openai_config()["base_url"]}/chat/completions',
                headers=headers,
                json=openai_request,
                timeout=600  # 增加超时时间
            )
        
        response = handle_rate_limit_with_backoff(make_api_call, request_id=request_id)
        
        if response.status_code == 200:
            logger.info(f"🔥 [REQ:{request_id}] OpenAI API调用成功")
            openai_response = response.json()
            logger.info(f"🔥 [REQ:{request_id}] OpenAI原始响应: {str(openai_response)[:500]}...")
            
            # 转换为Anthropic格式
            anthropic_response = converter.convert_response(openai_response)
            anthropic_response['model'] = model
            
            # 🔴 智能修复已禁用 - 这是导致Claude Code循环的根本原因
            # 智能修复过度干预了正常的响应流程，导致工具调用参数错误
            # 保留原始响应，让Claude Code正常处理
            logger.info(f"🔥 [REQ:{request_id}] ⚠️ 智能修复已禁用 - 使用原始响应")
            
            # smart_converter = SmartConverter()
            # fixed_response = smart_converter.fix_response_if_needed(anthropic_response, anthropic_request)
            # 
            # if fixed_response != anthropic_response:
            #     logger.info("🔧 智能修复已应用")
            #     anthropic_response = fixed_response
            
            logger.info(f"🔥 [REQ:{request_id}] 转换后Anthropic响应: {str(anthropic_response)[:500]}...")
            
            # 🔥 缓存响应以防止重复请求
            request_deduplicator.cache_response(anthropic_request, anthropic_response)
            
            # 计算请求处理时间
            request_duration = time.time() - request_start_time
            logger.info(f"🔥 [REQ:{request_id}] ✅ 请求完成 - 总耗时: {request_duration:.2f}秒")
            
            return jsonify(anthropic_response)
        else:
            error_msg = f'OpenAI API error: {response.text}'
            logger.error(f"OpenAI API调用失败: {response.status_code} - {response.text}")
            
            # 检查是否是限流错误
            if response.status_code == 429 or 'TPM' in response.text or 'RPM' in response.text:
                logger.warning("检测到API限流，返回限流错误响应")
                return jsonify({
                    'type': 'error',
                    'error': {
                        'type': 'rate_limit_error',
                        'message': 'API rate limit exceeded. Please try again in a few moments.'
                    }
                }), 429
            else:
                return jsonify({
                    'type': 'error',
                    'error': {
                        'type': 'api_error',
                        'message': error_msg
                    }
                }), response.status_code
            
    except Exception as e:
        error_msg = f'Conversion error: {str(e)}'
        logger.error(f"转换错误: {str(e)}", exc_info=True)
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'conversion_error',
                'message': error_msg
            }
        }), 500

@app.route('/messages', methods=['POST'])
def messages_anthropic():
    """标准Anthropic API端点"""
    return messages()

@app.route('/v1/complete', methods=['POST'])
def complete():
    """处理Anthropic格式的完成请求（兼容旧版API）"""
    try:
        # 获取Anthropic格式的请求
        anthropic_request = request.get_json()
        
        # 验证必需字段
        if 'prompt' not in anthropic_request:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: prompt'
                }
            }), 400
        
        # 转换prompt为messages格式
        prompt = anthropic_request.get('prompt', '')
        messages = [{"role": "user", "content": prompt}]
        
        # 构建新的请求
        new_request = {
            "model": anthropic_request.get('model', 'claude-3-sonnet-20240229'),
            "messages": messages,
            "max_tokens": anthropic_request.get('max_tokens', 1000),
            "temperature": anthropic_request.get('temperature', 1.0),
            "stream": anthropic_request.get('stream', False)
        }
        
        # 转换为OpenAI格式
        openai_request = converter.convert_request(new_request)
        
        # 调用OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_openai_config()["api_key"]}'
        }
        
        response = http_session.post(
            f'{get_openai_config()["base_url"]}/chat/completions',
            headers=headers,
            json=openai_request,
            timeout=30
        )
        
        if response.status_code == 200:
            openai_response = response.json()
            # 转换为Anthropic格式
            anthropic_response = converter.convert_response(openai_response)
            anthropic_response['model'] = anthropic_request.get('model', 'claude-3-sonnet-20240229')
            return jsonify(anthropic_response)
        else:
            error_msg = f'OpenAI API error: {response.text}'
            app.logger.error(error_msg)
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'api_error',
                    'message': error_msg
                }
            }), response.status_code
            
    except Exception as e:
        error_msg = f'Conversion error: {str(e)}'
        app.logger.error(error_msg)
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'conversion_error',
                'message': error_msg
            }
        }), 500

@app.route('/complete', methods=['POST'])
def complete_anthropic():
    """标准Anthropic完成端点"""
    return complete()

@app.route('/v1/models', methods=['GET'])
def list_models():
    """返回支持的模型列表（Anthropic格式）"""
    logger.info("获取模型列表")
    
    # 尝试从目标API获取模型列表
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_openai_config()["api_key"]}'
        }
        
        response = http_session.get(
            f'{get_openai_config()["base_url"]}/models',
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            models_data = response.json()
            logger.info(f"从目标API获取到 {len(models_data.get('data', []))} 个模型")
            return jsonify(models_data)
        else:
            logger.warning(f"获取模型列表失败: {response.status_code}")
            
    except Exception as e:
        logger.warning(f"获取模型列表异常: {str(e)}")
    
    # 如果获取失败，返回默认的Anthropic模型列表
    default_models = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307"
    ]
    
    models_data = []
    for model in default_models:
        models_data.append({
            "id": model,
            "object": "model",
            "created": 1707879684,
            "owned_by": "anthropic"
        })
    
    logger.info(f"返回默认模型列表 {len(models_data)} 个模型")
    return jsonify({
        "object": "list",
        "data": models_data
    })

@app.route('/v1/messages/count_tokens', methods=['POST'])
def count_tokens():
    """计算token数量（Anthropic API兼容）"""
    try:
        logger.info("收到token计算请求")
        anthropic_request = request.get_json()
        
        # 验证必需字段
        if 'messages' not in anthropic_request and 'text' not in anthropic_request:
            return jsonify({
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Missing required field: messages or text'
                }
            }), 400
        
        # 简单的token估算（实际应该使用tiktoken）
        text = ""
        if 'messages' in anthropic_request:
            for message in anthropic_request['messages']:
                if isinstance(message.get('content'), str):
                    text += message['content']
                elif isinstance(message.get('content'), list):
                    for content in message['content']:
                        if content.get('type') == 'text':
                            text += content.get('text', '')
        elif 'text' in anthropic_request:
            text = anthropic_request['text']
        
        # 简单估算：大约4个字符 = 1个token
        estimated_tokens = max(1, len(text) // 4)
        
        logger.info(f"估算token数量: {estimated_tokens} (文本长度: {len(text)})")
        
        return jsonify({
            "input_tokens": estimated_tokens
        })
        
    except Exception as e:
        error_msg = f'Token计算错误: {str(e)}'
        logger.error(error_msg)
        return jsonify({
            'type': 'error',
            'error': {
                'type': 'token_calculation_error',
                'message': error_msg
            }
        }), 500

@app.route('/messages/count_tokens', methods=['POST'])
def count_tokens_anthropic():
    """标准Anthropic token计算端点"""
    return count_tokens()

@app.route('/config', methods=['GET'])
def get_config():
    """获取当前配置"""
    return jsonify(config_manager.config)

@app.route('/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        new_config = request.get_json()
        
        # 更新OpenAI配置
        if 'openai' in new_config:
            openai_cfg = new_config['openai']
            config_manager.update_openai_config(
                api_key=openai_cfg.get('api_key'),
                base_url=openai_cfg.get('base_url')
            )
        
        # 更新服务器配置
        if 'server' in new_config:
            server_cfg = new_config['server']
            config_manager.update_server_config(
                host=server_cfg.get('host'),
                port=server_cfg.get('port'),
                debug=server_cfg.get('debug')
            )
        
        
        # 保存配置
        if config_manager.save_config():
            refresh_configs()  # 刷新配置缓存
            return jsonify({"status": "success", "message": "配置已更新"})
        else:
            return jsonify({"status": "error", "message": "保存配置失败"}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/get-models', methods=['POST'])
def get_models():
    """获取可用模型列表"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        key = data.get('key', '')
        
        if not url or not key:
            return jsonify({"models": []}), 200
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}'
        }
        
        models_response = requests.get(
            f'{url}/models',
            headers=headers,
            timeout=10
        )
        
        available_models = []
        if models_response.status_code == 200:
            try:
                models_data = models_response.json()
                if 'data' in models_data:
                    available_models = [model.get('id', '') for model in models_data['data'] if model.get('id')]
            except:
                pass
        
        return jsonify({"models": available_models}), 200
            
    except requests.exceptions.Timeout:
        return jsonify({"models": []}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({"models": []}), 200
    except Exception as e:
        return jsonify({"models": []}), 200

@app.route('/test-connection', methods=['POST'])
def test_connection():
    """测试OpenAI API连接"""
    try:
        data = request.get_json()
        url = data.get('url', '')
        key = data.get('key', '')
        test_model = data.get('model', '')
        
        if not url or not key:
            return jsonify({"success": False, "error": "URL和密钥不能为空"}), 400
        
        if not test_model:
            return jsonify({"success": False, "error": "请选择或输入要测试的模型"}), 400
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {key}'
        }
        
        # 直接使用传入的模型名称进行测试
        test_request = {
            "model": test_model,
            "messages": [
                {"role": "user", "content": "Hello, this is a test message."}
            ],
            "max_tokens": 10,
            "temperature": 0.1
        }
        
        chat_response = requests.post(
            f'{url}/chat/completions',
            headers=headers,
            json=test_request,
            timeout=30
        )
        
        if chat_response.status_code == 200:
            return jsonify({
                "success": True, 
                "message": f"连接成功！模型 {test_model} 测试通过"
            })
        else:
            return jsonify({
                "success": False, 
                "error": f"模型测试失败: {chat_response.status_code} - {chat_response.text}"
            }), 400
            
    except requests.exceptions.Timeout:
        return jsonify({"success": False, "error": "连接超时"}), 400
    except requests.exceptions.ConnectionError:
        return jsonify({"success": False, "error": "无法连接到服务器"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    """OpenAI格式的聊天完成端点（Claude Code兼容）"""
    try:
        # 获取OpenAI格式的请求
        openai_request = request.get_json()
        model = openai_request.get('model', 'gpt-4')
        
        logger.info(f"收到OpenAI格式聊天完成请求 - 模型: {model}")
        
        # 验证必需字段
        if 'messages' not in openai_request:
            logger.warning("请求缺少messages字段")
            return jsonify({
                'error': {
                    'message': 'Missing required field: messages',
                    'type': 'invalid_request_error'
                }
            }), 400
        
        # 直接调用OpenAI API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_openai_config()["api_key"]}'
        }
        
        logger.info(f"调用OpenAI API: {get_openai_config()['base_url']}/chat/completions")
        
        # 使用智能限流处理
        def make_api_call():
            return http_session.post(
                f'{get_openai_config()["base_url"]}/chat/completions',
                headers=headers,
                json=openai_request,
                timeout=60
            )
        
        response = handle_rate_limit_with_backoff(make_api_call)
        
        if response.status_code == 200:
            logger.info("OpenAI API调用成功")
            return jsonify(response.json())
        else:
            error_msg = f'OpenAI API error: {response.text}'
            logger.error(f"OpenAI API调用失败: {response.status_code} - {response.text}")
            return jsonify({
                'error': {
                    'message': error_msg,
                    'type': 'api_error'
                }
            }), response.status_code
            
    except Exception as e:
        error_msg = f'Chat completion error: {str(e)}'
        logger.error(f"聊天完成错误: {str(e)}", exc_info=True)
        return jsonify({
            'error': {
                'message': error_msg,
                'type': 'server_error'
            }
        }), 500

@app.route('/v1/engines', methods=['GET'])
def list_engines():
    """返回支持的引擎列表（OpenAI格式兼容）"""
    return list_models()

@app.route('/v1/files', methods=['GET', 'POST'])
def files():
    """文件操作端点（Claude Code兼容）"""
    if request.method == 'GET':
        # 返回空文件列表
        return jsonify({
            "object": "list",
            "data": []
        })
    elif request.method == 'POST':
        # 模拟文件上传
        return jsonify({
            "id": "file_" + str(int(time.time())),
            "object": "file",
            "bytes": 0,
            "created_at": int(time.time()),
            "filename": "uploaded_file.txt",
            "purpose": "assistants"
        })

@app.route('/v1/assistants', methods=['GET', 'POST'])
def assistants():
    """助手操作端点（Claude Code兼容）"""
    if request.method == 'GET':
        # 返回空助手列表
        return jsonify({
            "object": "list",
            "data": []
        })
    elif request.method == 'POST':
        # 模拟创建助手
        return jsonify({
            "id": "asst_" + str(int(time.time())),
            "object": "assistant",
            "created_at": int(time.time()),
            "name": "Claude Code Assistant",
            "model": "claude-3-sonnet-20240229",
            "instructions": "You are a helpful assistant for code development."
        })

@app.route('/v1/runs', methods=['GET', 'POST'])
def runs():
    """运行操作端点（Claude Code兼容）"""
    if request.method == 'GET':
        # 返回空运行列表
        return jsonify({
            "object": "list",
            "data": []
        })
    elif request.method == 'POST':
        # 模拟创建运行
        return jsonify({
            "id": "run_" + str(int(time.time())),
            "object": "run",
            "created_at": int(time.time()),
            "assistant_id": "asst_demo",
            "status": "queued",
            "model": "claude-3-sonnet-20240229"
        })

@app.route('/v1/threads', methods=['GET', 'POST'])
def threads():
    """线程操作端点（Claude Code兼容）"""
    if request.method == 'GET':
        # 返回空线程列表
        return jsonify({
            "object": "list",
            "data": []
        })
    elif request.method == 'POST':
        # 模拟创建线程
        return jsonify({
            "id": "thread_" + str(int(time.time())),
            "object": "thread",
            "created_at": int(time.time()),
            "metadata": {}
        })

@app.route('/v1/messages/batches', methods=['GET', 'POST'])
def message_batches():
    """消息批处理端点（Claude Code兼容）"""
    if request.method == 'GET':
        # 返回空批处理列表
        return jsonify({
            "object": "list",
            "data": []
        })
    elif request.method == 'POST':
        # 模拟创建批处理
        return jsonify({
            "id": "batch_" + str(int(time.time())),
            "object": "batch",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
            "status": "in_progress"
        })

@app.route('/', methods=['GET'])
def index():
    """返回配置页面"""
    try:
        with open('config.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return jsonify({"error": "配置页面未找到"}), 404

@app.route('/health', methods=['GET'])
def health():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "version": "1.0.0"
    })

if __name__ == '__main__':
    # 使用配置中的服务器设置
    host = get_server_config().get('host', '0.0.0.0')
    port = get_server_config().get('port', 8080)
    debug = get_server_config().get('debug', True)
    
    # 单实例检查
    instance_checker = SingleInstanceChecker(port)
    
    if not instance_checker.check_single_instance():
        print("单实例检查失败，程序退出")
        sys.exit(1)
    
    print(f"启动API转换服务器...")
    print(f"配置页面: http://{host}:{port}/")
    print(f"API端点: http://{host}:{port}/v1/")
    print(f"配置API: http://{host}:{port}/config")
    
    # 禁用Flask的自动重启以避免多实例问题
    app.run(host=host, port=port, debug=False, use_reloader=False)

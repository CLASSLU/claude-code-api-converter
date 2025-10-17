#!/usr/bin/env python3
"""
服务管理器：负责API服务启停管理
"""

import os
import sys
import time
import subprocess
import psutil
import socket
import re
from pathlib import Path
from app.server import app, config, logger
import logging
import requests

class ServiceManager:
    """服务启停管理类"""

    def __init__(self):
        self._server_port = None

    def load_env_file(self, env_file: str = '.env.development'):
        """加载环境变量文件"""
        p = Path(env_file)
        if p.exists():
            for line in p.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
            print(f"已加载环境配置: {env_file}")
        else:
            print(f"环境配置文件不存在: {env_file}")

    def is_port_in_use(self, port, retries=3, delay=0.5):
        """使用socket连接检查端口是否被占用"""
        for i in range(retries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('127.0.0.1', port))
                    if result == 0:
                        return True
            except Exception:
                pass
            
            if i < retries - 1:
                time.sleep(delay)
        
        return False

    def find_server_process(self, port):
        """查找占用指定端口的服务器进程"""
        if not self.is_port_in_use(port):
            return None
        
        try:
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            if result.returncode == 0:
                patterns = [
                    rf'TCP\s+0.0.0.0:{port}\s+0.0.0.0:0\s+LISTENING\s+(\d+)',
                    rf'TCP\s+127.0.0.1:{port}\s+0.0.0.0:0\s+LISTENING\s+(\d+)',
                    rf'TCP\s+\*:{port}\s+0.0.0.0:0\s+LISTENING\s+(\d+)',
                    rf'TCP\s+\[::\]:{port}\s+\[::\]:0\s+LISTENING\s+(\d+)'
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, result.stdout)
                    if matches:
                        pid = int(matches[0])
                        try:
                            proc = psutil.Process(pid)
                            cmdline = ' '.join(proc.cmdline() or []).lower()
                            if 'python' in proc.name().lower() and ('server' in cmdline or 'app.server' in cmdline):
                                return proc
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
        except Exception:
            pass
        return None

    def start(self, background: bool = False):
        """启动服务"""
        server_cfg = config.get_server_config()
        port = server_cfg['port']
        self._server_port = port
        
        if self.is_port_in_use(port):
            existing_proc = self.find_server_process(port)
            if existing_proc:
                print(f"服务已在端口 {port} 运行")
                return
            else:
                print(f"端口 {port} 被其他进程占用")
                return

        try:
            self.load_env_file()
            os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

            print("启动API服务器...")
            print(f"地址: http://{server_cfg['host']}:{server_cfg['port']}/")

            if background:
                # 后台模式启动
                creation_flags = 0
                if sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW
                cmd = [sys.executable, __file__, 'run_server']
                
                try:
                    # 直接启动子进程，不创建临时日志文件
                    # 所有日志都会通过主日志系统记录
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=creation_flags
                    )
                    
                    # 等待服务启动 - 优化等待逻辑
                    for i in range(20):  # 最多等待20次，每次0.3秒 = 6秒
                        time.sleep(0.3)
                        if self.is_port_in_use(port):
                            print(f"服务已启动 (PID: {process.pid})")
                            return
                        
                        # 检查进程是否还在运行
                        if process.poll() is not None:
                            # 进程已退出，读取错误信息
                            try:
                                stdout, stderr = process.communicate(timeout=1)
                                error_msg = stderr.decode('utf-8', errors='replace') if stderr else ""
                                if error_msg:
                                    print(f"服务启动失败: {error_msg}")
                                else:
                                    print("服务启动失败: 进程意外退出")
                            except:
                                print("服务启动失败: 进程意外退出")
                            return
                    
                    print("服务启动超时")
                    # 尝试获取错误信息
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                        error_msg = stderr.decode('utf-8', errors='replace') if stderr else ""
                        if error_msg:
                            print(f"启动错误信息: {error_msg}")
                    except:
                        pass
                    return
                    
                except Exception as e:
                    print(f"启动服务时出错: {e}")
                    return
            else:
                # 前台模式启动
                app.run(host=server_cfg['host'], port=server_cfg['port'], debug=server_cfg['debug'])

        except Exception as e:
            print(f"启动服务时出错: {e}")
            return

    def stop(self):
        server_cfg = config.get_server_config()
        port = server_cfg['port']
        
        # 首先尝试通过shutdown端点停止服务
        try:
            response = requests.post(f"http://127.0.0.1:{port}/shutdown", timeout=5)
            if response.status_code == 200:
                # 等待服务停止
                for i in range(10):  # 最多等待10秒
                    time.sleep(1)
                    if not self.is_port_in_use(port):
                        print("服务已停止")
                        return True
                print("服务停止超时")
                return False
        except (socket.timeout, ConnectionRefusedError, OSError, requests.exceptions.RequestException):
            pass
        
        # 如果shutdown端点失败，尝试查找并终止进程
        proc = self.find_server_process(port)
        if proc:
            try:
                proc.terminate()
                # 等待进程结束
                try:
                    proc.wait(timeout=5)
                    print("服务已停止")
                    return True
                except psutil.TimeoutExpired:
                    # 如果进程不响应terminate，强制杀死
                    proc.kill()
                    proc.wait(timeout=2)
                    print("服务已强制停止")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
                print(f"无法停止进程: {e}")
                return False
        
        print("没有找到正在运行的服务")
        return False

    def status(self):
        server_cfg = config.get_server_config()
        try:
            with socket.create_connection(('127.0.0.1', server_cfg['port']), timeout=0.5):
                print(f"服务正在运行 (端口 {server_cfg['port']} 可用)")
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            print("服务未运行")
            return False

    def restart(self, args):
        print("正在重启服务...")
        self.stop()
        time.sleep(2)  # 等待服务完全停止
        background = getattr(args, 'background', False)
        self.start(background=background)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='服务管理器')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'restart', 'run_server'], help='要执行的命令')
    parser.add_argument('-b', '--background', action='store_true', help='以后台模式运行服务')

    args = parser.parse_args()
    mgr = ServiceManager()
    command = args.command

    if command == 'start':
        mgr.start(background=args.background)
    elif command == 'run_server':
        # 加载环境变量文件确保配置一致性
        mgr.load_env_file()
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
        
        # 确保日志级别为INFO
        logger.logger.setLevel(logging.INFO)
        # 移除控制台处理器
        for handler in logger.logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
                logger.logger.removeHandler(handler)
        # 处理werkzeug日志
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.INFO)
        for handler in werkzeug_logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                werkzeug_logger.removeHandler(handler)
        server_cfg = config.get_server_config()
        app.run(host=server_cfg['host'], port=server_cfg['port'], debug=server_cfg['debug'])
    elif command == 'stop':
        mgr.stop()
    elif command == 'status':
        mgr.status()
    elif command == 'restart':
        mgr.restart(args)
    else:
        print("未知命令，请使用: start, stop, status, restart")


if __name__ == '__main__':
    main()

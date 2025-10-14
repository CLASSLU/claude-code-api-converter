#!/usr/bin/env python3
"""
智能API服务器启动脚本
提供单实例保护、状态检查、进程管理等功能
"""

import os
import sys
import time
import signal
import psutil
import subprocess
import requests
from pathlib import Path

class ServerManager:
    """API服务器管理器"""
    
    def __init__(self, port=8080):
        self.port = port
        self.server_script = "api_server.py"
        self.lock_file = f"server_manager_{port}.lock"
        self.pid_file = f"server_{port}.pid"
        
    def check_server_running(self):
        """检查服务器是否正在运行"""
        try:
            response = requests.get(f"http://localhost:{self.port}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_server_processes(self):
        """获取所有服务器进程"""
        current_pid = os.getpid()
        server_processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid:
                    continue
                    
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('api_server.py' in str(arg) for arg in cmdline):
                    server_processes.append({
                        'pid': proc.info['pid'],
                        'cmdline': ' '.join(cmdline),
                        'status': proc.status(),
                        'cpu_percent': proc.cpu_percent(),
                        'memory_mb': proc.memory_info().rss / 1024 / 1024
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return server_processes
    
    def stop_server_processes(self):
        """停止所有服务器进程"""
        processes = self.get_server_processes()
        stopped_count = 0
        
        for proc_info in processes:
            pid = proc_info['pid']
            try:
                print(f"正在停止进程 {pid}...")
                proc = psutil.Process(pid)
                proc.terminate()
                
                # 等待进程优雅退出
                try:
                    proc.wait(timeout=5)
                    print(f"成功: 进程 {pid} 已停止")
                    stopped_count += 1
                except psutil.TimeoutExpired:
                    # 强制杀死进程
                    proc.kill()
                    print(f"成功: 强制停止进程 {pid}")
                    stopped_count += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                try:
                    os.kill(pid, 9)
                    print(f"成功: 强制杀死进程 {pid}")
                    stopped_count += 1
                except:
                    print(f"警告: 无法停止进程 {pid}")
        
        return stopped_count
    
    def start_server(self):
        """启动服务器"""
        # 检查是否已有服务器运行
        if self.check_server_running():
            print("警告: 服务器已在运行")
            return False
        
        # 停止现有进程
        processes = self.get_server_processes()
        if processes:
            print(f"发现 {len(processes)} 个现有服务器进程，正在停止...")
            self.stop_server_processes()
            time.sleep(2)
        
        # 启动新服务器
        try:
            print(f"正在启动服务器 (端口 {self.port})...")
            
            # 使用subprocess启动服务器进程
            process = subprocess.Popen(
                [sys.executable, self.server_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # 保存PID
            with open(self.pid_file, 'w') as f:
                f.write(str(process.pid))
            
            # 等待服务器启动
            for i in range(30):  # 最多等待30秒
                time.sleep(1)
                if self.check_server_running():
                    print(f"成功: 服务器启动成功 (PID: {process.pid})")
                    return True
                
                # 检查进程是否还在运行
                if process.poll() is not None:
                    # 读取进程输出以获取错误信息
                    stdout, stderr = process.communicate()
                    if stdout:
                        print(f"错误: 服务器启动失败，进程已退出")
                        print(f"错误信息: {stdout}")
                    else:
                        print(f"错误: 服务器启动失败，进程已退出 (无错误信息)")
                    return False
                
                print(f"等待服务器启动... ({i+1}/30)")
            
            print("错误: 服务器启动超时")
            process.terminate()
            return False
            
        except Exception as e:
            print(f"错误: 启动服务器失败: {str(e)}")
            return False
    
    def stop_server(self):
        """停止服务器"""
        print("正在停止服务器...")
        
        # 从PID文件读取PID
        pid = None
        if os.path.exists(self.pid_file):
            try:
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
            except:
                pass
        
        # 停止所有服务器进程
        stopped_count = self.stop_server_processes()
        
        # 清理文件
        for file_path in [self.pid_file, self.lock_file]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        if stopped_count > 0:
            print(f"成功: 已停止 {stopped_count} 个服务器进程")
            return True
        else:
            print("警告: 没有找到运行中的服务器进程")
            return False
    
    def restart_server(self):
        """重启服务器"""
        print("正在重启服务器...")
        self.stop_server()
        time.sleep(2)
        return self.start_server()
    
    def show_status(self):
        """显示服务器状态"""
        print("=" * 60)
        print("API服务器状态")
        print("=" * 60)
        
        # 检查健康状态
        if self.check_server_running():
            print("状态: 服务器状态: 运行中")
            try:
                response = requests.get(f"http://localhost:{self.port}/v1/models", timeout=5)
                if response.status_code == 200:
                    models_data = response.json()
                    model_count = len(models_data.get('data', []))
                    print(f"   可用模型数量: {model_count}")
            except:
                pass
        else:
            print("状态: 服务器状态: 未运行")
        
        # 显示进程信息
        processes = self.get_server_processes()
        if processes:
            print(f"\n进程: 发现 {len(processes)} 个服务器进程:")
            for proc in processes:
                print(f"   PID: {proc['pid']}")
                print(f"   状态: {proc['status']}")
                print(f"   CPU: {proc['cpu_percent']:.1f}%")
                print(f"   内存: {proc['memory_mb']:.1f} MB")
                print(f"   命令: {proc['cmdline'][:80]}...")
                print()
        else:
            print("\n进程: 没有发现服务器进程")
        
        print("=" * 60)
    
    def show_logs(self, lines=50):
        """显示服务器日志"""
        log_file = "api_server.log"
        if not os.path.exists(log_file):
            print(f"错误: 日志文件 {log_file} 不存在")
            return
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:]
                
                print(f"日志: 显示最近 {len(recent_lines)} 行日志:")
                print("=" * 80)
                for line in recent_lines:
                    print(line.rstrip())
                print("=" * 80)
                
        except Exception as e:
            print(f"错误: 读取日志失败: {str(e)}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='API服务器管理器')
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'status', 'logs'], 
                       help='要执行的命令')
    parser.add_argument('--port', type=int, default=8080, help='服务器端口')
    parser.add_argument('--lines', type=int, default=50, help='显示日志行数')
    
    args = parser.parse_args()
    
    manager = ServerManager(args.port)
    
    if args.command == 'start':
        success = manager.start_server()
        sys.exit(0 if success else 1)
        
    elif args.command == 'stop':
        success = manager.stop_server()
        sys.exit(0 if success else 1)
        
    elif args.command == 'restart':
        success = manager.restart_server()
        sys.exit(0 if success else 1)
        
    elif args.command == 'status':
        manager.show_status()
        
    elif args.command == 'logs':
        manager.show_logs(args.lines)

if __name__ == '__main__':
    main()

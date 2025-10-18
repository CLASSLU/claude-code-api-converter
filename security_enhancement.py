#!/usr/bin/env python3
"""
Security Enhancement Module for API Conversion Server
Addresses the memory leak issues and enhances overall system security.

This module implements:
1. Memory leak detection and prevention
2. Stream buffer management
3. Resource cleanup mechanisms
4. Security monitoring and logging
"""

import gc
import psutil
import threading
import time
import logging
from typing import Dict, Any, Optional
from contextlib import contextmanager
import weakref

class SecurityManager:
    """
    Enhanced security manager with memory leak prevention
    and resource monitoring capabilities.
    """

    def __init__(self, max_memory_mb: int = 200, check_interval: int = 60):
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self.active_connections = weakref.WeakSet()
        self.memory_monitor_active = True
        self.logger = logging.getLogger(__name__)

        # Start memory monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._memory_monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()

    def _memory_monitor_loop(self):
        """Background thread for monitoring memory usage"""
        while self.memory_monitor_active:
            try:
                current_memory = self._get_memory_usage_mb()

                if current_memory > self.max_memory_mb:
                    self.logger.warning(
                        f"Memory usage exceeded threshold: {current_memory:.1f}MB > {self.max_memory_mb}MB"
                    )
                    self._perform_emergency_cleanup()

                time.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"Memory monitor error: {e}")
                time.sleep(10)  # Brief pause on error

    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0

    def _perform_emergency_cleanup(self):
        """Perform emergency cleanup to free memory"""
        try:
            # Force garbage collection
            collected = gc.collect()
            self.logger.info(f"Emergency cleanup: collected {collected} objects")

            # Close any hanging connections
            self._cleanup_hanging_connections()

            # Log cleanup results
            new_memory = self._get_memory_usage_mb()
            self.logger.info(f"Memory after cleanup: {new_memory:.1f}MB")

        except Exception as e:
            self.logger.error(f"Emergency cleanup failed: {e}")

    def _cleanup_hanging_connections(self):
        """Clean up hanging connections and resources"""
        connection_count = len(self.active_connections)
        if connection_count > 0:
            self.logger.warning(f"Cleaning up {connection_count} hanging connections")

            # Force cleanup of all connections
            for conn in list(self.active_connections):
                try:
                    if hasattr(conn, 'close'):
                        conn.close()
                except Exception:
                    pass

    @contextmanager
    def managed_connection(self, connection):
        """Context manager for managing connection lifecycle"""
        self.active_connections.add(connection)
        try:
            yield connection
        finally:
            try:
                if hasattr(connection, 'close'):
                    connection.close()
            except Exception:
                pass
            finally:
                self.active_connections.discard(connection)

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "memory_usage_mb": memory_info.rss / 1024 / 1024,
                "memory_percent": process.memory_percent(),
                "cpu_percent": process.cpu_percent(),
                "active_connections": len(self.active_connections),
                "threads": process.num_threads(),
                "file_descriptors": process.num_fds() if hasattr(process, 'num_fds') else 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get system stats: {e}")
            return {"error": str(e)}

    def shutdown(self):
        """Gracefully shutdown the security manager"""
        self.memory_monitor_active = False
        self._cleanup_hanging_connections()
        gc.collect()

# SSE Stream Buffer Manager
class StreamBufferManager:
    """
    Manages SSE stream buffers to prevent memory leaks
    """

    def __init__(self, max_buffer_size: int = 1024 * 1024):  # 1MB max
        self.max_buffer_size = max_buffer_size
        self.active_buffers = {}

    def create_buffer(self, stream_id: str) -> bytearray:
        """Create a new managed buffer"""
        if stream_id in self.active_buffers:
            raise ValueError(f"Buffer for stream {stream_id} already exists")

        buffer = bytearray()
        self.active_buffers[stream_id] = buffer
        return buffer

    def append_to_buffer(self, stream_id: str, data: bytes) -> bool:
        """Append data to buffer with size checking"""
        if stream_id not in self.active_buffers:
            return False

        buffer = self.active_buffers[stream_id]
        if len(buffer) + len(data) > self.max_buffer_size:
            # Buffer overflow - trigger cleanup
            self.cleanup_buffer(stream_id)
            return False

        buffer.extend(data)
        return True

    def cleanup_buffer(self, stream_id: str):
        """Clean up a specific buffer"""
        if stream_id in self.active_buffers:
            del self.active_buffers[stream_id]

    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about active buffers"""
        total_size = sum(len(buf) for buf in self.active_buffers.values())
        return {
            "active_buffers": len(self.active_buffers),
            "total_buffer_size_mb": total_size / 1024 / 1024,
            "max_buffer_size_mb": self.max_buffer_size / 1024 / 1024
        }

    def cleanup_all(self):
        """Clean up all buffers"""
        self.active_buffers.clear()

# Integration with existing server
def initialize_security_system():
    """Initialize the enhanced security system"""
    security_manager = SecurityManager(max_memory_mb=200, check_interval=30)
    stream_manager = StreamBufferManager()

    return security_manager, stream_manager

# Usage example for integration
if __name__ == "__main__":
    # Initialize security components
    security_manager, stream_manager = initialize_security_system()

    try:
        # Example: Monitor system stats
        stats = security_manager.get_system_stats()
        print(f"System Stats: {stats}")

        # Example: Managed stream processing
        with security_manager.managed_connection(lambda: None):
            buffer = stream_manager.create_buffer("test_stream")
            stream_manager.append_to_buffer("test_stream", b"test data")

    finally:
        # Cleanup
        security_manager.shutdown()
        stream_manager.cleanup_all()
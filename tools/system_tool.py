"""
系统工具
提供系统级别的操作功能
"""
import psutil
import platform
import shutil
from datetime import datetime
from typing import Dict, Any
from .base_tool import BaseTool, ToolResult


class SystemInfoTool(BaseTool):
    """
    系统信息工具
    提供系统硬件和软件信息查询
    """

    def __init__(self):
        super().__init__(
            name="get_system_info",
            description="获取系统硬件和软件信息"
        )

    def execute(self, info_type: str = "all") -> ToolResult:
        """
        获取系统信息

        参数:
            info_type: 信息类型 ("all", "cpu", "memory", "disk", "network", "platform")

        返回:
            ToolResult: 包含系统信息或错误信息
        """
        try:
            info = {}

            if info_type in ["all", "platform"]:
                info["platform"] = {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                    "architecture": platform.architecture(),
                    "python_version": platform.python_version()
                }

            if info_type in ["all", "cpu"]:
                info["cpu"] = {
                    "physical_cores": psutil.cpu_count(logical=False),
                    "logical_cores": psutil.cpu_count(logical=True),
                    "current_frequency": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
                    "usage_percent": psutil.cpu_percent(interval=1)
                }

            if info_type in ["all", "memory"]:
                memory = psutil.virtual_memory()
                info["memory"] = {
                    "total": f"{memory.total / (1024**3):.2f} GB",
                    "available": f"{memory.available / (1024**3):.2f} GB",
                    "used": f"{memory.used / (1024**3):.2f} GB",
                    "percent": f"{memory.percent}%"
                }

            if info_type in ["all", "disk"]:
                disk_partitions = []
                for partition in psutil.disk_partitions():
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        disk_partitions.append({
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "total": f"{usage.total / (1024**3):.2f} GB",
                            "used": f"{usage.used / (1024**3):.2f} GB",
                            "free": f"{usage.free / (1024**3):.2f} GB",
                            "percent": f"{usage.percent}%"
                        })
                    except PermissionError:
                        continue
                info["disk"] = disk_partitions

            if info_type in ["all", "network"]:
                network_stats = psutil.net_io_counters()
                info["network"] = {
                    "bytes_sent": f"{network_stats.bytes_sent / (1024**2):.2f} MB",
                    "bytes_recv": f"{network_stats.bytes_recv / (1024**2):.2f} MB",
                    "packets_sent": network_stats.packets_sent,
                    "packets_recv": network_stats.packets_recv
                }

            return ToolResult(
                success=True,
                output=str(info) if info else "没有获取到指定类型的信息"
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"获取系统信息失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "info_type": {
                    "type": "string",
                    "description": "信息类型 (all, cpu, memory, disk, network, platform)",
                    "default": "all"
                }
            }
        }


class ProcessTool(BaseTool):
    """
    进程管理工具
    提供进程查询和管理功能
    """

    def __init__(self):
        super().__init__(
            name="manage_processes",
            description="管理系统进程"
        )

    def execute(self, action: str = "list", process_name: str = None, pid: int = None) -> ToolResult:
        """
        管理进程

        参数:
            action: 操作类型 ("list", "kill", "find")
            process_name: 进程名称 (用于find和kill操作)
            pid: 进程ID (用于kill操作)

        返回:
            ToolResult: 包含执行结果或错误信息
        """
        try:
            if action == "list":
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                    try:
                        proc_info = proc.info
                        processes.append({
                            "pid": proc_info['pid'],
                            "name": proc_info['name'],
                            "cpu_percent": f"{proc_info['cpu_percent']:.1f}%",
                            "memory_percent": f"{proc_info['memory_percent']:.1f}%",
                            "status": proc_info['status']
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                return ToolResult(
                    success=True,
                    output=f"系统进程列表 (共{len(processes)}个进程):\n{str(processes[:20])}"  # 只显示前20个
                )

            elif action == "find":
                if not process_name:
                    return ToolResult(
                        success=False,
                        error="查找进程需要提供进程名称"
                    )
                
                found_processes = []
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if process_name.lower() in proc.info['name'].lower():
                            found_processes.append({
                                "pid": proc.info['pid'],
                                "name": proc.info['name']
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                return ToolResult(
                    success=True,
                    output=f"找到 {len(found_processes)} 个匹配进程: {str(found_processes)}"
                )

            elif action == "kill":
                if pid:
                    try:
                        process = psutil.Process(pid)
                        process.terminate()
                        return ToolResult(
                            success=True,
                            output=f"成功终止进程 {pid}"
                        )
                    except psutil.NoSuchProcess:
                        return ToolResult(
                            success=False,
                            error=f"进程 {pid} 不存在"
                        )
                    except psutil.AccessDenied:
                        return ToolResult(
                            success=False,
                            error=f"没有权限终止进程 {pid}"
                        )
                elif process_name:
                    killed_count = 0
                    for proc in psutil.process_iter(['pid', 'name']):
                        try:
                            if process_name.lower() in proc.info['name'].lower():
                                proc.terminate()
                                killed_count += 1
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue
                    
                    return ToolResult(
                        success=True,
                        output=f"成功终止 {killed_count} 个匹配进程"
                    )
                else:
                    return ToolResult(
                        success=False,
                        error="终止进程需要提供进程ID或名称"
                    )

            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的操作: {action}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"进程管理失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型 (list, find, kill)",
                    "default": "list"
                },
                "process_name": {
                    "type": "string",
                    "description": "进程名称 (用于find和kill操作)"
                },
                "pid": {
                    "type": "integer",
                    "description": "进程ID (用于kill操作)"
                }
            }
        }


class DiskTool(BaseTool):
    """
    磁盘管理工具
    提供磁盘空间查询和文件清理功能
    """

    def __init__(self):
        super().__init__(
            name="manage_disk",
            description="管理磁盘空间和文件"
        )

    def execute(self, action: str = "usage", path: str = "/") -> ToolResult:
        """
        管理磁盘

        参数:
            action: 操作类型 ("usage", "cleanup")
            path: 路径 (用于usage操作)

        返回:
            ToolResult: 包含执行结果或错误信息
        """
        try:
            if action == "usage":
                usage = shutil.disk_usage(path)
                
                info = {
                    "path": path,
                    "total": f"{usage.total / (1024**3):.2f} GB",
                    "used": f"{usage.used / (1024**3):.2f} GB",
                    "free": f"{usage.free / (1024**3):.2f} GB",
                    "percent": f"{(usage.used / usage.total) * 100:.1f}%"
                }
                
                return ToolResult(
                    success=True,
                    output=str(info)
                )

            elif action == "cleanup":
                # 简单的清理操作 - 清理临时文件
                temp_dirs = ['/tmp', '/var/tmp']
                cleaned_size = 0
                
                for temp_dir in temp_dirs:
                    if os.path.exists(temp_dir):
                        try:
                            for item in os.listdir(temp_dir):
                                item_path = os.path.join(temp_dir, item)
                                try:
                                    if os.path.isfile(item_path):
                                        size = os.path.getsize(item_path)
                                        os.remove(item_path)
                                        cleaned_size += size
                                    elif os.path.isdir(item_path):
                                        import shutil
                                        size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                                                 for dirpath, dirnames, filenames in os.walk(item_path) 
                                                 for filename in filenames)
                                        shutil.rmtree(item_path)
                                        cleaned_size += size
                                except PermissionError:
                                    continue
                        except PermissionError:
                            continue
                
                return ToolResult(
                    success=True,
                    output=f"清理完成，释放了 {cleaned_size / (1024**2):.2f} MB 空间"
                )

            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的操作: {action}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"磁盘管理失败: {str(e)}"
            )

    def get_parameters(self) -> Dict[str, Any]:
        """定义工具参数"""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型 (usage, cleanup)",
                    "default": "usage"
                },
                "path": {
                    "type": "string",
                    "description": "路径 (用于usage操作)",
                    "default": "/"
                }
            }
        }


# 为了方便导入，添加一个缺失的导入
import os
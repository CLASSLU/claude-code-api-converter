"""
API蓝图模块
集中管理所有API端点
"""

import sys
from pathlib import Path
from flask import Blueprint

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# 创建主API蓝图
api_bp = Blueprint('api', __name__)

# 导入所有子蓝图
from app.api.messages import messages_bp
from app.api.models import models_bp
from app.api.health import health_bp
from app.api.config import config_bp

# 注册子蓝图到主蓝图
api_bp.register_blueprint(messages_bp, url_prefix='')
api_bp.register_blueprint(models_bp, url_prefix='')
api_bp.register_blueprint(health_bp, url_prefix='')
api_bp.register_blueprint(config_bp, url_prefix='')
import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """统一配置日志，确保所有模块的日志都写入 app.log 文件"""
    # 创建一个根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 避免重复添加 handler
    if root_logger.handlers:
        return root_logger
    
    # 使用 RotatingFileHandler 滚动记录日志
    file_handler = RotatingFileHandler('app.log', maxBytes=10240000, backupCount=5, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    
    # 同时输出到控制台，方便调试
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    return root_logger

import json
import random
import pandas as pd
from langchain_core.tools import tool
import logging

# 使用根日志记录器，确保使用与 app_flask.py 一致的日志配置
logger = logging.getLogger(__name__)


@tool
def get_bom_data() -> str:
    """
    读取物料清单数据
    
    从 sample_bom.csv 文件读取所有物料信息，返回 JSON 格式字符串
    
    Returns:
        str: JSON 格式的物料清单数据（包含物料名称、供应商、交期、单价等字段）
    """
    try:
        df = pd.read_csv('sample_bom.csv')
        bom_list = df.to_dict(orient='records')
        result = json.dumps(bom_list, ensure_ascii=False, indent=2)
        logger.info(f"成功读取 BOM 数据，共 {len(bom_list)} 条物料")
        return result
    except FileNotFoundError:
        error_msg = "错误：未找到 sample_bom.csv 文件"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"读取 BOM 数据时发生错误：{str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@tool
def get_supplier_leadtime(supplier_name: str) -> str:
    """
    查询供应商实时交期
    
    模拟从供应商系统查询实时交期，返回原始交期基础上浮动 ±2 周的结果
    
    Args:
        supplier_name: 供应商名称
        
    Returns:
        str: 实时交期信息（JSON 格式，包含原始交期、当前交期、变动量）
    """
    try:
        df = pd.read_csv('sample_bom.csv')
        supplier_data = df[df['供应商'] == supplier_name]
        
        # 供应商不存在
        if supplier_data.empty:
            result = {
                "supplier": supplier_name,
                "message": f"未找到供应商 {supplier_name} 的数据"
            }
            logger.warning(f"供应商 {supplier_name} 未找到")
            return json.dumps(result, ensure_ascii=False)
        
        # 获取原始交期并计算变动后交期（最少 4 周）
        original_leadtime = int(supplier_data['交期(周)'].values[0])
        variation = random.randint(-2, 2)
        new_leadtime = max(4, original_leadtime + variation)
        
        result = {
            "supplier": supplier_name,
            "original_leadtime_weeks": original_leadtime,
            "current_leadtime_weeks": new_leadtime,
            "variation_weeks": variation,
            "message": f"供应商 {supplier_name} 实时交期为 {new_leadtime} 周（原始交期 {original_leadtime} 周，变动 {variation:+d} 周）"
        }
        
        logger.info(f"供应商 {supplier_name} 实时交期查询完成：{new_leadtime} 周")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"查询供应商交期时发生错误：{str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@tool
def get_historical_risks(material_name: str) -> str:
    """
    查询物料历史风险记录
    
    根据物料名称中包含的关键字，返回预设的历史延迟概率和平均延迟时间
    
    Args:
        material_name: 物料名称
        
    Returns:
        str: 历史风险信息（JSON 格式，包含延迟概率、平均延迟周数、风险等级）
    """
    try:
        # 根据物料类型返回不同的历史风险数据
        if "TIA" in material_name:
            result = {
                "material": material_name,
                "historical_delay_probability": "40%",
                "average_delay_weeks": 3,
                "risk_level": "高",
                "message": "历史延迟概率 40%，平均延迟 3 周"
            }
        elif "DSP" in material_name:
            result = {
                "material": material_name,
                "historical_delay_probability": "30%",
                "average_delay_weeks": 2,
                "risk_level": "中",
                "message": "历史延迟概率 30%，平均延迟 2 周"
            }
        elif "ROSA" in material_name or "TOSA" in material_name:
            result = {
                "material": material_name,
                "historical_delay_probability": "25%",
                "average_delay_weeks": 2,
                "risk_level": "中",
                "message": "历史延迟概率 25%，平均延迟 2 周"
            }
        elif "Driver" in material_name:
            result = {
                "material": material_name,
                "historical_delay_probability": "20%",
                "average_delay_weeks": 1,
                "risk_level": "低",
                "message": "历史延迟概率 20%，平均延迟 1 周"
            }
        else:
            result = {
                "material": material_name,
                "historical_delay_probability": "0%",
                "average_delay_weeks": 0,
                "risk_level": "低",
                "message": "无显著历史延迟记录"
            }
        
        logger.info(f"物料 {material_name} 历史风险查询完成")
        return json.dumps(result, ensure_ascii=False)
        
    except Exception as e:
        error_msg = f"查询历史风险时发生错误：{str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg}, ensure_ascii=False)


@tool
def send_alert(report_content: str) -> str:
    """
    发送风险预警通知
    
    将分析报告发送给项目组，返回发送确认信息
    
    Args:
        report_content: 预警报告内容
        
    Returns:
        str: 发送结果确认消息
    """
    try:
        preview = report_content[:50] if len(report_content) > 50 else report_content
        result = f"✅ 预警已发送给项目组：{preview}..."
        logger.info("预警已成功发送给项目组")
        return result
    except Exception as e:
        error_msg = f"发送预警时发生错误：{str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


def get_all_tools():
    """
    获取所有可用工具列表
    
    Returns:
        list: 工具函数列表
    """
    return [get_bom_data, get_supplier_leadtime, get_historical_risks, send_alert]

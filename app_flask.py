# 设置标准输出编码为 UTF-8
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入 Flask 及相关模块
from flask import Flask, render_template_string, request, jsonify
import re
import json
import os
from datetime import datetime
import logging
import markdown

# 从 utils 模块导入统一的日志配置
from utils import setup_logging

# 初始化日志配置
logger = setup_logging()

# 导入 agent 模块（在日志配置之后导入，确保 agent 使用同样的日志配置）
import agent

# 创建 Flask 应用实例
app = Flask(__name__)

# 配置 Flask 自身的日志也使用同样的 handler
for handler in logger.handlers:
    app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

app.logger.info('Optical NPI Material Guardian startup')


def extract_metrics(report: str):
    """
    从报告文本中提取关键指标（fallback 方案）
    
    当无法从 JSON 代码块解析指标时，使用正则表达式从文本中提取
    
    Args:
        report: 分析报告文本
        
    Returns:
        tuple: (风险物料数量, 延期天数, 成本超支比例)
    """
    risk_count = 3
    delay_days = 14
    cost_risk = "15%"

    # 提取高风险物料数量
    risk_patterns = [
        r"高风险物料数量.*(\d+)\s*项",
        r"(\d+)\s*项.*高风险"
    ]
    for pattern in risk_patterns:
        match = re.search(pattern, report)
        if match:
            risk_count = int(match.group(1))
            break

    # 提取预估延期天数
    delay_patterns = [
        r"预估延期天数[：:]\s*(\d+)",
        r"预估项目延期[：:]\s*(\d+)\s*天",
        r"延期(\d+~\d+)\s*天",
        r"延期\s*(\d+)\s*天"
    ]
    for pattern in delay_patterns:
        match = re.search(pattern, report)
        if match:
            result = match.group(1)
            if '~' in result:
                delay_days = int(result.split('~')[1])
            else:
                delay_days = int(result)
            break

    # 提取成本超支比例
    cost_patterns = [
        r"成本超支比例[：:]\s*(\d+(?:\.\d+)?%?)",
        r"预估成本超支比例[：:]\s*(\d+(?:\.\d+)?%?)",
        r"约\s*(\d+(?:\.\d+)?%?)",
        r"(\d+(?:\.\d+)?%?)\s*成本超支"
    ]
    for pattern in cost_patterns:
        match = re.search(pattern, report)
        if match:
            cost_value = match.group(1)
            if '%' not in cost_value:
                cost_value = f"{cost_value}%"
            cost_risk = cost_value
            break

    return risk_count, delay_days, cost_risk


def count_high_risk_items(report: str):
    """
    从报告的高风险物料清单表格中统计行数
    
    注：此函数为备用方案，当前已不再使用（优先使用 JSON 中的 high_risk_count）
    
    Args:
        report: 分析报告文本
        
    Returns:
        int: 表格中的数据行数
    """
    high_risk_count = 0
    
    table_section = re.search(r'##.*高风险物料清单.*?##', report, re.DOTALL)
    if table_section:
        table_content = table_section.group(0)
        lines = table_content.strip().split('\n')
        data_rows = [line for line in lines if line.startswith('|') and not line.startswith('|---')]
        high_risk_count = len(data_rows) - 1
    
    return max(high_risk_count, 1)


def markdown_to_html(markdown_text: str) -> str:
    """
    将 Markdown 文本转换为 HTML
    
    Args:
        markdown_text: Markdown 格式文本
        
    Returns:
        HTML 格式文本
    """
    html = markdown.markdown(
        markdown_text,
        extensions=[
            'tables',
            'fenced_code',
            'codehilite'
        ]
    )
    return html


def save_report_to_file(report: str, target_date_str: str) -> str:
    """
    保存分析报告到 reports 目录（HTML 格式）
    
    Args:
        report: 分析报告内容（Markdown 格式）
        target_date_str: 目标 build 日期字符串（用于生成文件名）
        
    Returns:
        保存的文件路径
    """
    try:
        # 确保 reports 目录存在
        reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # 生成文件名：包含日期和时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_part = target_date_str.replace('-', '')
        filename = f"risk_report_{date_part}_{timestamp}.html"
        filepath = os.path.join(reports_dir, filename)
        
        # 将 Markdown 转换为 HTML
        html_report = markdown_to_html(report)
        
        # 保存 HTML 报告（带美观的样式和元信息）
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optical NPI 物料风险分析报告 - {target_date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            max-width: 960px;
            margin: 40px auto;
            padding: 20px;
            background: #f5f7fa;
            color: #333;
        }}
        .report-container {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .meta {{
            color: #888;
            font-size: 0.9rem;
            margin-bottom: 20px;
        }}
        h1 {{ 
            color: #667eea; 
            border-bottom: 2px solid #667eea; 
            padding-bottom: 10px; 
            margin-top: 0;
        }}
        h2 {{ 
            color: #444; 
            margin-top: 28px; 
        }}
        h3 {{ 
            color: #555; 
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 10px 14px;
            text-align: left;
        }}
        th {{ 
            background: #667eea; 
            color: white; 
            font-weight: 600; 
        }}
        tr:nth-child(even) {{ 
            background: #f8f9fa; 
        }}
        code {{
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f0f0f0;
            padding: 10px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        ul, ol {{
            margin-left: 20px;
        }}
        li {{
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <div class="report-container">
        <div class="meta">
            <strong>目标 Build 日期：</strong>{target_date_str}<br>
            <strong>生成时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
        {html_report}
    </div>
</body>
</html>"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        app.logger.info(f"报告已保存到: {filepath}")
        return filepath
    except Exception as e:
        app.logger.error(f"保存报告失败: {str(e)}")
        return None


def analyze_risk(target_date_str):
    """
    执行物料风险分析的核心函数
    
    调用 Agent 进行分析，解析结果指标，并返回结构化数据
    
    Args:
        target_date_str: 目标 build 日期字符串
        
    Returns:
        dict: 分析结果（包含风险物料数、延期天数、成本超支、报告内容、分析步骤）
    """
    try:
        app.logger.info(f"开始分析，目标日期: {target_date_str}")
        
        # 构造用户输入并调用 Agent
        user_input = f"目标 build 日期为 {target_date_str}，请进行全面物料风险分析。"
        result = agent.run_agent(user_input)
        output = result.get("output", "")
        steps = result.get("intermediate_steps", [])
        
        # 初始化指标变量
        risk_count = 0
        delay_days = 0
        cost_risk = "0%"
        match = None
        
        app.logger.info(f"返回前 output 长度: {len(output)}")
        
        # 方法1：从 Markdown 的 JSON 代码块中解析
        match = re.search(r'```json\s*\n?(.*?)\n?```', output, re.DOTALL)
        if match:
            try:
                metrics = json.loads(match.group(1))
                risk_count = metrics.get('high_risk_count', 0)
                delay_days = metrics.get('estimated_delay_days', 0)
                cost_risk = metrics.get('cost_overrun_percentage', '0%')
                app.logger.info("从 JSON 代码块成功解析指标数据")
            except Exception as json_error:
                app.logger.warning(f"JSON 代码块解析失败，尝试原始提取: {str(json_error)}")
                match = None
        
        # 方法2：从文本中的原始 JSON 对象解析
        if not match:
            match = re.search(r'\{[^{}]*"high_risk_count"[^{}]*\}', output)
            if match:
                try:
                    metrics = json.loads(match.group(0))
                    risk_count = metrics.get('high_risk_count', 0)
                    delay_days = metrics.get('estimated_delay_days', 0)
                    cost_risk = metrics.get('cost_overrun_percentage', '0%')
                    app.logger.info("从原始 JSON 对象成功解析指标数据")
                except Exception as json_error:
                    app.logger.warning(f"原始 JSON 对象解析失败: {str(json_error)}")
                    match = None
        
        # 方法3：fallback - 使用正则表达式从文本提取
        if not match:
            app.logger.warning("未找到 JSON 块，使用 fallback")
            risk_count, delay_days, cost_risk = extract_metrics(output)

        app.logger.info(f"分析完成: 风险物料={risk_count}, 延期={delay_days}天, 成本超支={cost_risk}")

        # 过滤掉报告末尾的 JSON 代码块
        clean_md = re.sub(r'\n```json[\s\S]*?```\s*$', '', output).strip()
        
        # 将 Markdown 转换为 HTML（用于前端展示）
        html_body = markdown_to_html(clean_md)
        
        # 保存报告到 reports 目录
        html_report_path = save_report_to_file(clean_md, target_date_str)

        return {
            "success": True,
            "risk_count": risk_count,
            "delay_days": delay_days,
            "cost_risk": cost_risk,
            "report": clean_md,              # 清洗后的 Markdown（备用）
            "html_report": html_body,        # HTML 主体（用于前端渲染）
            "html_report_path": html_report_path,  # 保存的文件路径
            "steps": steps
        }

    except Exception as e:
        app.logger.error(f"分析失败: {str(e)}")
        return {
            "success": False,
            "risk_count": 0,
            "delay_days": 0,
            "cost_risk": "0%",
            "report": f"分析过程中发生错误：{str(e)}",
            "steps": []
        }


# ==================== 前端 HTML 模板 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optical NPI Material Guardian</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
        }
        .header p {
            font-size: 1.1rem;
            opacity: 0.9;
        }
        .model-info {
            background: rgba(255,255,255,0.1);
            padding: 10px 20px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 10px;
        }
        .card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .input-section {
            display: flex;
            gap: 16px;
            align-items: center;
            flex-wrap: wrap;
        }
        .input-section input {
            flex: 1;
            min-width: 200px;
            padding: 12px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .input-section input:focus {
            outline: none;
            border-color: #667eea;
        }
        .input-section button {
            padding: 12px 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .input-section button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .input-section button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .dashboard {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .metric-card h3 {
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 8px;
        }
        .metric-card .value {
            font-size: 2.5rem;
            font-weight: 700;
        }
        .report-section h2 {
            color: #333;
            margin-bottom: 16px;
            font-size: 1.4rem;
        }
        .report-content {
            background: white;
            border-radius: 12px;
            padding: 24px;
            line-height: 1.7;
            color: #333;
            max-height: 800px;
            overflow-y: auto;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }
        .report-content h1 { 
            font-size: 1.6rem; 
            margin: 20px 0 10px; 
            color: #333; 
            border-bottom: 2px solid #667eea; 
            padding-bottom: 10px;
        }
        .report-content h2 { 
            font-size: 1.3rem; 
            margin: 20px 0 10px; 
            color: #444; 
        }
        .report-content h3 { 
            font-size: 1.1rem; 
            color: #555; 
        }
        .report-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 16px 0;
        }
        .report-content th, .report-content td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }
        .report-content th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }
        .report-content tr:nth-child(even) { 
            background: #f8f9fa; 
        }
        .report-content code {
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .report-content pre {
            background: #f0f0f0;
            padding: 10px;
            border-radius: 6px;
            overflow-x: auto;
        }
        .report-content ul, .report-content ol {
            margin-left: 20px;
            margin-top: 10px;
            margin-bottom: 10px;
        }
        .report-content li {
            margin-bottom: 5px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .loading-spinner {
            width: 40px;
            height: 40px;
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .error {
            background: #ffebee;
            border-left: 4px solid #ef5350;
            padding: 15px;
            border-radius: 0 8px 8px 0;
            color: #c62828;
        }
        .steps-section {
            margin-top: 20px;
        }
        .steps-header {
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
            padding: 12px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 10px;
            font-weight: 600;
            transition: transform 0.2s;
        }
        .steps-header:hover {
            transform: translateY(-1px);
        }
        .steps-header .arrow {
            transition: transform 0.3s;
        }
        .steps-header.expanded .arrow {
            transform: rotate(90deg);
        }
        .steps-content {
            display: none;
            background: #f8f9fa;
            border-radius: 0 0 10px 10px;
            padding: 20px;
            margin-top: -5px;
            border: 1px solid #e9ecef;
        }
        .steps-content.visible {
            display: block;
        }
        .step-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 16px;
            background: white;
            border-radius: 8px;
            margin-bottom: 8px;
            border-left: 3px solid #667eea;
        }
        .step-item:last-child {
            margin-bottom: 0;
        }
        .step-number {
            width: 28px;
            height: 28px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            flex-shrink: 0;
        }
        .step-details {
            flex: 1;
        }
        .step-tool {
            font-weight: 600;
            color: #333;
            margin-bottom: 4px;
        }
        .step-action {
            color: #666;
            font-size: 0.9rem;
        }
        .step-input {
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: #888;
            margin-top: 4px;
            word-break: break-all;
        }
        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.8rem;
            }
            .input-section {
                flex-direction: column;
            }
            .input-section input, .input-section button {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Optical NPI Material Guardian</h1>
            <p>光模块 NPI 物料风险智能分析系统</p>
            <div class="model-info">{{ model_info }}</div>
        </div>

        <div class="card">
            <div class="input-section">
                <input type="date" id="targetDate" value="2026-06-30">
                <button id="analyzeBtn">开始智能分析</button>
            </div>
        </div>

        <!-- 仪表盘：显示三个核心指标 -->
        <div class="dashboard" id="dashboard" style="display: none;">
            <div class="metric-card">
                <h3>高风险物料</h3>
                <div class="value" id="riskCount">0</div>
                <div style="font-size: 0.8rem; opacity: 0.8; margin-top: 4px;">个</div>
            </div>
            <div class="metric-card">
                <h3>预估延期</h3>
                <div class="value" id="delayDays">0</div>
                <div style="font-size: 0.8rem; opacity: 0.8; margin-top: 4px;">天</div>
            </div>
            <div class="metric-card">
                <h3>成本超支</h3>
                <div class="value" id="costRisk">0%</div>
                <div style="font-size: 0.8rem; opacity: 0.8; margin-top: 4px;">风险</div>
            </div>
        </div>

        <!-- 报告展示区域 -->
        <div class="card report-section" id="reportSection" style="display: none;">
            <h2>风险分析报告</h2>
            <div class="report-content" id="reportContent"></div>
            
            <!-- 分析步骤（Agent 思考链） -->
            <div class="steps-section" id="stepsSection" style="display: none;">
                <div class="steps-header" id="stepsHeader">
                    <span class="arrow">▶</span>
                    <span>分析步骤 (Agent 思考链)</span>
                    <span id="stepsCount" style="margin-left: auto; opacity: 0.8;"></span>
                </div>
                <div class="steps-content" id="stepsContent"></div>
            </div>
        </div>

        <!-- 加载指示器 -->
        <div id="loadingIndicator" style="display: none;" class="card loading">
            <div class="loading-spinner"></div>
            <div>正在分析物料风险...</div>
        </div>
    </div>

    <script>
        // 分析按钮点击事件
        document.getElementById('analyzeBtn').addEventListener('click', async function() {
            const date = document.getElementById('targetDate').value;
            if (!date) {
                alert('请选择目标 Build 日期');
                return;
            }

            const btn = this;
            btn.disabled = true;
            btn.innerHTML = '分析中...';

            // 隐藏结果区域，显示加载动画
            document.getElementById('dashboard').style.display = 'none';
            document.getElementById('reportSection').style.display = 'none';
            document.getElementById('stepsSection').style.display = 'none';
            document.getElementById('loadingIndicator').style.display = 'block';

            try {
                // 发送分析请求
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ target_date: date })
                });

                const result = await response.json();

                // 更新仪表盘数据
                document.getElementById('riskCount').textContent = result.risk_count;
                document.getElementById('delayDays').textContent = result.delay_days;
                document.getElementById('costRisk').textContent = result.cost_risk;
                document.getElementById('reportContent').innerHTML = result.html_report || result.report;
                
                // 显示报告保存路径
                const reportSection = document.getElementById('reportSection');
                const existingPathEl = document.getElementById('reportPathInfo');
                if (existingPathEl) existingPathEl.remove();
                
                if (result.html_report_path) {
                    const pathEl = document.createElement('div');
                    pathEl.id = 'reportPathInfo';
                    pathEl.style.cssText = 'margin-top:16px;padding:12px 16px;background:#e8f5e9;border-radius:8px;color:#2e7d32;font-size:0.9rem;display:flex;align-items:center;gap:8px;';
                    pathEl.innerHTML = '📁 报告已保存至：<code style="background:#c8e6c9;padding:4px 8px;border-radius:4px;">' + result.html_report_path + '</code>';
                    reportSection.appendChild(pathEl);
                }

                // 渲染分析步骤
                renderSteps(result.steps || []);

                // 显示结果区域
                document.getElementById('dashboard').style.display = 'grid';
                document.getElementById('reportSection').style.display = 'block';

            } catch (error) {
                document.getElementById('reportContent').innerHTML = '<div class="error">请求失败：' + error.message + '</div>';
                document.getElementById('reportSection').style.display = 'block';
            } finally {
                // 隐藏加载动画，恢复按钮状态
                document.getElementById('loadingIndicator').style.display = 'none';
                btn.disabled = false;
                btn.innerHTML = '开始智能分析';
            }
        });

        // 步骤折叠/展开切换
        document.getElementById('stepsHeader').addEventListener('click', function() {
            this.classList.toggle('expanded');
            document.getElementById('stepsContent').classList.toggle('visible');
        });

        // 渲染分析步骤列表
        function renderSteps(steps) {
            const stepsContent = document.getElementById('stepsContent');
            const stepsCount = document.getElementById('stepsCount');
            const stepsSection = document.getElementById('stepsSection');

            if (steps && steps.length > 0) {
                stepsCount.textContent = steps.length + ' 步';
                stepsContent.innerHTML = steps.map(step => `
                    <div class="step-item">
                        <div class="step-number">${step.step}</div>
                        <div class="step-details">
                            <div class="step-tool">${step.tool}</div>
                            <div class="step-action">${step.action}</div>
                            ${step.input && Object.keys(step.input).length > 0 ? 
                                '<div class="step-input">输入: ' + JSON.stringify(step.input) + '</div>' : ''}
                        </div>
                    </div>
                `).join('');
                stepsSection.style.display = 'block';
            } else {
                stepsSection.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""


# ==================== Flask 路由 ====================
@app.route('/')
def index():
    """首页路由：返回主页面"""
    model_info = agent.get_model_info()
    return render_template_string(HTML_TEMPLATE, model_info=model_info)


@app.route('/analyze', methods=['POST'])
def analyze():
    """分析接口：接收目标日期，返回分析结果"""
    data = request.get_json()
    target_date = data.get('target_date', '')
    result = analyze_risk(target_date)
    return jsonify(result)


# 启动应用
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

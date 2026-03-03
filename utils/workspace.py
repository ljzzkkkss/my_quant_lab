import os
import json
from pathlib import Path
from utils.logger import logger

# 配置文件保存在 configs 目录下
WORKSPACE_FILE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "configs" / "workspace.json"

def save_workspace(state_dict: dict) -> bool:
    """保存当前 UI 配置到本地 JSON"""
    try:
        WORKSPACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # 仅保存基础数据类型 (剔除 DataFrame 或 UI 组件等无法序列化的对象)
        save_dict = {
            k: v for k, v in state_dict.items()
            if isinstance(v, (int, float, str, bool)) and not k.startswith("FormSubmitter")
        }
        with open(WORKSPACE_FILE, 'w', encoding='utf-8') as f:
            json.dump(save_dict, f, indent=4, ensure_ascii=False)
        logger.info("💾 工作区配置已成功持久化保存。")
        return True
    except Exception as e:
        logger.error(f"❌ 保存工作区失败: {e}")
        return False

def load_workspace() -> dict:
    """加载本地配置"""
    if not WORKSPACE_FILE.exists():
        return {}
    try:
        with open(WORKSPACE_FILE, 'r', encoding='utf-8') as f:
            logger.info("📂 工作区配置已读取。")
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 加载工作区失败: {e}")
        return {}
import streamlit as st
from contextlib import contextmanager

@contextmanager
def ui_button_lock(placeholder, running_text="⏳ 演算中...", normal_text="🚀 执行", key="btn"):
    """
    Streamlit 独家高级技巧：按钮状态防连点与自动恢复的上下文管理器。
    无论内部代码是正常跑完，还是中途 return/报错 退出，
    都能保证 100% 恢复按钮的原始状态，彻底告别按钮死锁！
    """
    try:
        # 进入上下文：瞬间渲染灰色锁定按钮
        placeholder.empty()
        placeholder.button(running_text, disabled=True, use_container_width=True, key=f"{key}_running")
        yield
    finally:
        # 退出上下文（无论是正常结束还是异常退出）：恢复蓝色主按钮
        placeholder.empty()
        placeholder.button(normal_text, type="primary", use_container_width=True, key=f"{key}_done")
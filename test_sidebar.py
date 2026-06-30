"""
测试页面 - 找到侧边栏的正确选择器
"""
import streamlit as st
import time

# 页面配置
st.set_page_config(
    page_title="测试 - 侧边栏选择器",
    page_icon="🔍",
    layout="wide",
)

# 注入测试脚本
st.markdown(
    """
    <script>
    // 等待页面加载完成
    setTimeout(function() {
        // 找到所有带有 data-testid 属性的元素
        const elements = document.querySelectorAll('[data-testid]');
        
        let result = "找到的元素：\\n";
        elements.forEach(el => {
            result += el.tagName + " [data-testid=" + el.getAttribute('data-testid') + "]\\n";
        });
        
        // 显示结果
        alert(result);
        
        // 在控制台输出
        console.log("找到的元素：", elements);
    }, 2000);
    </script>
    
    <style>
    /* 测试：把所有元素加上红色边框 */
    [data-testid] {
        border: 1px solid red !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🔍 测试页面 - 找到侧边栏的正确选择器")

st.markdown("""
### 说明
这个页面会：
1. 在页面加载 2 秒后，弹出alert显示所有带有 `data-testid` 属性的元素
2. 把所有带有 `data-testid` 属性的元素加上**红色边框**

请查看：
- alert 弹窗中的内容（侧边栏的 `data-testid` 是什么？）
- 页面上哪些元素有红色边框
""")

st.sidebar.title("侧边栏")
st.sidebar.text_input("测试输入框")
st.sidebar.button("测试按钮")

st.markdown("### 请在浏览器中查看：")
st.markdown("1. alert 弹窗中的内容")
st.markdown("2. 页面上哪些元素有红色边框")
st.markdown("3. 按 F12 打开开发者工具，查看侧边栏的 HTML 结构")

st.markdown("---")
st.markdown("### 侧边栏的正确选择器可能是：")
st.markdown("- `section[data-testid='stSidebar']`")
st.markdown("- `.stSidebar`")
st.markdown("- `[data-testid='stSidebar']`")
st.markdown("- 或者其他（请以 alert 弹窗中的内容为准）")

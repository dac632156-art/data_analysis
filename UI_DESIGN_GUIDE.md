# DataMind AI - UI 设计说明文档

## 🎨 配色方案（清新浅绿渐变）

### 主配色
- **背景渐变**：`linear-gradient(160deg, #D8F2F5 0%, #E8F7D9 100%)`
  - 顶部：`#D8F2F5`（浅天青）
  - 底部：`#E8F7D9`（嫩浅黄绿）

- **主色**：`#9FD8C8`（柔和薄荷绿）
- **强调色**：`#5CB8A2`（低饱和柔青）
- **深主色**：`#4AA790`（强调色 hover 状态）
- **更深主色**：`#3F927E`（强调色 active 状态）

### 文字配色
- **主文字**：`#2A4A43`（深灰绿）
- **次要文字**：`#5A7C74`（中度灰绿）
- **占位文字**：`#94B0A9`（浅灰）

### 组件配色
- **卡片背景**：`rgba(255, 255, 255, 0.75)`（半透明白色）
- **卡片边框**：`#C7E6DF`（极浅薄荷灰）
- **侧边栏背景**：`rgba(255, 255, 255, 0.85)`（半透明白色 + 毛玻璃效果）

### 功能色
- **成功**：`#5CB8A2`（强调色）
- **警告**：`#F1C40F`（黄色）
- **错误**：`#E74C3C`（红色）

---

## 📐 布局规范

### 侧边栏
- **宽度**：280px
- **背景**：半透明白色 + 毛玻璃效果（`backdrop-filter: blur(10px)`）
- **边框**：右侧 1px 实线 `#C7E6DF`
- **内边距**：2rem 1.5rem

### 主内容区
- **左边距**：280px（侧边栏宽度）
- **内边距**：2rem 3rem
- **最大宽度**：1400px

### 卡片
- **背景**：`rgba(255, 255, 255, 0.75)`
- **边框**：1px solid `#C7E6DF`
- **圆角**：12px
- **阴影**：`0 2px 12px rgba(92, 184, 162, 0.08)`
- **hover 阴影**：`0 4px 16px rgba(92, 184, 162, 0.15)`
- **hover 效果**：`transform: translateY(-2px)`

---

## 🔤 字体规范

### 字体家族
```
"PingFang SC", "Microsoft YaHei", sans-serif
```

### 字号层级
- **页面标题**：2rem (32px)，font-weight: 700
- **区块标题**：1.5rem (24px)，font-weight: 600
- **卡片标题**：1.2rem (19px)，font-weight: 600
- **正文**：1rem (16px)，font-weight: 400
- **次要文字**：0.9rem (14px)，font-weight: 400
- **小字/提示**：0.85rem (14px)，font-weight: 400

---

## 🎯 组件规范

### 按钮

#### 主按钮（Primary Button）
```css
background: #5CB8A2;
color: #FFFFFF;
border: none;
border-radius: 8px;
padding: 0.75rem 1.5rem;
font-weight: 600;
box-shadow: 0 2px 8px rgba(92, 184, 162, 0.2);
transition: all 0.3s ease;
```

**Hover 状态**：
```css
background: #4AA790;
transform: translateY(-2px);
box-shadow: 0 4px 12px rgba(92, 184, 162, 0.3);
```

**Active 状态**：
```css
background: #3F927E;
```

#### 次要按钮（Secondary Button）
```css
background: transparent;
color: #9FD8C8;
border: 1px solid #9FD8C8;
border-radius: 8px;
padding: 0.75rem 1.5rem;
font-weight: 500;
```

**Hover 状态**：
```css
background: rgba(159, 216, 200, 0.15);
border-color: #5CB8A2;
color: #5CB8A2;
```

### 输入框
```css
background: rgba(255, 255, 255, 0.75);
color: #2A4A43;
border: 1px solid #C7E6DF;
border-radius: 8px;
padding: 0.75rem 1rem;
transition: all 0.3s ease;
```

**Focus 状态**：
```css
border-color: #5CB8A2;
box-shadow: 0 0 0 2px rgba(92, 184, 162, 0.15);
```

### 数据表格
```css
background: rgba(255, 255, 255, 0.75);
border: 1px solid #C7E6DF;
border-radius: 12px;
overflow: hidden;
```

**表头**：
```css
background: #9FD8C8;
color: #2A4A43;
font-weight: 600;
```

**行交替色**：
- 偶数行：`rgba(255, 255, 255, 0.5)`
- 奇数行：`rgba(199, 230, 223, 0.3)`
- Hover：`rgba(159, 216, 200, 0.3)`

### 指标卡片
```css
background: rgba(255, 255, 255, 0.75);
border: 1px solid #C7E6DF;
border-radius: 12px;
padding: 1.5rem;
box-shadow: 0 2px 12px rgba(92, 184, 162, 0.08);
```

**指标值**：
```css
font-size: 2rem;
font-weight: 700;
color: #2A4A43;
```

---

## 📱 响应式断点

### 桌面端（默认）
- 侧边栏：280px 固定宽度
- 主内容区：margin-left: 280px

### 平板端（≤ 1024px）
- 侧边栏：折叠为图标模式（80px）
- 主内容区：margin-left: 80px

### 移动端（≤ 768px）
- 侧边栏：隐藏，通过汉堡菜单打开
- 主内容区：margin-left: 0
- 指标卡片：1 列布局

---

## ✨ 动画规范

### 过渡动画
```css
transition: all 0.3s ease;
```

### 淡入动画
```css
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

### 应用范围
- 卡片 hover：0.3s ease
- 按钮 hover：0.3s ease
- 页面切换：fadeIn 0.3s ease
- Tab 切换：淡入淡出 0.3s ease

---

## 🎨 设计原则

### 1. 清新自然
- 使用浅绿渐变背景，营造清新自然的氛围
- 避免高饱和度颜色，统一控制在 30-60%

### 2. 柔和统一
- 所有深色文字均带绿调，和背景色系统一
- 不使用纯黑 `#000`，改用深灰绿 `#2A4A43`

### 3. 半透明层次
- 半透明组件统一叠加白色基底，保证文字可读性
- 使用 `rgba(255, 255, 255, 0.75)` 作为卡片背景

### 4. 圆角柔和
- 卡片圆角：12px
- 按钮圆角：8px
- 输入框圆角：8px
- 匹配柔和渐变质感

### 5. 毛玻璃效果
- 侧边栏使用 `backdrop-filter: blur(10px)`
- 营造现代感和高档感

---

## 📦 资源清单

### 已提供的文件
1. ✅ `design_preview.html` - UI 设计稿（高保真 HTML 原型）
2. ✅ `static/custom.css` - Streamlit 自定义 CSS（已应用配色）
3. ✅ `config.py` - 图表配色配置（已更新）
4. ✅ `.streamlit/config.toml` - Streamlit 主题配置（已更新）

### 待创建的文件
1. ⏳ Figma 设计模板（JSON 格式）
2. ⏳ 组件库文档
3. ⏳ 图标资源包

---

## 🚀 下一步

### 1. 查看设计稿
- 在浏览器中打开 `design_preview.html`
- 确认配色和布局是否符合预期

### 2. 导入 Figma（可选）
- 如果需要进一步设计，可以将 `design_preview.html` 的截图导入 Figma
- 或者使用 Figma 插件（如 "HTML to Figma"）直接转换

### 3. 应用到 Streamlit
- 当前的 `static/custom.css` 已经应用了配色方案
- 运行 `streamlit run app.py` 查看实际效果

### 4. 微调优化
- 如果配色有任何不满意的地方，告诉我具体需求
- 我可以帮你调整 CSS 和 HTML

---

## 📞 联系方式

如果有任何问题或需要进一步调整，请随时告诉我！

---

**设计完成时间**：2026-06-16
**设计师**：AI Assistant
**版本**：v1.0

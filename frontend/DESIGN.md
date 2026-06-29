---
name: 设备检修智能管理系统
description: 智能检修实验室 - 融合AI技术与设备检修的专业管理系统
colors:
  primary: "#195FA8"
  primary-light: "#3A7BC8"
  primary-dark: "#0F3A6B"
  success: "#23A55A"
  warning: "#FF8C38"
  danger: "#E53E3E"
  neutral-gray: "#7C8798"
  neutral-light: "#F5F7FA"
  neutral-dark: "#2D3748"
  white: "#FFFFFF"
typography:
  display:
    fontFamily: "system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "clamp(2rem, 5vw, 3rem)"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "normal"
  headline:
    fontFamily: "system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "1.125rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.5px"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
  xl: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.white}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-light}"
  button-success:
    backgroundColor: "{colors.success}"
    textColor: "{colors.white}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-warning:
    backgroundColor: "{colors.warning}"
    textColor: "{colors.white}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-danger:
    backgroundColor: "{colors.danger}"
    textColor: "{colors.white}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  card-default:
    backgroundColor: "{colors.white}"
    rounded: "{rounded.xl}"
    padding: "{spacing.lg}"
  input-default:
    backgroundColor: "{colors.white}"
    textColor: "{colors.neutral-dark}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: 设备检修智能管理系统

## 1. Overview

**Creative North Star: "智能检修实验室"**

这是一个融合AI技术与设备检修专业性的智能管理系统，设计理念源自现代工业运维平台。系统通过科技感与实用性并重的设计语言，为工程师和维护人员打造高效、智能的工作环境。

界面采用简洁现代的视觉风格，避免过度装饰和花哨效果。白卡片配浅灰底色营造清爽专业的氛围，工业深蓝作为主色传达可靠与专业感。三级灰色系统确保信息层次清晰，让用户能快速定位关键信息。

系统明确拒绝紫色系配色和花哨渐变效果，坚持工业运维平台的配色规范。设计注重实用性和效率，每个视觉元素都服务于功能需求，让用户专注于设备检修工作本身。

**Key Characteristics:**
- 工业深蓝主色调，专业可靠
- 四色状态系统，清晰直观
- 白卡片+浅灰底色，清爽现代
- 触感自信的交互反馈
- 信息层次清晰，高效易用

## 2. Colors

基于工业运维检修平台的配色规范，采用专业可靠的色彩系统。

### Primary
- **工业深蓝** (#195FA8): 用于主导航、核心按钮、重要操作。传达专业、可靠、稳定的技术形象。
- **工业浅蓝** (#3A7BC8): 用于主色悬停状态、次要强调元素。
- **工业深蓝** (#0F3A6B): 用于主色激活状态、深度强调。

### Status Colors
- **正常绿** (#23A55A): 用于设备正常运行、成功状态、完成状态。
- **预警橙** (#FF8C38): 用于设备预警、待处理状态、注意提醒。
- **故障红** (#E53E3E): 用于设备故障、错误状态、危险警示。
- **离线灰** (#7C8798): 用于设备离线、禁用状态、次要信息。

### Neutral
- **纯白** (#FFFFFF): 用于卡片背景、输入框背景、内容区域。
- **浅灰背景** (#F5F7FA): 用于页面背景、分隔区域、次要背景。
- **深灰文字** (#2D3748): 用于标题、重要文字、主要信息。
- **中性灰** (#7C8798): 用于正文、次要文字、辅助信息。

### Named Rules
**工业配色规范。** 严格遵循工业运维检修平台的配色标准，主色使用工业深蓝(#195FA8)，状态色固定为绿/橙/红/灰四色，禁止使用紫色系和花哨渐变效果。

**三级灰度系统。** 使用深灰(#2D3748)用于标题，中性灰(#7C8798)用于正文，浅灰(#F5F7FA)用于背景，确保信息层次清晰。

## 3. Typography

**Display Font:** system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
**Body Font:** system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif
**Label Font:** system-ui, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif

**Character:** 专业、清晰、易读。字体选择注重跨平台兼容性和中文显示效果，确保在各种设备上都有良好的阅读体验。

### Hierarchy
- **Display** (600, clamp(2rem, 5vw, 3rem), 1.2): 用于页面主标题，如仪表盘标题、重要页面标题。
- **Headline** (600, 1.5rem, 1.3): 用于区块标题、卡片标题、章节标题。
- **Title** (500, 1.125rem, 1.4): 用于次级标题、表单标签、重要信息。
- **Body** (400, 0.875rem, 1.5): 用于正文内容、描述文字、表格内容。最大行长度65-75ch。
- **Label** (500, 0.75rem, 1.4, 0.5px): 用于标签、徽章、辅助说明文字。

### Named Rules
**系统字体优先。** 优先使用系统默认字体栈，确保加载速度和跨平台一致性。中文环境优先显示'PingFang SC'和'Microsoft YaHei'。

## 4. Elevation

系统采用交互反馈式的阴影设计，阴影主要用于状态变化时的视觉反馈，而非装饰性的层次营造。

### Shadow Vocabulary
- **悬停阴影** (`box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1)`): 用于卡片、按钮悬停状态，提供轻微的浮起感。
- **聚焦阴影** (`box-shadow: 0 0 0 3px rgba(25, 95, 168, 0.1)`): 用于输入框、按钮聚焦状态，提供清晰的视觉反馈。
- **激活阴影** (`box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15)`): 用于按下状态，提供触感反馈。

### Named Rules
**交互反馈原则。** 阴影主要用于交互反馈（悬停、聚焦、激活），避免过度使用阴影装饰。默认状态保持扁平，状态变化时才出现阴影效果。

**适度阴影。** 阴影模糊度控制在8-12px之间，避免过大的阴影造成视觉混乱。

## 5. Components

### Buttons
- **Shape:** 圆角8px，保持专业感的同时不失现代感。
- **Primary:** 工业深蓝背景(#195FA8)，白色文字，内边距10px 20px。
- **Hover / Focus:** 悬停时变为工业浅蓝(#3A7BC8)，聚焦时添加聚焦阴影。
- **Success / Warning / Danger:** 分别使用绿/橙/红背景，白色文字，相同的圆角和内边距。
- **Ghost:** 透明背景，工业深蓝文字，用于次要操作。

### Chips / Tags
- **Style:** 根据状态使用对应的背景色和文字色，圆角12px，内边距4px 12px。
- **State:** 正常(绿底白字)、预警(橙底白字)、故障(红底白字)、离线(灰底白字)。

### Cards / Containers
- **Corner Style:** 圆角16px，营造现代感。
- **Background:** 纯白背景(#FFFFFF)。
- **Shadow Strategy:** 默认无阴影，悬停时添加悬停阴影。
- **Border:** 无边框，通过阴影和间距区分层次。
- **Internal Padding:** 24px，确保内容呼吸感。

### Inputs / Fields
- **Style:** 1px边框(#E5E7EB)，白色背景，圆角8px。
- **Focus:** 边框变为工业深蓝(#195FA8)，添加聚焦阴影。
- **Error:** 边框变为故障红(#E53E3E)，显示错误提示文字。
- **Disabled:** 背景变为浅灰(#F5F7FA)，文字变为中性灰(#7C8798)。

### Navigation
- **Style:** 深色背景(#1D2B3A)，工业深蓝(#195FA8)激活状态，浅灰文字(#BF CBD9)默认状态。
- **Typography:** 14px字重500，保持清晰易读。
- **Default / Hover / Active:** 默认浅灰文字，悬停白色文字，激活工业深蓝背景+白色文字。
- **Mobile:** 侧边栏可收起，保持桌面端和移动端的一致体验。

### Status Indicators
- **Style:** 圆点+文字组合，圆点6px直径，带脉冲动画。
- **State:** 正常(绿点)、预警(橙点)、故障(红点)、离线(灰点)。

## 6. Do's and Don'ts

### Do:
- **Do** 使用工业深蓝(#195FA8)作为主色，用于导航和核心按钮。
- **Do** 使用固定的四色状态系统：绿(#23A55A)正常、橙(#FF8C38)预警、红(#E53E3E)故障、灰(#7C8798)离线。
- **Do** 采用白卡片+浅灰底色的布局，营造清爽现代的视觉效果。
- **Do** 使用三级灰色系统区分标题(#2D3748)、正文(#7C8798)、背景(#F5F7FA)。
- **Do** 为交互元素添加悬停和聚焦状态，提供清晰的视觉反馈。
- **Do** 保持8px的间距倍数，确保布局的节奏感和一致性。
- **Do** 使用圆角8-16px，在专业感和现代感之间取得平衡。

### Don't:
- **Don't** 使用紫色系配色，严格遵循工业运维检修平台的配色规范。
- **Don't** 使用花哨的渐变效果，保持简洁专业的设计风格。
- **Don't** 过度使用阴影装饰，阴影主要用于交互反馈。
- **Don't** 使用过大的圆角(超过16px)，保持专业感。
- **Don't** 混用多种色彩系统，坚持统一的配色规范。
- **Don't** 忽视信息层次，确保标题、正文、辅助信息的视觉区分。
- **Don't** 使用复杂的动画效果，保持简洁流畅的交互体验。
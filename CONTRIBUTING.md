# 贡献指南

感谢你对这个项目的关注！本文档说明如何参与贡献。

## 项目结构

```
xiaoyu-hue.github.io/
├── assets/           # CSS、JavaScript、图片资源
│   ├── main.js       # 微动效系统主逻辑
│   ├── prefs.js      # 主题和偏好设置
│   ├── theme-boot.js # 主题初始化
│   ├── style.css     # 样式表
│   └── pwa.js        # Service Worker
├── blog/             # 博客文章（HTML）
├── src/              # 构建源文件
│   ├── layouts/      # HTML 模板
│   ├── pages/        # 页面正文
│   └── data/         # 站点元数据
├── tests/            # 测试套件
│   ├── e2e/          # Playwright E2E 测试
│   ├── js/           # JavaScript 单元测试
│   └── test_*.py     # Python 单元测试
├── build.py          # 构建脚本
├── index.html        # 首页入口
└── sw.js             # Service Worker
```

## 开发环境

### 前置要求

- Node.js >= 18
- Python >= 3.9
- Git

### 安装依赖

```bash
npm install
```

### 运行测试

```bash
# 全部测试
npm test

# 单项测试
npm run test:unit    # Python 单元测试
npm run test:js      # JavaScript 单元测试
npm run test:e2e     # Playwright E2E 测试
```

## 提交规范

### Commit 消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型**:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档变更
- `style`: 代码格式（不影响功能）
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

**示例**:
```
feat(motion): 添加鼠标光晕跟随效果

实现 document-level glow 效果，通过 requestAnimationFrame 驱动。
添加 CSS 变量 --glow-x, --glow-y 控制位置。

Co-authored-by: xiaoyu-hue <xiaoyu-hue@users.noreply.github.com>
```

### 提交作者

所有 commit 必须使用远端仓库账号身份提交：
- 用户名：`xiaoyu-hue`
- 邮箱：`xiaoyu-hue@users.noreply.github.com`

## 代码规范

### JavaScript

- 使用 ES Modules（`type: module`）
- 避免使用 `var`，优先使用 `const` 和 `let`
- 所有函数使用命名函数表达式（便于调试栈）
- CSP 限制下，行内样式必须使用 `el.style.setProperty()`

### CSS

- 使用 CSS 自定义属性（变量）管理设计令牌
- 优先使用 `transform` 和 `opacity` 实现动画（GPU 加速）
- 遵循 BEM 命名约定

### Python

- 遵循 PEP 8 规范
- 使用类型提示
- 所有公开函数添加 docstring

## 测试要求

所有新功能必须包含测试：
- 单元测试：覆盖核心逻辑
- E2E 测试：覆盖关键用户流程
- 视觉回归测试：覆盖 UI 变更

## Pull Request 流程

1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/xxx`）
3. 提交变更（`git commit -m "feat: xxx"`）
4. 推送到分支（`git push origin feature/xxx`）
5. 创建 Pull Request

## 联系我们

如有问题，请通过 GitHub Issues 联系我们。

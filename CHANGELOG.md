# Changelog

所有重要变更将记录在这个文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- 微动效系统五层架构：CSS 样式层 + JS 编排层 + 降级层 + 控制层 + 检测层
- 自定义光标系统：指针元素 + 跟随节点 + 缩放过渡
- 点击涟漪效果：按钮/卡片点击时的扩散动画
- 鼠标光晕跟随：页面级环境光效果
- 卡片 3D 倾斜：鼠标位置驱动视差效果
- 磁性按钮：鼠标靠近时按钮自动吸附效果

### Changed
- 字体系统重构：标题使用 Syne，正文使用 Inter，代码使用 JetBrains Mono
- 间距系统升级：section padding 从 80px 增加到 140px，card padding 从 36px 增加到 48px
- CSS 变量系统化：定义完整的设计令牌体系

### Fixed
- CSP 配置优化：确保所有运行时功能兼容
- Service Worker 缓存策略：更新缓存版本号
- 可访问性：添加更多 ARIA 属性

## [1.0.0] - 2026-10-02

### Added
- 个人作品集网站基础架构
- 博客系统（8 篇文章）
- PWA 支持：离线访问 + 添加到主屏幕
- RSS 订阅支持
- 主题切换：支持浅色/深色模式
- 偏好设置持久化
- 滚动淡入动画
- 响应式设计
- 完整的测试套件：Python 单元测试 + JavaScript 单元测试 + E2E 测试
- GitHub Actions CI/CD 流水线
- 视觉回归测试
- 性能监控
- 安全扫描（CodeQL, Gitleaks, Socket Security）
- 结构化数据（JSON-LD）
- Open Graph 和 Twitter Card 支持
- Sitemap 和 robots.txt
- 链接完整性检查
- 密钥泄露检测
- CSP 和 JSON-LD 一致性验证

### Security
- 严格 CSP 配置
- 无外部依赖（零第三方库）
- 零硬编码凭证
- 所有用户输入使用 textContent

---

## 版本说明

- **Major**: 不兼容的 API 或架构变更
- **Minor**: 向后兼容的功能新增
- **Patch**: 向后兼容的问题修复

[Unreleased]: https://github.com/xiaoyu-hue/xiaoyu-hue.github.io/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/xiaoyu-hue/xiaoyu-hue.github.io/releases/tag/v1.0.0

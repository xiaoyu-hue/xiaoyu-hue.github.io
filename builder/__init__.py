"""builder —— 站点构建包（2026-10 由 build.py 机械拆分而来）。

拆分原则：函数体逐字节搬运，逻辑零改动；build.py 保留为 CLI 入口 + 兼容层。
验收标准：python3 build.py 产物与拆分前逐字节一致。"""

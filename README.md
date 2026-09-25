# 手机部署 QQ 机器人：Termux + Ubuntu PRoot + AstrBot + NapCat

> 面向初学者的**方案与操作清单**，截至 2026-09-25。无需 root；不是 Docker 一键部署。先读[完整教程](docs/从零安装与连接.md)和[安全说明](docs/安全与故障排查.md)。

```text
测试 QQ 号 → Linux QQ / NapCat ──OneBot v11 反向 WebSocket──> AstrBot → 回复
                    ↑                                      ↑
             Termux 内的用户态环境                    Ubuntu PRoot 用户态
                     Android ARM64 手机（两者共享手机网络）
```

## 适用范围和事实边界

- **已在一台 ARM64 安卓手机上观察到**：AstrBot、NapCat 和 ARM64 Linux QQ 在 Termux／PRoot 用户态运行；管理页可达，QQ 在线，OneBot 适配器出现连接；机主确认“可以回复”。实机采用私有备份提取后的隔离实例，不依赖本公开仓库。
- **仍未证明**：全新手机从本文完整安装一次、冷重启后的自动恢复、可归因到 AI 模型生成的逐消息回复。因此本文不是“复制命令即可保证成功”的承诺。
- 本仓库**不提供** QQ、NapCat、AstrBot 的镜像/二进制/账号/模型密钥，也不含原机配置、备份或录屏。NapCat 是第三方 QQ 接入，可能受上游兼容性与账号风控影响；优先用自己的测试账号。
- PRoot 可以提供 Ubuntu 文件系统，但不是完整虚拟机或 Docker Engine。不要把 x86_64/AMD64 私有镜像当成可在 ARM64 手机上原样运行的服务；即使能解包，也不等于可以直接执行其中的架构相关程序。

## 开始之前

1. ARM64 安卓手机、有足够空间与内存、稳定 Wi-Fi，准备可供测试的 QQ 账号。
2. 按 [Termux 官方说明](https://github.com/termux/termux-app#installation)选择安装来源；不要混装签名不同的 Termux/插件。
3. 跟着 [从零安装与连接](docs/从零安装与连接.md)操作；**每一步失败先停下排错，不要继续堆命令**。
4. 网页只在手机本机或可信内网打开；推荐电脑通过 SSH 本地转发访问，**不做公网端口映射**。

## 文档导航

- [从零安装与连接](docs/从零安装与连接.md)：Termux、Ubuntu、AstrBot、NapCat、OneBot、AI 模型与验证。
- [安全与故障排查](docs/安全与故障排查.md)：访问方式、账号密码来源、常见错误、重启与备份。
- [验收记录模板](docs/验收记录模板.md)：自己打勾，录视频前按层验证。
- [上游参考](docs/上游参考.md)：本教程所依据的官方项目和版本变化提示。

## 许可与归属

本仓库仅为独立撰写的教程，文本及原创示例按 [MIT](LICENSE) 提供；Termux、Ubuntu、AstrBot、NapCat、QQ 等各归其权利人所有，其许可证/条款以各官方项目为准。本项目与上述项目没有官方隶属关系。

# 重要提示
该旧版 ElainaBot 因架构问题已停止维护，请使用 v2 框架 https://github.com/ElainaCore/ElainaBot_v2
拥有更全的事件适配，多机器人适配等

<div align="center">

# ElainaBot
ElainaBot 基于 Python 开发的 QQ 官方机器人框架，支持 WH/WS 连接、插件热更新、内存优化、Web监控面板，内置 Markdown/Ark/语音快捷发送封装，支持模板快速导入。

</div>

## 核心特性
- ✨ 插件化架构，支持插件动态热加载/卸载
- 🚀 内置 HTTP/数据库连接池，内存自动回收优化
- 📊 Web 可视化面板：状态、内存、日志实时监控
- 🖼 多图床上传：B站、QQ频道、腾讯云COS
- 💾 MySQL 持久化存储，配套数据库连接池

> 项目仅作学习交流，禁止商用及非法使用

## 交流群
ElainaBot框架交流群：[1085402468](https://qm.qq.com/q/5O3xGoe4so)

## 手动安装
环境要求：Windows/Linux/MacOS；Python3.8+、MySQL5.7+、Git
```bash
# 拉取源码
git clone https://github.com/lengxi-root/ElainaBot.git
git clone https://gitee.com/lengxi-root/ElainaBot.git
cd ElainaBot

# 安装依赖
pip install -r requirements.txt
```
启动后访问面板完成配置：`http://你的ip:5001/web`
若修改配置端口，访问地址端口同步更换

## 使用方法
启动项目后访问面板地址（填入配置的 token）
```
http://localhost:端口/web/?token=access_token
```
面板功能：机器人运行状态查看、内存监控、配置管理等

## 项目结构
```
ElainaBot/
├── config.py          # 全局配置
├── main.py            # 程序入口
├── requirements.txt   # 依赖清单
├── core/              # 核心模块
│   ├── event/         # 事件处理
│   └── plugin/        # 插件管理器
├── function/          # 工具库（上传、数据库、连接池、ws客户端等）
├── plugins/           # 业务插件目录（示例插件/系统插件）
└── web/
    └── app.py        # Flask 控制面板服务
```

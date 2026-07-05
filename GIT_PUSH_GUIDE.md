# Git 推送指南

本项目的 Git 远程仓库使用 **SSH** 方式连接（HTTPS 被防火墙拦截），以后推送代码统一用以下命令：

```powershell
cd d:\数据分析项目
git add -A
git commit -m "你的提交信息"
git push
```

> ⚠️ 切勿使用 HTTPS 方式（会超时），已配置好 SSH Key 映射到 `git@github.com:linziquan/data-analysis.git`

## 如果在新电脑上使用

1. 生成 SSH Key：
```powershell
ssh-keygen -t ed25519 -C "你的标识"
```

2. 复制公钥：
```powershell
Get-Content ~\.ssh\id_ed25519.pub
```

3. 去 https://github.com/settings/keys → Add SSH Key → 粘贴公钥

4. 克隆项目：
```powershell
git clone git@github.com:linziquan/data-analysis.git
```

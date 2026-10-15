# Render 云部署教程（Deadline 哨兵）

目标：把网站放到 Render 上常驻运行，**你的电脑关机也能访问**，
拿到一个固定的 https 地址，例如 https://deadline-sentinel.onrender.com

---

## 前提

1. 一个 GitHub 账号（把代码传上去）。
2. 一个 Render 账号（用 GitHub 登录即可，免费）：https://render.com

---

## 第 1 步：把代码推到 GitHub

在 deadline-sentinel 目录执行（把 URL 换成你自己新建的空仓库）：

    cd C:\Users\Y7000\deadline-sentinel
    gh auth login          # 若没装 gh，就去 github.com 手动新建仓库
    gh repo create deadline-sentinel --public --source=. --push

或者手动：
1. 打开 https://github.com/new ，新建一个空仓库（不要勾 README）。
2. 回到本地：

    git remote add origin https://github.com/<你的用户名>/deadline-sentinel.git
    git push -u origin main

> 注意：`.env`（含你的 Key）已被 .gitignore 忽略，不会被推上去，安全。

---

## 第 2 步：在 Render 部署

1. 打开 https://dashboard.render.com ，用 GitHub 登录。
2. 点 **New +** → **Blueprint**。
3. 选中你刚推的 `deadline-sentinel` 仓库 → Render 会自动读取仓库里的 `render.yaml`。
4. 点 **Apply / Create**，等待构建（约 2-5 分钟）。
5. 成功后你会得到地址： **https://<服务名>.onrender.com**

以后每次 `git push`，Render 会自动重新部署。

---

## 第 3 步（可选）：配置 AI

在 Render 服务页 → **Environment** 里添加：

    BASE_URL = https://openrouter.ai/api/v1
    API_KEY  = 你的key
    MODEL    = openai/gpt-4o-mini

保存后会重启生效。**不配也没关系**，网站自动进入「离线模式」，所有核心功能照常。

---

## 免费版的注意事项（务必知道）

- **会休眠**：免费实例闲置约 15 分钟自动休眠，下次有人访问需冷启动（首次打开慢 30-60 秒），之后正常。
- **月度额度**：免费 750 小时/月，够 1 个服务 7×24。
- **地址固定**：与你的电脑无关，关机也不影响（除非它正在冷启动）。
- 想要**不休眠**：升级 Starter 套餐，约 $7/月。

---

## 常见问题

- 部署失败：看 Render 的 Logs；多半是 `requirements.txt` 或启动命令问题。
- 打开是 502：还在冷启动，等 30-60 秒刷新。
- 端口：Render 会自动注入 PORT 环境变量，`webapp.py` 已支持，无需改动。
- 想自定义域名：Render 后台 Settings → Custom Domain，绑你自己的域名。

---

## 相关文件

- render.yaml            Render 部署蓝图（已在仓库里）
- requirements.txt       依赖清单
- webapp.py              启动入口（读取 PORT/HOST 环境变量）

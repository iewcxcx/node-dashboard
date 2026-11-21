# 节点延迟看板（手机 + GitHub 免费版）

只用手机浏览器 + 两个机场订阅就能做，不用买服务器。
原理：GitHub Actions 每小时在云上帮你测节点，测完把结果写进 `results.json`，
`index.html` 只读这个结果文件来显示。订阅链接只放在 GitHub Secrets 里，
不会出现在网页代码和结果里。

## 这个版本测什么

- TCP 延迟（连节点服务器端口要多久），每节点测 2 次取最快
- 在线 / 离线、丢包率
- 不测下载速度、不测 Netflix / ChatGPT 解锁（那是下一步，想加再加）

**先看懂这个数字再用它：**探测是在 GitHub 的服务器上跑的，显示的是
GitHub 机房 → 节点的延迟，不是你手机 → 节点的延迟。两地排名通常
差不多，能用来淘汰离线 / 明显慢的节点，但不能直接当成你手机上的速度。
想知道手机上的真实延迟，用手机 Clash 客户端自带的批量测速最准。

**支持的订阅格式：**Clash / Mihomo YAML（机场后台最常见的那种）
和 vmess / vless / trojan / ss 链接都支持。复制订阅时优先用机场后台
的 Clash 订阅链接；如果机场还给了通用 / V2Ray 订阅链接，也能用。

## 手机操作步骤

### 1. 注册 GitHub，建仓库
1. 手机浏览器打开 github.com，注册 / 登录。
2. 点右上角 `+` → New repository，名字填 `node-dashboard`。
3. 选 **Public**（免费的 GitHub Pages 要求公开仓库）。
   注意：公开的是节点名字和延迟，订阅链接不会公开。
4. 点 Create repository。

### 2. 把两个订阅放进 Secrets（最重要，别贴到代码里）
1. 进仓库 → Settings → Secrets and variables → Actions → New repository secret。
2. Name 填 `SUB1`，Secret 填第一个机场的订阅链接，点 Add secret。
3. 再建一个，Name 填 `SUB2`，Secret 填第二个机场的订阅链接。
4. （可选）想改面板上显示的机场名字：Settings → Secrets and variables → Actions → Variables，
   新建 `AIRPORT1_NAME`、`AIRPORT2_NAME`，值填机场名字，不填就显示“机场1 / 机场2”。

### 3. 上传这三个文件
把本包里的文件按原样上传到仓库根目录：
- `index.html`
- `probe.py`
- `.github/workflows/probe.yml`

手机上传方法：仓库主页点 Add file → Upload files，选文件上传。
`.github` 是隐藏文件夹，手机文件管理器里直接上传可能看不到它，
可以在仓库里点 Add file → Create new file，文件名填
`.github/workflows/probe.yml`，再把 `probe.yml` 的内容粘贴进去。

### 4. 手动跑一次探测
1. 点仓库顶部的 Actions 标签。
2. 左边选 Probe Nodes，点 Run workflow → Run workflow。
3. 等 1-3 分钟，变绿勾就说明测完了，仓库里会多出 `results.json`。
4. 如果是红叉，点进去看日志，常见原因是 SUB1 / SUB2 的名字写错、
   或者订阅链接复制错了。

### 5. 开启 GitHub Pages，手机看面板
1. Settings → Pages。
2. Build and deployment → Source 选 Deploy from a branch，
   Branch 选 `main`，文件夹选 `/ (root)`，点 Save。
3. 等 1-2 分钟，页面上方会出现你的网址：
   `https://你的GitHub用户名.github.io/node-dashboard/`
4. 手机浏览器打开这个网址就能看，以后每小时自动更新一次，
   打开页面刷新一下就能看到最新结果。

## 以后加机场 / 删机场

不用改代码，最多支持 10 个订阅（SUB1 到 SUB10）。

- 加一个机场：在 Settings → Secrets and variables → Actions 里新建
  Secret，Name 填 `SUB3`（第 4 个就填 `SUB4`，以此类推），值填新机场
  的订阅链接；想改显示名字就再加一个 Variable `AIRPORT3_NAME`。
  下一次每小时自动探测（或手动 Run workflow 一次）后，新节点就
  出现在面板上了。
- 删一个机场：在同一个 Secrets 页面删掉对应的 `SUBx`，下一次探测后
  那个机场的节点就从面板上消失了，`results.json` 会重新生成，
  不用手动删数据。
- 注意：不要留空的 SUB 编号占位，空的会被跳过，不影响其他机场。

- 面板显示“没有匹配的节点”：先去 Actions 看第一次探测跑完没有。
- 某个节点一直离线：先看机场客户端里这个节点本身能不能连，
  云上测的是 TCP 端口，连不上就显示离线。
- 想改成每 30 分钟测一次：把 `probe.yml` 里的 `0 * * * *` 改成
  `*/30 * * * *`，注意免费版每小时次数有限，别改得太频繁。
- 想加速度和解锁测试：下一步要装 sing-box / mihomo 做代理测试，
  比这个版本复杂，先把这个基础版跑通再加。

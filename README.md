# Frame — Sunlei 摄影集

Astro 网站、只读 NAS JPG 处理工具、本地选片页、Cloudflare Worker + 私有 R2 图片服务。线上域名：`frame.sunlei.page`（配置目标，尚未部署）。

当前是 2024 年试点：扫描 5,193 张 JPG（约 24.90 GiB），跨活动抽样查看 198 张，作品集初选 30 张。不是全年逐张终审。候选片默认未确认，不能上传或正式发布。

## 本地预览

需要 Node.js 24+，Python 3.10+（当前环境 Python 3.9 已运行验证）。

```sh
npm ci
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
npm run dev
```

首页 `/`，系列页 `/albums/land/`，选片台 `/review/`。首次克隆没有图片，需要挂载 NAS 后运行下述扫描和处理。选片修改保存在浏览器，导出后再导入项目；不会自动发布。

## 日常选片流程

```sh
.venv/bin/python scripts/photos.py scan /Volumes/MyDocument/Photos/2024
.venv/bin/python scripts/photos.py sample --per-event 6
.venv/bin/python scripts/photos.py prepare
# 在 /review/ 调整，导出 frame-selections.json，然后：
.venv/bin/python scripts/review.py /完整路径/frame-selections.json
npm run build
```

`sample` 是均匀抽样，不是全库自动评分。初选理由和题名由人工视觉检查生成，尚需大图复核。日期目前取活动目录，`dateSource: folder` 明确记录，不冒充精确 EXIF 时间。`content/selections.json` 可以继续加入经检查的候选 ID；本地 inventory 保存 ID 与源路径的映射。

RAW、视频不处理。不会重命名或修改 NAS 文件。原图先应用方向与色彩配置，再生成长边 480/960/1600/2560 的 JPEG/WebP；不放大、不自动裁切、不套滤镜。展示图编码前清除继承元数据。对象名含原图内容哈希与处理版本；相同文件不会重复转换。原片、缓存、展示图和凭证均不进入 Git。原片备份独立于发布系统。

## 发布

1. `npx wrangler login`，登录自己的 Cloudflare 账户。
2. 在同一账户创建 `sunlei-frame-photos` R2 bucket。保持私有，关闭 r2.dev 和公开 bucket 域名。
3. 在选片页确认照片、导出并导入清单。
4. `python3 scripts/upload.py` 查看上传计划；`python3 scripts/upload.py --execute` 上传确认的展示图。使用 Wrangler 登录凭证，不要求把密钥写到项目。中断后会按上传记录继续。
5. `npm run deploy` 校验上传记录、构建正式页面并发布到 `frame.sunlei.page`。

正式构建使用独立 `site-public` 目录，不复制本地照片；照片只从 R2 读取。Worker 只提供本次已确认清单中的图片路径，未确认文件和已撤下图片即使仍在 bucket 也无法通过网站读取。选片页会从正式构建移除。域名走 Worker，R2 不提供旁路入口。

`content/uploaded.json` 是上传成功记录。若手动删除 R2 对象，需清理对应记录后重新上传；当前不自动校验云端对象是否被外部删除。撤下公开照片还需考虑用户缓存；版本回退不会撤回已经下载的图片。

GitHub Actions 默认只验证构建。配置 production 环境的 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` Secrets，并设置仓库变量 `DEPLOY_ENABLED=true` 后，main 更新才自动部署。Token 仅授予对应账户 Worker 部署和所需 R2/域名权限。NAS 处理与上传在本机执行，CI 不接触 NAS。使用上传成功的清单提交来触发部署。

## 验证

```sh
npm test
npm run build
npm audit
```

测试覆盖源文件不变、EXIF 方向、元数据清除、跨站清单拒绝、未知/重复 ID 拒绝及只上传已确认图片。浏览器需验证桌面/手机布局、全屏键盘与触摸、选片本地保存和导出。构建成功不代表远程部署或 Access 已配置。

字体 Newsreader 随网站本地提供；许可证位于 `site-public/fonts/OFL.txt`。

架构依据：[Worker 优先路由](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/)、[R2 私有存储](https://developers.cloudflare.com/r2/buckets/public-buckets/)。

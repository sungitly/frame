# Frame — Sunlei

目标域名 `frame.sunlei.page`。当前新版可在本机使用，尚未部署域名。30 幅作品，3 本摄影书；由全库评分候选中的 287 张联系表复看、挑选和编排。

## 本地浏览与调整

```sh
npm ci
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
npm run build
npm run studio
```

打开 http://127.0.0.1:4321/ 。`/review/` 是本地整理页：查看全部/已入选/未入选/重复，按活动与文件名搜索，放大、对比重复照片、加入或移出、批量取舍、改标题和相册、恢复初选。选择记录即时保存在 `.local/overrides.json`，点击“更新影集”重建本地页面。备份取舍按钮导出 JSON v2；该备份当前供留档，不用旧版 `review.py` 导入。

`npm run dev` 仅用于页面开发，不提供选片 API。整理页只存在于本机服务，不进入公开部署。

## 2024 年照片库

只读取 JPG/JPEG，不处理 RAW，不改 NAS 原件。全量 5,193 张、约 24.90 GiB。生成去除 EXIF/GPS 的 sRGB JPEG：480 和 1600 长边；Frame 额外从原始 JPG 生成 2560。不放大、不自动改色。日期优先 EXIF 拍摄时间，缺失时才使用目录日期。

当前 Mac 已完成扫描和评分，缓存可以复用。新机器从头准备（macOS 15+，Swift 命令行工具）：

```sh
.venv/bin/python scripts/photos.py scan /Volumes/MyDocument/Photos/2024
.venv/bin/python scripts/analyze.py
swiftc -O scripts/vision-score.swift -o .local/vision-score
.venv/bin/python scripts/score.py
.venv/bin/python scripts/curation.py classify
.venv/bin/python scripts/curation.py materialize
npm run build
```

两站可共享 Photo 的分析缓存：在 Frame 的 `.local/library-config.json` 中设置 `{"dataRoot":"本机 Photo/.local 的绝对路径"}`，然后 classify / materialize。分享的是预览与分析，两个站的取舍记录互相独立。分析脚本应在拥有 inventory 的 Photo 目录执行。当前索引针对一个年度；跨年扩展需要增加命名空间，勿覆盖已有年度索引。

自动选择和编辑取舍分层：`.local/library.json` 是全库初选；`content/editorial.json` 保存策展决定；`.local/overrides.json` 保存用户修改且优先级最高。Frame 的 `content/albums.json` 定义书名、封面与页序，新增照片追加到所选书末尾。重新 classify 不覆盖手动修改。原片路径、完整库、模型标签和未入选照片均不提交 Git。

评分在本机 Apple Vision 运行，不调用远程视觉服务。审美分数只辅助排序，低分不直接删除。重复检测采用 SHA-256 精确匹配，及同活动 3 秒内双感知哈希相似且检测人脸数量相同的保守比较，保留综合表现较好的一张；不会把一串相似照片传递合并。它仍可能漏掉跨时刻重复或轻微废片；没有声称人工逐张终审 5,193 张，也不根据人脸推断亲属身份。

## 发布

源码与入选清单提交 GitHub，照片展示图上传私有 R2，不把原始 JPG 放入源码仓库。`sunlei-frame-photos` 已创建，r2.dev 关闭，尚未上传照片。

```sh
.venv/bin/python scripts/upload.py          # 查看实际入选展示图的上传计划
.venv/bin/python scripts/upload.py --execute
npm run deploy
```

上传支持断点续传，记录在 `content/uploaded.json`。删除远程对象后要移除对应记录再上传。正式构建从独立 `site-public` 目录取静态文件，不带入本地照片、整理页和照片库 API。Worker 只允许当前入选清单中实际规格的图片路径；移出后即使旧文件仍在 bucket，也不能通过网站读取。

Photo 上线前必须配置覆盖域名全部路径的 Cloudflare Access：家人邮箱 Allow 列表、邮箱验证码登录，填入 `wrangler.json` 的 `ACCESS_TEAM_DOMAIN` 和 `ACCESS_AUD`。Worker 在所有页面和照片前验证 JWT；缺配置拒绝访问。不要开放 R2 旁路域名。Frame 为公开摄影书。

GitHub Actions 默认只构建验证；部署需要 production 环境的 Cloudflare Secrets 与 `DEPLOY_ENABLED=true`。图片处理与上传在本机完成，CI 不读取 NAS。Photo 仓库必须保持 private。当前 Access 尚未完成，不能把家庭站当成已经上线。

## 检查与参考

`npm test`：原片与方向、元数据清除、实际上传规格、手动优先、低分保留、跨站写入拒绝、未知 ID 拒绝与恢复初选。`npm run build:production` 检查正式页面构建，不能代替真实 Access 登录验收。

[AfterFrame 参考说明](AFTERFRAME.md)。Newsreader 字体许可证位于 `site-public/fonts/OFL.txt`。

# Bilibili 一键删除脚本

此文件夹包含一个用于删除 B 站个人评论和动态的自动化脚本。通过解析登录 Cookie，脚本可以自动获取用户 ID，下载 AICU 评论数据，并批量删除评论或动态。

## 文件说明

- `bilibili_oneclick_delete.py` - 一键删除脚本。
- `getreply (1).json` - 示例 AICU 导出 JSON 文件（用于测试或手动模式）。

## 功能特性

- **自动 Cookie 解析**：支持粘贴完整 Cookie 字符串或逐项输入，支持多行粘贴。
- **自动 AICU 数据获取**：从 Cookie 中提取 DedeUserID，自动构造 AICU API 请求，下载评论 JSON 数据，无需手动保存文件。
- **批量删除评论**：支持从 AICU 数据删除评论，支持嵌套字段解析。
- **批量删除动态**：使用正确的 API 参数和 CSRF 令牌删除动态。
- **错误处理**：包含重试机制、API 错误检查和用户友好的提示。
- **灵活模式**：支持手动上传 AICU JSON 或自动下载模式。

## 使用方法

1. **安装 Python 3**：确保系统已安装 Python 3.x。

2. **安装依赖**：

   ```powershell
   pip install requests
   ```

3. **运行脚本**：

   ```powershell
   python bilibili_oneclick_delete.py
   ```

4. **输入登录 Cookie**：
   - 粘贴完整 Cookie 字符串，例如 `SESSDATA=...; bili_jct=...; DedeUserID=...`。
   - 或按回车分行粘贴，脚本自动解析。
   - 也可逐项输入 `SESSDATA`、`bili_jct`、`DedeUserID`。

5. **选择删除操作**：
   - `1`：AICU 导出 JSON 删除评论（手动模式：输入 JSON 文件路径）
   - `2`：直接从 B 站历史删除评论（可能因接口限制失效）
   - `3`：删除动态
   - `4`：先 AICU 评论删除，再删除动态（推荐）
     - 在此模式下，脚本会询问是否自动获取 AICU 数据：
       - 选择 `y`：自动从 Cookie 提取 DedeUserID，构造请求下载 JSON 并删除。
       - 选择 `n`：输入本地 AICU JSON 文件路径。

6. **执行删除**：
   - 脚本会显示进度，处理每个评论/动态。
   - 删除成功后显示确认信息。

## 脚本细节解释

### Cookie 解析
- 脚本解析 Cookie 中的 `SESSDATA`（会话令牌）、`bili_jct`（CSRF 令牌）和 `DedeUserID`（用户 ID）。
- 用于 API 请求的认证和参数构造。

### AICU 数据获取
- AICU 是 B 站的评论导出工具。
- 脚本自动构造请求：`https://ai-comment.bilibili.com/getreply?uid={DedeUserID}`，下载 JSON 数据。
- 数据包含评论的 `type`、`oid`、`rpid` 等必要参数。

### 删除评论
- 使用 B 站删除评论 API：`https://api.bilibili.com/x/v2/reply/del`
- 参数：`type`、`oid`、`rpid`、`csrf`（从 bili_jct 提取）。
- 支持嵌套 JSON 字段解析（如 `data.replies` 或 `data` 下的评论列表）。

### 删除动态
- 使用动态删除 API：`https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/rm_dynamic`
- 参数：`dynamic_id`、`csrf`。
- 动态 ID 从 AICU 数据或用户输入获取。

### 错误处理
- 检查 API 响应状态码和错误消息。
- 对于 `-400` 错误，提示检查 Cookie 或 AICU 数据。
- 重试机制：删除失败时自动重试最多 3 次。
- 网络错误时显示具体错误信息。

### 安全注意
- Cookie 仅在内存中使用，不保存到文件。
- 删除操作不可逆，请谨慎使用。
- 建议先在小批量测试。

## 注意事项

- 该脚本基于公开 B 站 API 接口实现，可能因 API 变更而失效。
- 操作前请备份账号内容并确认登录 Cookie 正确。
- 删除操作不可恢复，请谨慎使用。
- 如果遇到 API 风控，建议更换 IP 或稍后重试。
- AICU 数据结构可能变化，脚本会尝试多种解析方式。
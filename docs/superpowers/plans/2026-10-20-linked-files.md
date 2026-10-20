# 待办关联文件 Implementation Plan

> **For agentic workers:** Use inline execution in this chat for the approved scope. Preserve the existing dirty checkout; do not stage unrelated changes.

**Goal:** 每条待办关联多个本机文件/目录，在侧边栏汇总并追溯经验。

**Architecture:** 在现有单 HTML 应用扩展 linkedFiles 数据、表单和汇总页面；Python 服务仅新增定位已保存关联路径的接口。汇总从待办派生，不引入第二份关联数据。

**Tech Stack:** 原生 JavaScript、Python 标准库、jsdom、unittest。

## Global Constraints

- 引用原路径，不复制文件；备份只包含关联记录。
- 保留已有改动和保存协议；旧待办缺少 linkedFiles 时仍可编辑。
- POSIX 和 Windows 绝对路径；目录/文件、说明、搜索和中英文界面。
- 文件管理器仅定位资源，不执行被关联文件。

### Task 1: 待办关联与汇总

**Files:** personal-office-workbench.html、linked_files_test.cjs、smoke_test.cjs

**Interfaces:** `normalizeLinkedPath(path)` 返回规范路径；`normalizeLinkedFiles(items)` 返回去重的 `{path,kind,note}[]`；`linkedFileIndex()` 返回包含 tasks 的汇总记录；`readLinkedFileEditor(root, validate)` 提交前验证表单。

- [x] 用 jsdom 编写完整用户流程测试并先运行确认缺少关联入口。
- [x] 实现路径规范化、旧数据兼容、关联编辑器、任务表单草稿/提交和编辑取消隔离。
- [x] 增加侧边栏 files 视图、搜索/类型筛选、待办跳转、路径复制/目录定位和任务关联摘要。
- [x] 更新导航数量断言并运行 `node linked_files_test.cjs` 与 `node smoke_test.cjs`。

### Task 2: 定位目录与备份验证

**Files:** server.py、server_test.py

**Interfaces:** POST /api/linked-files/reveal `{taskId,path}` 返回 `{ok:true}`，失败返回 JSON error。请求仅能定位已持久化关联；不允许外站触发。

- [x] 测试不存在、非关联、跨源路径的拒绝，及参数列表形式的 macOS/Windows 调用。
- [x] 实现本机 Origin/Host 检查和已保存关联验证，定位前检查存在及类型。
- [x] 验证 PUT、ZIP/JSON 往返保持文件说明与关联。
- [x] 运行 `python3 -m unittest -v server_test.py`。

### Task 3: 回归与交付

**Files:** package.json、README.md

- [x] 把新 UI 测试接入 npm test，说明关联输入与备份边界。
- [x] 运行 `npm test` 和 `git diff --check`，检查本轮 diff，修复回归。
- [x] 报告完成的交互、验证证据及真实系统桌面验证边界。

## Validation evidence

- `PYTHONPYCACHEPREFIX=/tmp/workbench-linked-files-pycache npm test` passed: 5 linked-file API tests, 8 lifecycle tests, UI smoke checks, linked-file flow and shutdown safety checks in an isolated upload snapshot.
- `git diff --check` passed.
- Tabbit browser validated grouped resources, completed/abandoned status, editing and saving notes, search, and scrolling the multiple-link editor using isolated temporary data.
- Windows Explorer command construction is mocked; no Windows desktop acceptance is claimed.

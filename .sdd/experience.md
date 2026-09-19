# 项目经验

存放位置：`<active_project_path>/.sdd/experience.md`。仅由编排器在修复复验后判断、去重并更新；Developer/Tester 返回建议与证据。开始任务时按关键词检索相关标题，无命中就继续，不读取全部历史。

流程依据：`<harness_root>/harness-core/protocols/experience-loop.md`。经验不覆盖当前项目契约与所选规范；未复验、原因推测、一次性问题留在错误记录，不为每次报错增加条目。

## 条目格式（说明，不是已发生的经验）

实际记录时使用有辨识度的标题，填写：

- 关键词与适用条件：已知的技术栈、版本或触发场景。
- 现象与已证实根因；有效修复；下次如何避免。
- 来源任务或独立 Bugfix 描述；复验日期；证据的项目相对路径和具体章节，交付时返回实际绝对路径。
- 同类复发时更新原条目，说明旧经验未能避免问题的已核实原因，补充新的验证证据；失效结论标明并保留旧来源。

有跨项目价值时在原条目附简短全局候选；经用户授权，由编排器更新 `<harness_root>/memory/harness-experience.md` 并回链对应标题。全局记录不是自动生效的强制规则，不自动修改 Skill 或技术规范。不记录密钥、敏感原始数据或完整日志。

## 分类同时标闲聊与超范围类状态时优先走同一兜底

- 关键词与适用条件：`qa.py`、M-003 提问分类、`small_talk`、`needs_clarification`、`requires_live_data`、`out_of_scope`、AC-017、AC-023。触发：分类 JSON 同时给出闲聊类型与超范围类 processing_status。
- 现象：信息不足或超出 IT 的提问被当成闲聊并追问，而不是同一条超范围兜底。已证实根因：M-003 可同时输出 `message_type=small_talk` 与 `needs_clarification`/`out_of_scope`；编排原先见闲聊就短路走 M-004。
- 有效修复：超范围类状态优先走配置中的同一 `OUT_OF_SCOPE_TEXT`，不追问、不调实时工单工具。真闲聊（`small_talk` + `ready`，或命中寒暄 hint）仍走 M-004。
- 下次如何避免：实现/验收分类编排时先看 processing_status 是否属于超范围三类，再决定闲聊短路；自验同时覆盖 AC-017 与 AC-023。
- 来源：T-011 Developer 自修；Tester 61a68ed9 于 2026-09-19 复验。证据：`.sdd/test-reports/test-T-011.md` 检查表 TC-03/TC-08/TC-09 与文末「经验候选」节。绝对路径：`/Users/kxy/cursor/class_projects/Develop_Helper/Projects_Repo/Customer_Service/.sdd/test-reports/test-T-011.md`。

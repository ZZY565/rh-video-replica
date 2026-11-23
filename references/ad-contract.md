# 广告改编约定

根字段：`mode:"ad_structure_adaptation"`、`full_ad_replica:false`。

`reference`：`origin:"real_commercial"`、`title`、`source_url`、`full_duration_seconds`。
`product`：`name`、`image`、`is_concept`、`provided_by_user`、`verified_claims:[]`。镜头主张必须属于已核实列表。
`scope`：`reference_range_seconds:[起,止]`、`output_duration_seconds`、`aspect_ratio`，并记录保留/替换/不承诺项。

`shots`按连续输出时间排列，每项包含`id/output_start/output_duration/reference_start/reference_end/observed/transfer/target_visual/acceptance/claims`。

例如：A段输出0–1.2秒，原片47–48.2秒，观察为翻动的豆子、暖光和烟雾；转移高反差工艺开场功能；新画面为新生成的翻豆近景；验收豆子运动连续、无原品牌文字；claims为空。

内容段未必对应一个硬切镜头。校验只检查连续时间、范围和主张来源，不证明画面准确。选段不得称为整条广告完整复刻。

内容验收记录用`id/status/evidence_times/observations/deviations/remedy`，状态为`pass/partial/fail/not_assessed`。分别报告部分满足和完整满足，不合成无依据的“复刻率”。

`ad_audit.py compare`将段落起点与候选切点一对一匹配，只作诊断。一个内容段可能含多个切点，检测也会误报和漏报，不能作为唯一验收门槛。

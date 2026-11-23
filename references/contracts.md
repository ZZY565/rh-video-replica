# 文件协议

analysis.json 必须记录：reference 文件名/哈希、抽样方法、音频处理状态、镜头时间区间、可见观察、证据帧索引、置信度、尚不确定的动作。即使参考有音轨，也不意味着画面模型能够听见它。

storyboard.json 每镜头记录：id、start、duration、reference_range、retained_structure、adaptation、visual、caption、prompt、consistency_checks。不要将新创意记为参考观察。

edit-plan.json 最小示例：

```json
{
  "width":720,"height":1280,"fps":30,
  "brand":"品牌名称","footer":"创意演示",
  "music":"inputs/mixed-audio.wav",
  "shots":[
    {"kind":"video","source":"inputs/shot.mp4","start":0,"duration":3,
     "headline":"主标题\n第二行","subline":"副标题","layout":"top"},
    {"kind":"image","source":"inputs/product.png","duration":3,
     "headline":"品牌收束","layout":"top","cta":"进一步了解"}
  ]
}
```

标题应主动换行；模板按720宽、52px标题设计，通常每行不超过10个汉字。`layout` 可为 top/bottom，标题超过可用宽度会停止渲染。画幅尺寸取偶数。时长要落在帧格点（30fps可用3、4等整数秒），每镜头不超过60秒，总片不超过120秒。`music` 可省略，此时导出无声成片，报告须说明。视频源必须覆盖 start+duration，不静默循环补时。

产物分类：reference 自制参考或真实外部样本；raw 云端原始输出；final 本地品牌合成；fallback 照片动效。不要把 fallback 描述成 AI 视频模型结果。

V2横版落版可用layout:"editorial"，干净画面用overlay:false。图片可设置zoom_start与zoom_end（1到2之间），商品落版建议1.02→1.0轻微拉远，避免袋口或杯柄裁切。动效仍属于静态主视觉合成，交付中须与云端运动镜头区分。

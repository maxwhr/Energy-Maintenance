# Task 25B-R2-U3 华为官方 HTML 支持知识报告

## 采集结果

- 固定种子页扫描：17。
- 独立 HTML FAQ：25。
- 匿名公开 support 文档：5，分别覆盖 SmartLogger 手册、SmartLogger/SmartMGC 告警参考、LUNA2000 ESS 手册、SUN2000 MAP0 手册和 SUN2000 M1 手册。
- 总候选：30；采集幂等键由来源、section locator 与内容 hash 组成。

## 内容处理

采集器只保存 FAQ 正文、章节标题、结构化 locator、安全提示和处理步骤；排除导航、页脚、Cookie 文案和营销段落。每个候选保留 source URL、产品族、设备型号、采集时间与内容 hash，未将整页 HTML 原样写入正式正文或日志。

## 公开访问与阻断

公开 supportgateway 仅在匿名可访问时使用。EDOC1100325389（SmartGuard）和 EDOC1100341318（MG0）未得到可用正文，EDOC1100358764 无有效公开内容，因此记录为覆盖缺口而不是绕过访问控制。`access_control_bypassed=false`。

## 官方来源样例

- https://solar.huawei.com/en/products/sun2000-150k-mg0/support/
- https://solar.huawei.com/en/products/LUNA2000-7-14-21-S1/support/
- https://support.huawei.com/enterprise/en/doc/EDOC1100330465
- https://support.huawei.com/enterprise/en/doc/EDOC1100108365
- https://support.huawei.com/enterprise/en/doc/EDOC1100394512


# Task 25B 文档解析与语义切分

## 支持范围

继续支持 TXT、MD、text-based PDF 和 DOCX，不新增 OCR 文档解析、Excel、PowerPoint、压缩包或图像文档解析。

`DocumentParser` 输出页级结构，`SemanticChunker` 生成语义 chunk。DOCX 标题样式映射为 Markdown heading，表格按整行文本保留，内嵌图片记录占位符；PDF 保留页码。

## Chunk 元数据

每个新 chunk 记录：

- `parser_version=structured_parser_v1`
- `chunker_version=semantic_chunker_v1`
- `section_path`
- `source_locator`
- `page_number`
- `block_types`
- `device_models`
- `fault_codes`
- `content_hash`
- duplicate status

切分优先按标题、段落、列表、表格和安全警告边界。超长段落先按句子拆分；型号和故障码不会使用任意字符窗口从中间截断。空 chunk 拒绝，content hash 重复 chunk 去重。

## 版本与重建边界

本任务没有无条件重切正式知识。只创建并索引 `Task25B_` 工程受控文档。正式 approved 文档全量重切/重建必须同时满足显式 CLI 参数和 `TASK25B_ALLOW_FULL_REINDEX=true`；本次开关为 false，脚本返回 `BLOCKED_BY_GATE`。

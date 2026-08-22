# 子站附件缺失补导报告

## 问题背景
ima知识库搜索"2026届新生入学手册PDF"时，只返回文章网址而没有附件内容。
排查发现：外部子站（招生就业/国际教育/亳文化研究/信息公开）导入时使用 import_urls API 只导入文章正文，**从未处理过页面内附件**。

## 扫描结果（check_subsite_attachments.py）
- 子站文章总数: 1983
- 含附件文章: 190
- 扫描到未导入附件: 242个唯一URL
  - 类型分布: 117 pdf / 67 xls / 54 doc / 2 zip / 2 rar
  - 栏目分布: 招生就业 226 / 国际教育 9 / 亳文化研究 6 / 信息公开 0

## 补导执行结果
### 第一批（ima_subsite_att_import.py 后台任务）
- 成功: 221
- 失败: 17（其中15个为下载超时，后重试成功；2个为源站404）
- 跳过: 4（压缩包，走归档流程）

### 第二批（15个超时文件重试）
- 成功: 15 / 15
- 说明: 首次失败因下载超时，实际源站文件可用

### 第三批（4个压缩包，ima_archive_import 流程）
- jyxx_2025.zip: 解压10个文件，全部上传
- gjjy_2020_1.rar: 解压5个文件，全部上传
- gjjy_2020_2.rar: 解压4个文件，全部上传
- bwhyjzx_2024.zip: 解压6个文件，全部上传
- 合计新增25个归档文件

## 最终状态
| 进度项 | 补导前 | 补导后 |
|---|---|---|
| atts_done | 1021 | **1257** (+236) |
| archives_done | 30 | **34** (+4) |
| files_done | 115 | **140** (+25) |

## 不可恢复文件（源站已删除）
1. https://www.bzuu.edu.cn/_upload/article/files/9a/0b/531c8cdc46d99efd5b21dd80ebc6/ec326cf2-9daf-4cc9-bad1-042a74104bac.doc (404)
2. https://www.bzuu.edu.cn/_upload/article/files/9a/0b/531c8cdc46d99efd5b21dd80ebc6/8fd6fc42-4cd0-4e92-b449-60c0e2b90ad2.docx (404)
   （均来自 https://kdfz.ustc.edu.cn/2025/0529/c5271a686505/page.htm）

## 关键验证
- 2026新生入学须知PDF已导入: ✅
  https://www.bzuu.edu.cn/_upload/article/files/31/5d/ca17cf414ae7a1f21f0abc556a4a/b8ceacc8-da35-49c4-ae29-46c7dc7da94a.pdf

## 经验教训
1. **import_urls 只导正文，不导附件**——子站导入必须单独走附件链路
2. 附件下载偶发超时应重试，不要直接判失败
3. 压缩包（zip/rar）必须走归档脚本（MEDIA_TYPE 不含 zip/rar）
4. 扫描日志 /root/subsite_att_check.log 可追溯每个附件来源文章

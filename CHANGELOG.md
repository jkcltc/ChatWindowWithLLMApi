# 0.25.2 in building (25.08.26)  
--- 
## 特性优化 
- 优化、重构了API的模型导入设置界面 
- 系统提示现在支持`{{model}}`:模型ID和`{{time}}`:时间 

## bug 
- 发现了非流式模式对话时崩溃的问题（已解决） 
- 简单测试了所有功能，进行了修复 
- 新出现的Dummy线程问题 


# 0.25.2 in building (25.07.15)  
---  
## 头像创建  
- 支持从历史记录中由AI创建头像  
- 完全重构文生图模块  
- 发现了头像模块和背景模块的高相似性，考虑合并  
  
## 特性优化  
- 优化了纯文本窗口，提高了可读性，一些元素可根据选项更新  
  
## BUG修复  
- 解决了气泡在流式过程中的异常扩展，缓解了抖动问题  
  
# 0.25.1 (25.07.06) 
--- 
## New Features 新增功能  
- 对话并发汇流  
Dialog Concurrency Convergence  

- 对话用量汇总分析  
Dialog Usage Summary Analytics  

## Feature Updates  特性更新
- 聊天窗口更改为气泡式  
Chat window changed to Bubble-style  

- 长对话优化现在可选择是否携带系统提示  
Long-dialog optimization now supports optional inclusion of system prompts  

- 新增大量快捷键  
Added numerous keyboard shortcuts  

- 对话现在会记录AI思考链、来自服务商的返回信息等元数据  
Dialog now records metadata (AI Chain of Thought, provider responses, etc.)  

- 重构了大量代码  
Significant code refactoring  

## Bug Fixes  问题修复  
- 修复了系统提示更新窗口导致的崩溃  
Fixed crash caused by system prompt update window  

- 暗色主题正常工作了  

Dark Theme now functions properly  

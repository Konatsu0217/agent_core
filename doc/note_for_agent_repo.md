# 工程名词

- SRE


# about LLM
## 架构
- Decoder Only
- RoPE / 1-Hot?
- KV-Cache: 缓存已经计算过的key-value对，避免重复计算
- FlashAttention?
- RMSNorm
- GQA

## 训练/微调
- SFT: 全量
- PEFT: LoRA/QLoRA
- 灾难性遗忘
- Model Merging

## 对齐 Alignment
教模型如何成为一个“乐于助人、无害且诚实”的AI助手 
- RLHF: （SFT -> 训练奖励模型 -> 强化学习）
- DPO(Direct Preference Optimization):
- 

## 推理
- TTFT(Time to First Token):首token耗时，实时交互不应该超过2秒
- 量化(Quantization):节省显存 + 低精度运算更快
  - GPTQ 
  - AWQ
- 推理服务器-vLLM  /  TensorRT-LLM  /  CTranslate2
  - 连续批处理 (Continuous Batching)
  - 分页注意力 (PagedAttention)
- 并行计算
  - 张量并行(Tensor Parallelism)：将模型**参数矩阵**拆分在多个GPU上，每个GPU只计算模型的一部分，最后将结果合并。
  - 流水线并行 (Pipeline Parallelism)：将模型的不同 **层** 分布在多个GPU上，每个GPU只计算模型的一部分，最后将结果合并。
  - 【MOE】专家并行
- transformer + kv cache

## mcp/tool/skill

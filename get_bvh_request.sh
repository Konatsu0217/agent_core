curl --request POST \
  --url https://api.siliconflow.cn/v1/chat/completions \
  --header 'Authorization: Bearer sk-vezwjwedaavmvvqduumclvzelriykxrkqmxuqoucqqyyjbof' \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "Pro/deepseek-ai/DeepSeek-V3.2",
  "messages": [
  {
    "content": "123",
    "role": "system"
  },
  {
    "content": "用户查询: 查一下北京的天气, system: 你的回复必须为json格式{"response": "你的回复","action": "简短、精准地表述你要做的肢体动作，使用英文","expression": "从我为你提供的tool_type = resource中选择表情(可选，如果未提供则为空字符串)"}",
    "role": "user"
  },
  {
    "content": null,
    "role": "assistant",
    "tool_calls": [
      {
        "function": {
          "arguments": {
            "city": "北京",
            "date": "today"
          },
          "name": "local.get_weather"
        },
        "id": "019b5934411d0ad08fa64ea96856ba05",
        "type": "function"
      }
    ]
  },
  {
    "content": "北京在 today 是晴天",
    "role": "tool",
    "tool_call_id": "019b5934411d0ad08fa64ea96856ba05"
  }],
  "stream": false,
  "max_tokens": 4096,
  "enable_thinking": false,
  "thinking_budget": 4096,
  "min_p": 0.05,
  "stop": null,
  "temperature": 0.7,
  "top_p": 0.7,
  "top_k": 50,
  "frequency_penalty": 0.5,
  "n": 1,
  "response_format": {
    "type": "text"
  },
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "<string>",
        "description": "<string>",
        "parameters": {},
        "strict": false
      }
    }
  ]
}
'
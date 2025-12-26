import requests
from openai import OpenAI

client = OpenAI(
    api_key="sk-vezwjwedaavmvvqduumclvzelriykxrkqmxuqoucqqyyjbof",  # 从https://cloud.siliconflow.cn/account/ak获取
    base_url="https://api.siliconflow.cn/v1"
)


# 使用 WeatherAPI 的天气查询函数
def get_weather(city: str):
    return f"The weather in {city} is clean with a temperature of -35°C."



# 定义 OpenAI 的 function calling tools
tools = [
    {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'description': 'Get the current weather for a given city.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {
                        'type': 'string',
                        'description': 'The name of the city to query weather for.',
                    },
                },
                'required': ['city'],
            },
        }
    }
]


# 发送请求并处理 function calling
def function_call_playground(prompt):
    messages = [{'role': 'user', 'content': prompt}]

    # 发送请求到 OpenAI API
    response = client.chat.completions.create(
        model="Pro/deepseek-ai/DeepSeek-V3.2",
        messages=messages,
        temperature=0.01,
        top_p=0.95,
        stream=False,
        tools=tools
    )

    # 处理 API 返回的工具调用请求
    func1_name = response.choices[0].message.tool_calls[0].function.name
    func1_args = response.choices[0].message.tool_calls[0].function.arguments
    func1_out = eval(f'{func1_name}(**{func1_args})')

    # 将结果添加到对话中并返回
    messages.append(response.choices[0].message)
    messages.append({
        'role': 'tool',
        'content': f'{func1_out}',
        'tool_call_id': response.choices[0].message.tool_calls[0].id
    })

    # 返回模型响应
    response = client.chat.completions.create(
        model="Pro/deepseek-ai/DeepSeek-V3.2",
        messages=messages,
        temperature=0.01,
        top_p=0.95,
        stream=False,
        tools=tools
    )

    return response.choices[0].message.content


# 示例使用
prompt = "how is the weather today in beijing, shanghai, guangzhou?"
print(function_call_playground(prompt))
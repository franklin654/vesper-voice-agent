from langchain_openai import ChatOpenAI

qwen_llm = ChatOpenAI(
    name="qwen2.4-14b-q4",
    base_url="http://127.0.0.1:12001",
    api_key="dsafadsfdsafasd"
)

while True:
    human = input("Enter Message: ")
    for message in qwen_llm.stream(human):
        print(message.content, flush=True, end="")
    print()
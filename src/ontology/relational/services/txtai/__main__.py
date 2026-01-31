
import os

os.environ["KMP_DUPLICATE_LIB_OK"] = "True"

from txtai import LLM

# breakpoint()
# llm = LLM(path="lm_studio/local-mistral-7b-openorca", method="litellm", verbose=True, api_base="http://localhost:4000", api_key="sk-1234")
llm = LLM(
    path="lm_studio/anthropic-claude-haiku-4.5",
    method="litellm",
    api_base="http://localhost:4000",
    api_key="sk-1234",
)


def extract_entity_relationship_graph(text: str):
    prompt = f"""<|im_start|>system
    You are a friendly assistant. You answer questions from users.<|im_end|>
    <|im_start|>user
    Extract an entity relationship graph from the following text. Output as JSON

    Nodes must have label and type attributes. Edges must have source, target and relationship attributes.

    text: {text} <|im_end|>
    <|im_start|>assistant
    """

    return llm(prompt, maxlength=4096, defaultrole="user")


# if __name__ == "__main__":

with open("txtai-input.txt") as file:
    result = file.read()

data = extract_entity_relationship_graph(result)
print(data)

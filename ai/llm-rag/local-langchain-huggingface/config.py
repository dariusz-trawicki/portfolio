from transformers import pipeline

#device=0 is for GPU, device=-1 is for CPU
def load_llm_pipeline():
    return pipeline("text2text-generation", model="google/flan-t5-small", max_new_tokens=256, device=-1)

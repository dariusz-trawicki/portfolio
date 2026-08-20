# pip install diffusers transformers accelerate torch
from diffusers import StableDiffusionPipeline
import torch

# Load model
pipe = StableDiffusionPipeline.from_pretrained(
    "runwayml/stable-diffusion-v1-5",
    torch_dtype=torch.float16,
)

# pipe = pipe.to("cuda")  # GPU required
pipe = pipe.to("mps")     # Apple Silicon (M1/M2) - requires PyTorch 2.0+ and macOS 12.3+

# Generate image
prompt = "a cat sitting on a beach at sunset, photorealistic"

image = pipe(
    prompt=prompt,
    num_inference_steps=30,    # more steps = better quality, slower
    guidance_scale=7.5,        # CFG scale: how strongly to condition on the prompt
).images[0]

image.save("output.png")
print("Saved output.png")

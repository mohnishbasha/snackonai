.PHONY: install pull-models pull-flux pull-turbo pull-llama-vision pull-llava pull-moondream run clean

install:
	pip install -r requirements.txt

install-flux:
	pip install diffusers transformers accelerate torch

# ── Image generation models ───────────────────────────────────────────────────
pull-flux:
	ollama pull flux1:schnell

pull-turbo:
	ollama pull x/z-image-turbo

# ── Vision / multimodal models ────────────────────────────────────────────────
pull-llama-vision:
	ollama pull llama3.2-vision:11b

pull-llava:
	ollama pull llava:13b

pull-moondream:
	ollama pull moondream

pull-models: pull-flux pull-turbo pull-llama-vision pull-llava pull-moondream

run:
	python -m mr_pixel_smith.cli

clean:
	rm -f *.png

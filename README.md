# ComfyUI-llama-cpp  
Run LLM/VLM models natively in ComfyUI based on llama.cpp  
**[[📃中文版](./README_zh.md)]** 

## Preview  
![](./img/preview.jpg)

## Installation  

### Install on Windows or Ubuntu

Clone the fork as `BK-llama-cpp` under `ComfyUI/custom_nodes`. Use ComfyUI's own Python environment to install dependencies. Use `requirements_cu131.txt` for the CUDA 13.1 wheel set.

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/LBK888/ComfyUI-llama-cpp_vlm.git BK-llama-cpp
python -m pip install -r BK-llama-cpp/requirements.txt
```

For Windows Portable, use `python_embeded/python.exe` from the Portable installation. For Ubuntu, use the Python in ComfyUI's virtual environment. You can also expose an existing checkout at `ComfyUI/custom_nodes/BK-llama-cpp` using a Windows junction (`New-Item -ItemType Junction`) or an Ubuntu symbolic link (`ln -s`). Enable one copy of this node pack because the fork shares the upstream node IDs.

### Optional T8 catalog clone

From the `BK-llama-cpp` checkout, run these commands once for a lightweight clone of the catalog. An existing full clone in the same location works too.

```bash
git clone --filter=blob:none --sparse https://github.com/T8mars/minimax-h3-prompt-skill-T8.git minimax-h3-prompt-skill-T8
git -C minimax-h3-prompt-skill-T8 sparse-checkout set --no-cone /catalog/template-index.json
```

The H3 enhancer reads `BK-llama-cpp/minimax-h3-prompt-skill-T8/catalog/template-index.json` when available and falls back to the bundled catalog if the clone is missing or unreadable. Update the separate clone with `git -C minimax-h3-prompt-skill-T8 pull --ff-only`, then restart ComfyUI to load the updated index. T8 provides catalog data. `requirements.txt` installs Python packages, so the T8 clone is managed through Git.

#### Download models:  
- Place your model files in the `ComfyUI/models/LLM` folder.  

	> If you need a VLM model to process image input, don't forget to download the `mmproj` weights.

## BK Instruct features

`Llama-cpp Parameters` accepts up to `32768` generated tokens, including reasoning. New nodes default to `4096`. A value of `0` uses the available context. Set the Model Loader's `n_ctx` to accommodate the prompt, images, history, and output. Instruct filters Qwen thinking from text and image completions and logs the finish reason and available token counts when generation hits a length limit.

Set `H3_story_enhancer` on `Llama-cpp Instruct` and enter the story in `custom_prompt`. The default is `off`. Choose `auto` to infer the generation mode, or select `1ref2va`, `2ref2va`, `Nref2va`, `i2va`, `flf2va` (FL2VA), `l2va`, or `t2va`. Each enabled run routes the story to a compatible template, plans the shots, and writes a MiniMax H3 prompt using the original brief and plan. The final round receives attached images when present. See the [Chinese README](./README_zh.md#h3_story_enhancer) for the mode and template details.

## Credits  
- [llama-cpp-python](https://github.com/JamePeng/llama-cpp-python) @JamePeng  
- [ComfyUI-llama-cpp](https://github.com/kijai/ComfyUI-llama-cpp) @kijai  
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) @comfyanonymous
- H3 mode guides are adapted from the [official MiniMax H3 writing guide](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) and the user's `my ref2AV system prompt.txt`.
- The bundled catalog adapts bilingual card metadata and story mechanisms from the [T8 Creative DNA Prompt Library](https://github.com/T8mars/minimax-h3-prompt-skill-T8/tree/5882fc3) by T8mars and contributors, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The cards were reduced to searchable titles, tags, mechanisms and structural cues.

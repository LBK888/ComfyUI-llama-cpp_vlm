# ComfyUI-llama-cpp
在 ComfyUI 中基于 llama.cpp 框架原生运行 LLM & VLM 模型。  
**[[📃English](./README.md)]**   

## 预览
![](./img/preview.jpg) 

## 安装步骤

### Windows 與 Ubuntu 安裝

在 `ComfyUI/custom_nodes` 下將 fork clone 成 `BK-llama-cpp`，並用 ComfyUI 的 Python 安裝相依套件。若使用 CUDA 13.1 版本的 wheel，請選 `requirements_cu131.txt`。

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/LBK888/ComfyUI-llama-cpp_vlm.git BK-llama-cpp
python -m pip install -r BK-llama-cpp/requirements.txt
```

Windows Portable 請使用 Portable 目錄裡的 `python_embeded/python.exe`。Ubuntu 請使用 ComfyUI 虛擬環境的 Python。若工作副本已在其他位置，可在 `ComfyUI/custom_nodes/BK-llama-cpp` 建立 junction（Windows 的 `New-Item -ItemType Junction`）或符號連結（Ubuntu 的 `ln -s`），指向工作副本。同一套 ComfyUI 請只啟用一份這個套件，因為 fork 沿用原版的節點 ID。

### 獨立安裝及更新 T8 模板庫

在 `BK-llama-cpp` 根目錄執行下列指令，只 checkout H3 會讀取的索引。若相同位置已經有完整 T8 clone，可直接使用。

```bash
git clone --filter=blob:none --sparse https://github.com/T8mars/minimax-h3-prompt-skill-T8.git minimax-h3-prompt-skill-T8
git -C minimax-h3-prompt-skill-T8 sparse-checkout set --no-cone /catalog/template-index.json
```

H3 優先讀取 `BK-llama-cpp/minimax-h3-prompt-skill-T8/catalog/template-index.json`。未安裝或無法讀取時，會改用內建模板。要更新時，在 `BK-llama-cpp` 下執行 `git -C minimax-h3-prompt-skill-T8 pull --ff-only`，再重啟 ComfyUI 重新載入索引。T8 提供模板資料，`requirements.txt` 由 pip 用來安裝 Python 套件，因此 T8 clone 由 Git 獨立管理。

### 模型路径:
- 请将下载的 `.gguf` 模型放置在 `ComfyUI/models/LLM` 目录中.  

	> 在使用VLM模型进行图像推理之前, 请确保已经下载并选择了主模型对应的`mmproj`权重文件.

## BK 分支的 Instruct 功能

`Llama-cpp Parameters` 的 `max_tokens` 上限是 `32768`，新節點預設 `4096`。它包含思考和正式回答，`0` 會使用後端剩餘的上下文。Model Loader 的 `n_ctx` 必須容納系統提示詞、圖片、對話歷史和輸出。使用 Qwen3.8 時，可從 `max_tokens=16384`、`n_ctx=32768` 起試，再依模型支援的上下文和可用 VRAM 調整。

Instruct 的文字和影像輸出都會移除思考區段，包含 Qwen 模板預先填入 `<think>` 所產生的單獨 `</think>`。如果生成碰到長度限制，ComfyUI 終端會顯示 `finish_reason`、`max_tokens`、`n_ctx` 和後端有回報的 token 用量。如果截斷發生在思考階段，可能沒有可用的正式答案。

### H3_story_enhancer

在 `Llama-cpp Instruct` 的 `custom_prompt` 填寫故事、指定台詞、片長和風格，從 `H3_story_enhancer` 選擇模式。欄位接在既有 widgets 後面，預設 `off`，舊工作流可以照常開啟。啟用 H3 時，`system_prompt` 會停用，系統提示由所選模式提供。切回 `off` 時，原先儲存的 `system_prompt` 會恢復使用。

| 模式 | 用途 |
| --- | --- |
| `off` | 一般 Instruct 推理 |
| `auto` | 依原始需求和圖片／影片的角色判斷模式 |
| `1ref2va`、`2ref2va`、`Nref2va` | 一份、兩份、三份以上的素材參考，通常用來維持身分、場景、聲音或風格 |
| `i2va` | 圖片 1 是首幀 |
| `flf2va` | 圖片 1 和 2 分別是首幀、尾幀，對應 MiniMax FL2VA |
| `l2va` | 圖片 1 是尾幀 |
| `t2va` | 由文字建立畫面與聲音 |

啟用後每筆輸入會用同一個本地模型推理三輪。第一輪從至多八個相關 T8 模板中選一個，也可沿用故事本身的結構。第二輪根據任務短指南補強事件因果、分鏡、拍攝和聲音。第三輪以原始需求和分鏡計畫寫成對應的 H3 格式，並在寫作時核對連戲、時間和指定台詞。節點會先在本地修正可以明確判定的欄位格式和任務標記，其餘格式問題至多補寫一輪。未指定長度時使用 15 秒。兩個 `STRING` 輸出只提供成稿。`images` 推理模式可將所有參考圖按輸入順序交給同一個故事，接圖時需要 VLM 和對應的 `mmproj`。如果素材只會在下游提供，可在原始需求寫明每份素材的名稱與用途。

使用支援 `reasoning_budget` 的 Qwen3.5／3.6／3.8 Thinking 後端時，H3 將分類、分鏡、成稿和補寫的思考上限設為 96、384、768、192 tokens。各輪仍使用工作流的 `max_tokens` 作為總輸出上限。Ref2VA 摘要只有任務標記時，可以從已寫好的分鏡取一句完整描述補上。ComfyUI 日誌會列出每輪耗時、prompt 和 completion 用量、思考上限與結束原因。

H3 支援離線使用。短指南參考 [MiniMax H3 官方寫作指南](https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing) 和 `my ref2AV system prompt.txt`。內建模板取自 [T8 Creative DNA Prompt Library](https://github.com/T8mars/minimax-h3-prompt-skill-T8/tree/5882fc3)，依 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 重整為 277 張可搜尋的摘要卡，保留標題、關鍵字、故事機制與結構重點。

## 致谢
- [llama-cpp-python](https://github.com/JamePeng/llama-cpp-python) @JamePeng  
- [ComfyUI-llama-cpp](https://github.com/kijai/ComfyUI-llama-cpp) @kijai
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) @comfyanonymous

# LLM Fine-Tuning Training Context

## Quick Start Command
```bash
cd /home/jovyan/silicogen/rtl_analyzer
python -m jupyter nbconvert --to notebook --execute notebooks/rtl_analyzer_phase3/08_llm_finetuning_unsloth_READY_TO_RUN.ipynb --output 08_executed.ipynb
```

## Dataset Status
| Dataset | Location | Samples | Ready |
|---------|----------|---------|-------|
| Combined | `datasets/llm/combined_unsloth.jsonl` | 110,911 | ✅ |
| VeriGen | `datasets/llm/verigen_unsloth.jsonl` | 108,971 | ✅ |
| Error Correction | `datasets/llm/error_correction_unsloth.jsonl` | 1,940 | ✅ |
| GitHub Release | https://github.com/Silicogen-Labs/machine-learning-theories/releases/tag/v1 | - | ✅ Uploaded |

## Recommended Training Config (Tesla T4 14.6GB)
```python
per_device_train_batch_size = 1
gradient_accumulation_steps = 8
max_steps = 500  # Test run (~45 min)
# OR
num_train_epochs = 2  # Full training (~24 hours, 27,728 steps)
```

## Model Recommendation
- **Qwen3.5-2B** (best balance for T4)
- QLoRA 4-bit quantization
- LoRA rank r=8

## Expected Results
- Test run (500 steps): Verify pipeline works
- Full training (27K steps): Verilog code generation model
- Output: `verilog_finetuned_model/` directory

## GPU Info
- Tesla T4: 14.6 GB VRAM
- CUDA 13.0
- PyTorch 2.11.0+cu130

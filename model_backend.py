"""Shared Gemma text-only loading for inference and optional QLoRA training."""
import json
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_ID = 'google/gemma-3-4b-it'
MODEL_NAME = 'gemma-3-4b-it'
DEFAULT_MODEL_PATH = ROOT / 'models' / MODEL_NAME
DEFAULT_ADAPTER_PATH = ROOT / 'training/runs/gemma3-cpe49-v1'
ADAPTER_MODEL_NAME = 'gemma-3-4b-cpe49-v1'


def active_deployment():
    """Only select a completed, reviewed local adapter; clones default to base."""
    marker = DEFAULT_ADAPTER_PATH / 'deployment_ready.json'
    if not marker.is_file():
        return {'name': MODEL_NAME, 'adapter_path': ''}
    ready = json.loads(marker.read_text(encoding='utf-8'))
    report = json.loads((DEFAULT_ADAPTER_PATH / 'training_report.json').read_text(encoding='utf-8'))
    weights = DEFAULT_ADAPTER_PATH / 'adapter_model.safetensors'
    if (ready.get('base_model') != MODEL_ID or report.get('topics') != 49
            or report.get('smoke_only') is not False
            or report.get('optimizer_steps', 0) <= 0
            or report.get('optimizer_steps') != report.get('expected_steps')
            or not weights.is_file()
            or ready.get('adapter_sha256') != hashlib.sha256(weights.read_bytes()).hexdigest()):
        raise RuntimeError('CPE49 Adapter 的完成標記或權重驗證不符，請先檢查訓練輸出。')
    return {'name': ADAPTER_MODEL_NAME, 'adapter_path': str(DEFAULT_ADAPTER_PATH)}


def model_path():
    return Path(os.environ.get('HF_MODEL_PATH') or DEFAULT_MODEL_PATH).expanduser().resolve()


def validate_adapter(path, base_path):
    config_path = Path(path) / 'adapter_config.json'
    if not config_path.is_file():
        raise RuntimeError(f'找不到 Gemma LoRA adapter：{config_path}')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    base = config.get('base_model_name_or_path', '')
    if base != MODEL_ID and Path(base).resolve() != Path(base_path).resolve():
        raise RuntimeError('Adapter 的基礎模型與目前 Gemma 不符；舊 Qwen Adapter 無法沿用，請重新訓練。')


def load_text_model(path, **kwargs):
    from transformers import AutoConfig, Gemma3ForCausalLM
    config = AutoConfig.from_pretrained(str(path), local_files_only=True)
    if config.model_type not in ('gemma3', 'gemma3_text'):
        raise RuntimeError('目前後端只載入 Gemma 3，請將 HF_MODEL_PATH 指向 gemma-3-4b-it。')
    if config.model_type == 'gemma3':
        # Explicitly map both legacy and current multimodal checkpoint names.
        # Transformers 5 otherwise initializes a text-only model with missing weights.
        kwargs['key_mapping'] = {
            r'^language_model\.model\.': 'model.',
            r'^model\.language_model\.': 'model.',
            r'^language_model\.lm_head\.': 'lm_head.',
        }
    # Gemma3ForCausalLM extracts the text config and skips the vision tower.
    model, info = Gemma3ForCausalLM.from_pretrained(str(path), local_files_only=True, output_loading_info=True, **kwargs)
    missing = [name for name in info.get('missing_keys', []) if not name.startswith(('vision_tower.', 'multi_modal_projector.'))]
    if missing or info.get('mismatched_keys'):
        raise RuntimeError('Gemma 文字權重未完整載入，請檢查下載檔案與 Transformers 版本。')
    return model

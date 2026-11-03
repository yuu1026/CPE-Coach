"""Local GPU smoke check: actual tokenizer, NF4 load, and a short Chinese reply.

Run before removing the previous model. This is not a CPE accuracy benchmark.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import torch
    from local_model_server import load_model, fit_history, MODEL_NAME, ADAPTER_PATH
    from model_backend import MODEL_ID, model_path
    tokenizer, model = load_model()
    messages = [
        {'role': 'system', 'content': '你是 CPE 教學助理，請使用繁體中文，一次只引導一個小步驟，不提供完整程式。'},
        {'role': 'user', 'content': '我不知道怎麼開始寫程式，請先問我一個問題。'},
        {'role': 'assistant', 'content': '你可以先描述題目會給你哪些輸入資料嗎？'},
        {'role': 'user', 'content': '會給兩個整數。請接著引導我，不要給答案。'},
    ]
    selected, omitted = fit_history(tokenizer, messages, 128, 4096)
    inputs = tokenizer.apply_chat_template(selected, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt').to('cuda:0')
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=128, do_sample=False,
                                pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
    tokens = output[0][inputs['input_ids'].shape[-1]:]
    reply = tokenizer.decode(tokens, skip_special_tokens=True)
    if not reply.strip():
        raise RuntimeError('Gemma did not produce a response.')
    report = {'model': MODEL_ID, 'served_model': MODEL_NAME, 'adapter_enabled': bool(ADAPTER_PATH), 'gpu': torch.cuda.get_device_name(0),
              'quantization': 'NF4 text-only', 'input_tokens': inputs['input_ids'].shape[-1],
              'output_tokens': len(tokens), 'omitted_turns': omitted, 'reply': reply,
              'peak_allocated_gib': round(torch.cuda.max_memory_allocated()/1024**3, 3),
              'scope': 'Loading/template/generation smoke check only; not fine-tuning or CPE accuracy evaluation.'}
    target = ROOT / 'models/gemma-smoke-result.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

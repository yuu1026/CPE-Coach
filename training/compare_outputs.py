"""Deterministic base/adapter samples; human review, not an automatic accuracy score."""
import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path
import torch
from peft import PeftModel
from transformers import AutoTokenizer, BitsAndBytesConfig

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from model_backend import model_path, load_text_model, validate_adapter

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adapter', type=Path, default=HERE / 'runs/gemma3-cpe10-v1')
    parser.add_argument('--model', default=str(model_path()))
    args = parser.parse_args()
    validate_adapter(args.adapter, args.model)
    train = [json.loads(x) for x in (HERE / 'data/train.jsonl').read_text(encoding='utf-8').splitlines()]
    evaluation = [json.loads(x) for x in (HERE / 'data/eval.jsonl').read_text(encoding='utf-8').splitlines()]
    selected = [r for r in evaluation if r['hint_level'] == 1 and r['problem_id'] in (10055, 272, 10812)] + [r for r in train if r['variant'] == 'correct' and r['hint_level'] == 1 and r['problem_id'] in (10055, 272, 10812)]
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    base = load_text_model(args.model, device_map={'': 0}, quantization_config=quant, dtype=torch.bfloat16, attn_implementation='sdpa')
    model = PeftModel.from_pretrained(base, str(args.adapter), is_trainable=False, local_files_only=True)
    model.eval()
    results = []
    for row in selected:
        inputs = tokenizer.apply_chat_template(row['messages'][:-1], tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors='pt').to('cuda')
        result = {'id': row['id'], 'expected_teaching_response': row['messages'][-1]['content']}
        for label in ('base', 'adapter'):
            context = model.disable_adapter() if label == 'base' else nullcontext()
            with context, torch.inference_mode():
                tokens = model.generate(**inputs, max_new_tokens=192, do_sample=False, repetition_penalty=1.1, pad_token_id=tokenizer.eos_token_id)
            generated = tokens[0][inputs['input_ids'].shape[-1]:]
            result[label] = tokenizer.decode(generated, skip_special_tokens=True)
            result[label + '_tokens'] = len(generated)
        results.append(result)
        print(f"Compared {row['id']}", flush=True)
    (args.adapter / 'generation_comparison.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved six qualitative comparisons, including three seen correct examples and three held-out bug types.')

if __name__ == '__main__':
    main()

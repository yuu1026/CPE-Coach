"""Single-GPU assistant-only QLoRA pilot. No full model weights are overwritten."""
import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

HERE = Path(__file__).resolve().parent

def read_records(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]

def encode_record(tokenizer, record, max_length):
    prefix = tokenizer.apply_chat_template(record['messages'][:-1], tokenize=True, add_generation_prompt=True, return_dict=True)['input_ids']
    full = tokenizer.apply_chat_template(record['messages'], tokenize=True, add_generation_prompt=False, return_dict=True)['input_ids']
    if full[:len(prefix)] != prefix:
        raise ValueError(f"Chat template prefix mismatch: {record['id']}")
    if len(full) > max_length:
        raise ValueError(f"{record['id']} has {len(full)} tokens > {max_length}; no silent truncation")
    labels = [-100] * len(prefix) + full[len(prefix):]
    if not any(x != -100 for x in labels):
        raise ValueError('No assistant tokens')
    return {'id': record['id'], 'input_ids': full, 'labels': labels}

def batch(record):
    ids = torch.tensor([record['input_ids']], device='cuda')
    return {'input_ids': ids, 'attention_mask': torch.ones_like(ids), 'labels': torch.tensor([record['labels']], device='cuda')}

def evaluate(model, encoded):
    model.eval()
    total = 0.0
    with torch.inference_mode():
        for record in encoded:
            with torch.autocast('cuda', dtype=torch.bfloat16):
                result = model(**batch(record), use_cache=False)
            total += float(result.loss)
            del result
    return total / len(encoded)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default=r'C:\Users\tt\models\Qwen3-4B-Instruct-2507')
    parser.add_argument('--output', type=Path, default=HERE / 'runs' / 'cpe10-v1')
    parser.add_argument('--epochs', type=int, default=1)
    parser.add_argument('--max-length', type=int, default=1536)
    parser.add_argument('--accumulation', type=int, default=4)
    parser.add_argument('--learning-rate', type=float, default=1e-4)
    parser.add_argument('--smoke', action='store_true', help='One optimizer step; use a separate output folder')
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError('Output folder already exists. Choose a new --output; existing training results are preserved.')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA unavailable')
    random.seed(42); torch.manual_seed(42)
    print('GPU:', torch.cuda.get_device_name(0), flush=True)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    training = [encode_record(tokenizer, r, args.max_length) for r in read_records(HERE / 'data/train.jsonl')]
    validation = [encode_record(tokenizer, r, args.max_length) for r in read_records(HERE / 'data/eval.jsonl') if r['hint_level'] == 1]
    print(f'Train={len(training)}, held-out bug eval={len(validation)}, max tokens={max(len(r["input_ids"]) for r in training)}', flush=True)
    quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True, quantization_config=quant, device_map={'': 0}, dtype=torch.bfloat16, attn_implementation='sdpa')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant': False})
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=['q_proj', 'v_proj'], bias='none', task_type='CAUSAL_LM'))
    model.print_trainable_parameters()
    before = evaluate(model, validation) if not args.smoke else None
    print(f'Validation assistant loss before={before}', flush=True)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.learning_rate, weight_decay=0.01)
    optimizer.zero_grad(set_to_none=True)
    steps_per_epoch = math.ceil(len(training) / args.accumulation)
    logs = []
    started = time.monotonic()
    steps = 0
    for epoch in range(args.epochs):
        model.train()
        indices = list(range(len(training)))
        random.shuffle(indices)
        for group_start in range(0, len(indices), args.accumulation):
            group = indices[group_start:group_start + args.accumulation]
            loss_sum = 0.0
            for index in group:
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    result = model(**batch(training[index]), use_cache=False)
                    loss = result.loss / len(group)
                if not torch.isfinite(loss):
                    raise RuntimeError('Nonfinite loss; no adapter saved')
                loss.backward()
                loss_sum += float(result.loss.detach())
                del result, loss
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            optimizer.step(); optimizer.zero_grad(set_to_none=True)
            steps += 1
            log = {'epoch': epoch + 1, 'step': steps, 'loss': round(loss_sum / len(group), 5), 'elapsed_seconds': round(time.monotonic() - started, 1), 'peak_vram_gb': round(torch.cuda.max_memory_allocated() / 1024**3, 3)}
            logs.append(log)
            print(json.dumps(log), flush=True)
            if args.smoke:
                break
        if args.smoke:
            break
    after = evaluate(model, validation) if not args.smoke else None
    args.output.mkdir(parents=True)
    model.save_pretrained(args.output, safe_serialization=True)
    tokenizer.save_pretrained(args.output)
    report = {'base_model': args.model, 'dataset_sha256': hashlib.sha256((HERE / 'data/train.jsonl').read_bytes()).hexdigest(), 'gpu': torch.cuda.get_device_name(0), 'training_examples': len(training), 'evaluation_examples': len(validation), 'epochs': args.epochs, 'optimizer_steps': steps, 'expected_steps': steps_per_epoch * args.epochs, 'smoke_only': args.smoke, 'method': 'NF4 QLoRA; rank8 q_proj/v_proj; assistant-only loss', 'max_length': args.max_length, 'gradient_accumulation': args.accumulation, 'learning_rate': args.learning_rate, 'validation_loss_before': before, 'validation_loss_after': after, 'peak_allocated_vram_gb': torch.cuda.max_memory_allocated() / 1024**3, 'elapsed_seconds': time.monotonic() - started, 'scope': 'Ten seen problems, held-out bug types; loss does not measure pedagogical quality or unseen-problem generalization', 'logs': logs}
    (args.output / 'training_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved adapter: {args.output}; eval loss {before} -> {after}', flush=True)

if __name__ == '__main__':
    main()

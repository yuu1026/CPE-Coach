"""Local Hugging Face 4-bit inference, compatible with this project's /api/chat client.
Run one process; do not expose this development service to the network.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from model_backend import MODEL_NAME as DEFAULT_MODEL_NAME, active_deployment, model_path, load_text_model, validate_adapter

FORCE_BASE = os.environ.get('HF_USE_BASE_MODEL') == '1'
DEPLOYMENT = active_deployment() if not FORCE_BASE and 'HF_ADAPTER_PATH' not in os.environ else {'name': DEFAULT_MODEL_NAME, 'adapter_path': ''}
ADAPTER_PATH = '' if FORCE_BASE else os.environ.get('HF_ADAPTER_PATH', DEPLOYMENT['adapter_path'])
MODEL_NAME = os.environ.get('HF_SERVE_MODEL_NAME') or (DEPLOYMENT['name'] if ADAPTER_PATH else DEFAULT_MODEL_NAME)
MAX_CONTEXT = 4096
LOCK = threading.Lock()

def finish_reason(tokens, maximum, eos_ids):
    ends = eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids]
    return 'stop' if len(tokens) < maximum or (len(tokens) and int(tokens[-1]) in ends) else 'length'

def fit_history(tokenizer, messages, maximum, context):
    selected = list(messages)
    omitted = 0
    while True:
        tokens = tokenizer.apply_chat_template(selected, add_generation_prompt=True, tokenize=True, return_dict=True)['input_ids']
        if len(tokens) + maximum <= context:
            return selected, omitted
        if len(selected) >= 4 and selected[1]['role'] == 'user' and selected[2]['role'] == 'assistant':
            selected = selected[:1] + selected[3:]
            omitted += 1
        else:
            raise ValueError('context_limit')


def load_model():
    import torch
    from transformers import AutoTokenizer, BitsAndBytesConfig
    path = model_path()
    if not (path / 'config.json').is_file():
        raise RuntimeError(f'找不到模型 config.json：{path}')
    if not torch.cuda.is_available():
        raise RuntimeError('PyTorch 無法使用 CUDA，請先安裝支援 RTX 5060 的 PyTorch。')
    adapter = ADAPTER_PATH
    if adapter:
        validate_adapter(adapter, path)
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True)
    quantization = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)
    model = load_text_model(path, device_map={'': 0}, quantization_config=quantization, dtype=torch.bfloat16, attn_implementation='sdpa')
    if adapter:
        from peft import PeftModel
        adapter_path = Path(adapter).resolve()
        if not (adapter_path / 'adapter_config.json').is_file():
            raise RuntimeError(f'找不到 LoRA adapter：{adapter_path}')
        model = PeftModel.from_pretrained(model, str(adapter_path), is_trainable=False, local_files_only=True)
        print(f'已載入 CPE adapter：{adapter_path}', flush=True)
    model.eval()
    return tokenizer, model


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def local_request(self):
        return self.headers.get('Host') in {'127.0.0.1:11436', 'localhost:11436'} and not self.headers.get('Origin')

    def do_GET(self):
        if not self.local_request():
            return self.reply(403, {'error': 'local backend requests only'})
        if self.path != '/healthz':
            return self.reply(404, {'error': 'not found'})
        self.reply(200, {'status': 'ready', 'model': MODEL_NAME, 'context': MAX_CONTEXT, 'quantization': 'nf4'})

    def do_POST(self):
        if not self.local_request():
            return self.reply(403, {'error': 'local backend requests only'})
        if self.path != '/api/chat':
            return self.reply(404, {'error': 'not found'})
        if not LOCK.acquire(blocking=False):
            return self.reply(429, {'error': '模型忙碌，請稍後再試'})
        try:
            self.connection.settimeout(15)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 100000:
                return self.reply(413, {'error': 'invalid request size'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or data.get('model') != MODEL_NAME or data.get('stream') is not False:
                return self.reply(400, {'error': 'model 或 stream 設定不符'})
            messages = data.get('messages')
            if not isinstance(messages, list) or not 1 <= len(messages) <= 20:
                return self.reply(400, {'error': 'invalid messages'})
            if any(not isinstance(m, dict) or m.get('role') not in {'system', 'user', 'assistant'} or not isinstance(m.get('content'), str) for m in messages):
                return self.reply(400, {'error': 'invalid message'})
            import torch
            options = data.get('options', {})
            if not isinstance(options, dict):
                return self.reply(400, {'error': 'invalid options'})
            maximum = min(1024, max(1, int(options.get('num_predict', 1024))))
            try:
                messages, omitted = fit_history(self.server.tokenizer, messages, maximum, MAX_CONTEXT)
            except ValueError:
                return self.reply(400, {'code': 'context_limit', 'error': '本輪程式與問題超過可用長度，程式未裁切', 'output_reserve': maximum, 'context_limit': MAX_CONTEXT})
            inputs = self.server.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors='pt').to('cuda:0')
            length = inputs['input_ids'].shape[-1]
            with torch.inference_mode():
                output = self.server.model.generate(**inputs, max_new_tokens=maximum, do_sample=False, repetition_penalty=1.1, pad_token_id=self.server.tokenizer.pad_token_id if self.server.tokenizer.pad_token_id is not None else self.server.tokenizer.eos_token_id)
            tokens = output[0][length:]
            eos = self.server.model.generation_config.eos_token_id
            answer = self.server.tokenizer.decode(tokens, skip_special_tokens=True)
            reason = finish_reason(tokens.tolist(), maximum, eos)
            print(f'推論完成：input={length}, output={len(tokens)}, reason={reason}', flush=True)
            self.reply(200, {'model': MODEL_NAME, 'message': {'role': 'assistant', 'content': answer}, 'done': True, 'done_reason': reason, 'prompt_eval_count': length, 'eval_count': len(tokens), 'history_turns_omitted': omitted})
        except (ValueError, TypeError):
            self.reply(400, {'error': 'invalid JSON or options'})
        except Exception as exc:
            print(f'推論失敗：{type(exc).__name__}: {exc}', flush=True)
            self.reply(500, {'error': '推論失敗，請查看模型服務終端機'})
        finally:
            LOCK.release()


if __name__ == '__main__':
    print('正在從本地硬碟以 4-bit 載入模型，請等待…', flush=True)
    tokenizer, model = load_model()
    server = ThreadingHTTPServer(('127.0.0.1', 11436), Handler)
    server.tokenizer, server.model = tokenizer, model
    print('模型已就緒：http://127.0.0.1:11436/healthz', flush=True)
    server.serve_forever()

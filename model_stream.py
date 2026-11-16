"""Incremental local generation; preserve single-model ownership on disconnect."""
import queue
import threading
import time


def events(model, tokenizer, inputs, maximum, model_name):
    import torch
    from transformers import TextIteratorStreamer, StoppingCriteria, StoppingCriteriaList
    started = time.perf_counter()
    cancel = threading.Event()
    result = {}
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=1)

    class Cancelled(StoppingCriteria):
        def __call__(self, input_ids, scores, **kwargs): return cancel.is_set()

    def generate():
        try:
            with torch.inference_mode():
                result['output'] = model.generate(**inputs, max_new_tokens=maximum, do_sample=False,
                    repetition_penalty=1.1, streamer=streamer,
                    stopping_criteria=StoppingCriteriaList([Cancelled()]),
                    pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id)
        except Exception as exc:
            result['error'] = exc
            streamer.end()

    worker = threading.Thread(target=generate, daemon=True, name='local-model-generation')
    worker.start()
    first_text = None
    try:
        yield {'done': False, 'phase': 'generation'}
        while True:
            try: text = next(streamer)
            except queue.Empty:
                if not worker.is_alive(): break
                yield {'done': False, 'phase': 'generation'}
                continue
            except StopIteration: break
            if text:
                if first_text is None: first_text = round(time.perf_counter()-started, 3)
                yield {'done': False, 'message': {'role': 'assistant', 'content': text}}
        worker.join()
        if 'error' in result: raise result['error']
        length = inputs['input_ids'].shape[-1]
        tokens = result['output'][0][length:].tolist()
        eos = model.generation_config.eos_token_id
        ends = eos if isinstance(eos, (list, tuple)) else [eos]
        reason = 'stop' if len(tokens)<maximum or (tokens and tokens[-1] in ends) else 'length'
        yield {'done': True, 'model': model_name, 'done_reason': reason,
               'prompt_eval_count': length, 'eval_count': len(tokens),
               'metrics': {'generation_seconds': round(time.perf_counter()-started, 3), 'first_text_seconds': first_text}}
    finally:
        cancel.set()
        # The caller holds the GPU lock until this worker actually exits.
        worker.join()

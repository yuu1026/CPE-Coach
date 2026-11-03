"""CPU check that selected-position assistant loss preserves loss AND gradients."""
import torch
from transformers import Gemma3TextConfig, Gemma3ForCausalLM
from train_qlora import batch


def main():
    torch.manual_seed(42)
    config = Gemma3TextConfig(vocab_size=32, hidden_size=16, intermediate_size=32,
                             num_hidden_layers=2, num_attention_heads=2,
                             num_key_value_heads=1, head_dim=8,
                             max_position_embeddings=64, sliding_window=16)
    model = Gemma3ForCausalLM(config).eval()
    record = {'input_ids': [2, 4, 5, 6, 7, 8], 'labels': [-100, -100, -100, 6, 7, 8], 'assistant_start': 3}
    inputs = batch(record, device='cpu')
    dense = model(input_ids=inputs['input_ids'], attention_mask=inputs['attention_mask'], labels=inputs['labels'])
    dense.loss.backward()
    gradients = {name: p.grad.clone() for name, p in model.named_parameters() if p.grad is not None}
    model.zero_grad()
    selected = model(**inputs)
    selected.loss.backward()
    torch.testing.assert_close(dense.loss, selected.loss, atol=1e-6, rtol=1e-6)
    for name, parameter in model.named_parameters():
        if name in gradients:
            torch.testing.assert_close(gradients[name], parameter.grad, atol=1e-6, rtol=1e-5)
    print('PASS: assistant-only loss and all parameter gradients match dense causal loss.')


if __name__ == '__main__':
    main()

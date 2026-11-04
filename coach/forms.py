from django import forms

class SubmissionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and self.data.get('action') == 'test':
            # Testing must ignore an unsent chat draft and its validation rules.
            self.fields['question'].disabled = True
            self.fields['hint_level'].disabled = True
            self.initial['question'] = ''
            self.initial['hint_level'] = 1

    action = forms.ChoiceField(required=False, choices=[('ask', '詢問助理'), ('test', '執行測試')], widget=forms.HiddenInput)
    parent_submission = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    run_custom = forms.BooleanField(label='額外執行自訂測資', required=False)
    custom_input = forms.CharField(label='自訂測資輸入（stdin）', max_length=10000, required=False, strip=False, widget=forms.Textarea(attrs={'rows': 3}))
    custom_expected = forms.CharField(label='自訂預期輸出（stdout）', max_length=10000, required=False, strip=False, widget=forms.Textarea(attrs={'rows': 3}))
    submission_id = forms.UUIDField(widget=forms.HiddenInput)
    code = forms.CharField(label='你的 C++ 程式碼（可留白）', max_length=12000, required=False, strip=False, help_text='還沒有想法也可以直接提交。留白時不編譯，由模型逐步引導你開始。', widget=forms.Textarea(attrs={'rows': 18, 'spellcheck': 'false', 'placeholder': '貼上程式碼，或留白從理解題目開始…'}))
    question = forms.CharField(label='你的想法、回答或遇到的問題', max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 2, 'placeholder': '例如：我完全沒有想法，或回答上一輪模型提出的問題。'}))
    hint_level = forms.TypedChoiceField(label='提示程度', coerce=int, choices=[(1, '1 · 給我方向'), (2, '2 · 幫我定位'), (3, '3 · 局部修正提示')])

    def clean_code(self):
        code = self.cleaned_data['code']
        return code if code.strip() else ''

    def clean_action(self):
        return self.cleaned_data.get('action') or 'ask'

    def clean(self):
        data = super().clean()
        if data.get('action') == 'test' and not data.get('code', '').strip():
            self.add_error('code', '執行測試需要程式碼；還沒開始寫時，請選「詢問助理」。')
        return data

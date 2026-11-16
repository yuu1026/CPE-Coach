"""Observable progress, never inferred mastery or fabricated learner answers."""
import hashlib
import re
from .diagnostics import code_tokens


def progress(code,question,history,evidence):
    tokens=code_tokens(code) or []
    features=[]
    for name,token in [('含輸入敘述','cin'),('含輸出敘述','cout'),('含排序呼叫','sort'),('含迴圈','for')]:
        if token in tokens:features.append(name)
    confirmations=[turn['question'][:180] for turn in history if re.search(r'我(?:已經|已|現在)?(?:了解|理解|懂|知道)',turn.get('question',''))][-3:]
    blocked=sum(turn.get('delivered') is False for turn in history[-3:])
    return {'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'observed_features':features,
            'student_reported_understanding':confirmations,'recent_blocked_turns':blocked,
            'current_goal':question[:240],'test_status':(evidence or {}).get('status','not_run'),
            'caution':'程式特徵與學生自述不等於已證明正確或真正理解；本輪原碼和實測結果優先。'}

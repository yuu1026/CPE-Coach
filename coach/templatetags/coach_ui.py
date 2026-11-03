from django import template
from django.conf import settings
from django.templatetags.static import static
from hashlib import sha256

register = template.Library()

@register.simple_tag
def versioned_static(path):
    """Change asset URLs when their contents change, including cached local browsers."""
    root = (settings.BASE_DIR / 'static').resolve()
    file = (root / path).resolve()
    if not file.is_relative_to(root) or not file.is_file():
        return static(path)
    version = sha256(file.read_bytes()).hexdigest()[:12]
    return f'{static(path)}?v={version}'

@register.filter
def status_label(value):
    return {'done': '已回覆', 'partial': '回覆未完整', 'failed': '提示失敗', 'running': '處理中', 'tested': '測試完成'}.get(value, '已保存')

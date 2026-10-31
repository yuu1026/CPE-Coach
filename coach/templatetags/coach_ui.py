from django import template

register = template.Library()

@register.filter
def status_label(value):
    return {'done': '已回覆', 'partial': '回覆未完整', 'failed': '提示失敗', 'running': '處理中', 'tested': '測試完成'}.get(value, '已保存')

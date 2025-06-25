from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from .models import Order


@shared_task
def send_order_confirmation_email(order_id):
    order = Order.objects.get(id=order_id)
    subject = f"Подтверждение заказа #{order.id}"
    text_content = f"Спасибо за ваш заказ #{order.id} на сумму {order.total_sum()} руб."
    html_content = render_to_string('email/order_confirmation.html', {'order': order})

    msg = EmailMultiAlternatives(
        subject,
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [order.user.email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


@shared_task
def process_import_task(file_path, user_id):
    from .utils import import_file
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.get(id=user_id)
    try:
        result = import_file(file_path, user)
        return {'status': 'success', 'result': result}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
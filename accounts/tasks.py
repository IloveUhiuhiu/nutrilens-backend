from celery import shared_task
from django.core.mail import send_mail

@shared_task
def send_otp_email_task(email, otp):
    """
    Task gửi email chạy ngầm.
    """
    subject = "Your NutriLens OTP"
    message = f"Your OTP code is: {otp}. It expires in 5 minutes."
    
    # Hàm này giờ sẽ chạy độc lập với luồng API chính
    send_mail(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=[email],
        fail_silently=False,
    )
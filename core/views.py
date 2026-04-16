from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import EmailMessage
from django.conf import settings


class DemoRequestThrottle(AnonRateThrottle):
    rate = '5/hour'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([DemoRequestThrottle])
def demo_request(request):
    data = request.data
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()

    if not name or not email:
        return Response({'error': 'Name and email are required.'}, status=status.HTTP_400_BAD_REQUEST)

    company = data.get('company', '—')
    phone = data.get('phone', '—')
    size = data.get('size', '—')

    subject = f'Demo Request — {company or name}'
    message = (
        f'Name: {name}\n'
        f'Email: {email}\n'
        f'Company/Building: {company}\n'
        f'Phone: {phone}\n'
        f'Business Size: {size}\n'
    )

    try:
        msg = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.DEMO_REQUEST_TO_EMAIL],
            reply_to=[email],
        )
        msg.send(fail_silently=False)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'Demo email failed: {e}')
        return Response({'error': 'Failed to send. Please email us directly.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'ok': True})

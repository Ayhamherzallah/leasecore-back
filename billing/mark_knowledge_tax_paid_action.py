    @action(detail=True, methods=['post'])
    def mark_knowledge_tax_paid(self, request, pk=None):
        """
        POST /api/billing/invoices/{id}/mark_knowledge_tax_paid/
        Mark the knowledge tax as paid to municipality.
        """
        invoice = self.get_object()
        from django.utils import timezone
        
        paid_date = request.data.get('paid_date', timezone.now().date())
        
        invoice.knowledge_tax_paid = True
        invoice.knowledge_tax_paid_date = paid_date
        invoice.save()
        
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

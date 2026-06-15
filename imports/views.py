from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from users.permissions import CanPerformFinancialCommand
from .specs import get_handler, resolve_building, HANDLERS

MAX_ROWS = 2000


class ImportViewSet(viewsets.ViewSet):
    """
    Smart spreadsheet import for invoices / expenses / payments.

      GET  /api/imports/spec/?resource=expenses   -> field spec for mapping UI
      POST /api/imports/validate/                 -> dry-run validation
      POST /api/imports/commit/                   -> create valid rows
    """
    permission_classes = [IsAuthenticated, CanPerformFinancialCommand]

    @action(detail=False, methods=['get'])
    def spec(self, request):
        resource = request.query_params.get('resource')
        handler = get_handler(resource)
        if not handler:
            return Response(
                {'detail': 'Unknown resource', 'available': list(HANDLERS.keys())},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(handler.meta())

    def _prepare(self, request):
        resource = request.data.get('resource')
        handler = get_handler(resource)
        if not handler:
            return None, None, None, Response(
                {'detail': 'Unknown resource'}, status=status.HTTP_400_BAD_REQUEST)

        rows = request.data.get('rows') or []
        if not isinstance(rows, list):
            return None, None, None, Response(
                {'detail': 'rows must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > MAX_ROWS:
            return None, None, None, Response(
                {'detail': f'Too many rows (max {MAX_ROWS}).'},
                status=status.HTTP_400_BAD_REQUEST)

        building, err = resolve_building(
            request.user, request.data.get('building'),
            required=handler.building_required,
        )
        if err:
            return None, None, None, Response(
                {'detail': err}, status=status.HTTP_400_BAD_REQUEST)
        return handler, rows, building, None

    @action(detail=False, methods=['post'])
    def validate(self, request):
        handler, rows, building, err = self._prepare(request)
        if err:
            return err

        building_id = building.id if building else None
        results, valid_count = [], 0
        for idx, row in enumerate(rows):
            clean, errors, display = handler.resolve(
                row or {}, user=request.user, building=building, building_id=building_id)
            ok = not errors
            valid_count += 1 if ok else 0
            results.append({
                'index': idx,
                'valid': ok,
                'errors': errors,
                'display': display,
            })

        return Response({
            'resource': handler.key,
            'total': len(rows),
            'valid': valid_count,
            'invalid': len(rows) - valid_count,
            'results': results,
        })

    @action(detail=False, methods=['post'])
    def commit(self, request):
        handler, rows, building, err = self._prepare(request)
        if err:
            return err

        building_id = building.id if building else None
        created, failed = [], []
        for idx, row in enumerate(rows):
            clean, errors, display = handler.resolve(
                row or {}, user=request.user, building=building, building_id=building_id)
            if errors:
                failed.append({'index': idx, 'errors': errors})
                continue
            try:
                label = handler.create(
                    clean, user=request.user, building=building, building_id=building_id)
                created.append({'index': idx, 'label': label})
            except Exception as e:  # noqa: BLE001 — surface per-row failure, keep going
                failed.append({'index': idx, 'errors': {'__all__': str(e)}})

        return Response({
            'resource': handler.key,
            'created_count': len(created),
            'failed_count': len(failed),
            'created': created,
            'failed': failed,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)

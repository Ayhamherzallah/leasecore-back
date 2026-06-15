import os
import tempfile

from io import BytesIO

from reportlab.lib.utils import ImageReader


def resolve_storage_file_path(file_field):
    """
    Return a local filesystem path for ReportLab, downloading from S3/R2 if needed.
    Caller may delete temp files after PDF generation when path starts with temp dir.
    """
    if not file_field or not file_field.name:
        return None

    try:
        local_path = file_field.path
        if local_path and os.path.exists(local_path):
            return local_path
    except NotImplementedError:
        pass
    except (ValueError, OSError):
        pass

    try:
        suffix = os.path.splitext(file_field.name)[1] or '.png'
        with file_field.open('rb') as src:
            content = src.read()
        if not content:
            return None
        fd, path = tempfile.mkstemp(suffix=suffix, prefix='pdf_asset_')
        os.close(fd)
        with open(path, 'wb') as dst:
            dst.write(content)
        return path
    except Exception:
        return None


def open_image_reader(file_field):
    """Return an ImageReader for ReportLab, works with local and remote storage."""
    if not file_field or not file_field.name:
        return None

    path = resolve_storage_file_path(file_field)
    if path and os.path.exists(path):
        try:
            return ImageReader(path)
        except Exception:
            pass

    try:
        with file_field.open('rb') as src:
            data = src.read()
        if data:
            return ImageReader(BytesIO(data))
    except Exception:
        pass

    return None

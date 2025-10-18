from django.core.management.base import BaseCommand, CommandError
from pathlib import Path

try:
    import segno  # lightweight QR code generator
except Exception:  # pragma: no cover
    segno = None


class Command(BaseCommand):
    help = 'Generate a QR code image for a URL. Default output: static/qr/dl_qr.svg'

    def add_arguments(self, parser):
        parser.add_argument('url', help='Website URL to encode in the QR code')
        parser.add_argument('--out', default='static/qr/dl_qr.svg', help='Output file path (supports .svg or .png)')
        parser.add_argument('--scale', type=int, default=5, help='Scale for raster outputs like PNG')

    def handle(self, *args, **options):
        if segno is None:
            raise CommandError('Missing dependency segno. Add segno to requirements.txt and install it.')

        url = options['url']
        out = Path(options['out'])
        out.parent.mkdir(parents=True, exist_ok=True)

        qr = segno.make(url)
        suffix = out.suffix.lower()

        if suffix == '.svg':
            qr.save(out, scale=3)
        elif suffix in {'.png', '.ppm'}:
            qr.save(out, scale=options['scale'])
        else:
            raise CommandError('Unsupported output format. Use .svg or .png')

        self.stdout.write(self.style.SUCCESS(f'QR code generated at {out} for {url}'))


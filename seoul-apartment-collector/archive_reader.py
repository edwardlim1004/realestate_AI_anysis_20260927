"""Read mixed private archives with size/hash verification and lazy Drive auth."""
import tempfile
from pathlib import Path
from google_drive_backup import s3_client, authorized_drive, download_verified_source

class VerifiedArchiveReader:
    def __init__(self, s3=None):
        self.s3 = s3 if s3 is not None else s3_client()
        self.drive = None

    def __call__(self, relative, entry):
        backend = entry.get('storage', 'r2')
        spec = (relative, entry['sha256'], entry['bytes'])
        if backend == 'gdrive':
            if not entry.get('drive_file_id'):
                raise ValueError('Missing Drive archive id')
            if self.drive is None:
                self.drive = authorized_drive(self.s3)
            spec += (entry['drive_file_id'],)
        elif backend != 'r2':
            raise ValueError('Unknown archive backend')
        with tempfile.TemporaryDirectory(prefix='verified-archive-') as tmp:
            target = Path(tmp) / 'scope.gz'
            download_verified_source(self.s3, spec, target, drive=self.drive)
            return target.read_bytes()

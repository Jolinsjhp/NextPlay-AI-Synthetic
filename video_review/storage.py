"""Private, bounded media storage. Untrusted names never become filesystem paths."""
import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.getenv('NEXTPLAY_STATE_DIR', str(Path(__file__).resolve().parents[1]/'.local'))) / 'video-review'
LOCK = threading.RLock()
MAX_BYTES = 64*1024*1024
ID = re.compile(r'^[a-f0-9]{32}$')
REVISION = re.compile(r'^[a-f0-9]{16}$')


def asset_path(asset_id, root=None):
    if not isinstance(asset_id, str) or not ID.fullmatch(asset_id):
        raise ValueError('Invalid video ID')
    return Path(root or ROOT)/asset_id


def read_asset(asset_id, root=None):
    path = asset_path(asset_id, root)
    return json.loads((path/'asset.json').read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as out:
        json.dump(value, out, ensure_ascii=False, allow_nan=False)
    os.replace(out.name, path)


def upload(stream, size, media_type, source_kind='uploaded_video', root=None):
    root = Path(root or ROOT)
    if type(size) is not int or not 32 <= size <= MAX_BYTES:
        raise ValueError('Upload must be 32 bytes to 64 MiB')
    if media_type not in ('video/mp4', 'video/webm') or source_kind not in ('uploaded_video', 'synthetic_demo'):
        raise ValueError('Only MP4 or WebM video is supported')
    with LOCK:
        existing = sum(p.stat().st_size for p in root.glob('*/media')) if root.exists() else 0
        if existing+size > int(os.getenv('NEXTPLAY_VIDEO_STORAGE_MB', '512'))*1024*1024:
            raise ValueError('Local video storage limit reached; remove old private uploads')
        asset_id = uuid.uuid4().hex
        folder = asset_path(asset_id, root); folder.mkdir(parents=True, mode=0o700)
        digest = hashlib.sha256(); remaining = size
        try:
            with (folder/'media').open('xb') as out:
                first = True
                while remaining:
                    block = stream.read(min(65536, remaining))
                    if not block:
                        raise ValueError('Incomplete video upload')
                    if first:
                        if (media_type == 'video/webm' and not block.startswith(b'\x1aE\xdf\xa3')
                            or media_type == 'video/mp4' and block[4:8] != b'ftyp'):
                            raise ValueError('Video container signature does not match its media type')
                        first = False
                    digest.update(block); out.write(block); remaining -= len(block)
            os.chmod(folder/'media', 0o600)
            asset = dict(schema_version='video-asset-1',video_id=asset_id,sha256=digest.hexdigest(),bytes=size,
                media_type=media_type,source_kind=source_kind,source_declaration='client_declared',
                created_at=datetime.now(timezone.utc).isoformat(),decoder_verified=False,
                media_url='/api/video-review/media/'+asset_id)
            write_json(folder/'asset.json', asset)
            return asset
        except Exception:
            (folder/'media').unlink(missing_ok=True)
            (folder/'asset.json').unlink(missing_ok=True)
            folder.rmdir()
            raise


def save_revision(asset_id, revision_id, record, root=None):
    if not REVISION.fullmatch(revision_id):raise ValueError('Invalid revision')
    read_asset(asset_id, root)
    path = asset_path(asset_id, root)/('revision-'+revision_id+'.json')
    with LOCK:
        if path.exists():
            old=json.loads(path.read_text())
            if old != record:raise ValueError('Immutable revision conflict')
        else:write_json(path,record)
    return record


def read_revision(asset_id, revision_id, root=None):
    if not isinstance(revision_id,str) or not REVISION.fullmatch(revision_id):raise ValueError('Invalid revision')
    return json.loads((asset_path(asset_id, root)/('revision-'+revision_id+'.json')).read_text())

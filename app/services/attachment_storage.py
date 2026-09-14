from supabase import create_client
from app.core.config import settings

# 创建Supabase client
def get_storage_client():
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase storage is not configured")

    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )

# 把pdf bytes上传到Supabase bucket
def upload_attachment_file(storage_key: str, content: bytes, content_type: str | None) -> None:
    client = get_storage_client()
    client.storage.from_(settings.supabase_storage_bucket).upload(
        path=storage_key,
        file=content,
        file_options={
            "content-type": content_type or "application/octet-stream",
            "upsert": "true",
        },
    )

# 根据storage_key从Supabase bucket下载PDF bytes
def download_attachment_file(storage_key: str) -> bytes:
    client = get_storage_client()
    return client.storage.from_(settings.supabase_storage_bucket).download(storage_key)

# 删除Supabase bucket里的文件
def delete_attachment_file(storage_key: str) -> None:
    client = get_storage_client()
    client.storage.from_(settings.supabase_storage_bucket).remove([storage_key])
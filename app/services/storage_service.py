import os
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)

def upload_file_to_supabase(bucket: str, file_path: str, file_content: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Uploads a file to Supabase Storage bucket using Supabase Storage REST API.
    Returns the public/authenticated URL of the uploaded file.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        logger.warning("Supabase URL or Key is missing. Skipping actual storage upload.")
        # Local mock return URL
        return f"/simulated-storage/{bucket}/{file_path}"

    # Standardize Supabase URL
    if not supabase_url.startswith("http"):
        supabase_url = f"https://{supabase_url}"
    supabase_url = supabase_url.rstrip("/")

    # URL format: POST /storage/v1/object/{bucket}/{path}
    url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
    
    req = urllib.request.Request(url, data=file_content, method="POST")
    req.add_header("Authorization", f"Bearer {supabase_key}")
    req.add_header("apikey", supabase_key)
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            res_body = response.read().decode("utf-8")
            res_data = json.loads(res_body)
            key_path = res_data.get("Key", f"{bucket}/{file_path}")
            # Construct authenticated retrieve URL
            return f"{supabase_url}/storage/v1/object/authenticated/{key_path}"
    except Exception as e:
        logger.error(f"Supabase Storage Upload failed: {str(e)}")
        # Check if file already exists, try upserting by overriding method
        try:
            req_upsert = urllib.request.Request(url, data=file_content, method="POST")
            req_upsert.add_header("Authorization", f"Bearer {supabase_key}")
            req_upsert.add_header("apikey", supabase_key)
            req_upsert.add_header("Content-Type", content_type)
            req_upsert.add_header("x-upsert", "true")
            with urllib.request.urlopen(req_upsert, timeout=15) as response:
                res_body = response.read().decode("utf-8")
                res_data = json.loads(res_body)
                return f"{supabase_url}/storage/v1/object/authenticated/{res_data.get('Key', f'{bucket}/{file_path}')}"
        except Exception as upsert_err:
            logger.error(f"Supabase Storage Upsert failed: {str(upsert_err)}")
            raise e


def delete_file_from_supabase(bucket: str, file_path: str) -> bool:
    """
    Deletes a file from Supabase Storage bucket.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        logger.warning("Supabase URL or Key is missing. Skipping storage delete.")
        return True

    if not supabase_url.startswith("http"):
        supabase_url = f"https://{supabase_url}"
    supabase_url = supabase_url.rstrip("/")

    url = f"{supabase_url}/storage/v1/object/{bucket}/{file_path}"
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {supabase_key}")
    req.add_header("apikey", supabase_key)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status in [200, 204]
    except Exception as e:
        logger.error(f"Supabase Storage delete failed: {str(e)}")
        return False

import os
import boto3
from botocore.exceptions import NoCredentialsError, ClientError, PartialCredentialsError
import config 

s3_client = None

def get_s3_client():
    """Initializes and returns an S3 client, caching it globally within this module."""
    global s3_client
    if s3_client:
        return s3_client
    try:
        print("  Initializing Boto3 S3 Client...")
        client = boto3.client('s3', region_name=config.AWS_REGION)
        client.head_bucket(Bucket=config.S3_BUCKET_NAME)
        print(f"  S3 Client connected successfully to bucket '{config.S3_BUCKET_NAME}' in region '{config.AWS_REGION}'.")
        s3_client = client
        return s3_client
    except (NoCredentialsError, PartialCredentialsError):
        print("  FATAL ERROR: AWS credentials not found. Configure via env vars, ~/.aws/credentials, or IAM role.")
        return None 
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == 'NoSuchBucket':
            print(f"  FATAL ERROR: S3 Bucket '{config.S3_BUCKET_NAME}' not found or access denied.")
        elif error_code == '403':
             print(f"  FATAL ERROR: Access Denied to S3 Bucket '{config.S3_BUCKET_NAME}'. Check permissions.")
        else:
            print(f"  FATAL ERROR accessing S3 Bucket '{config.S3_BUCKET_NAME}': {error_code} - {e}")
        return None 
    except Exception as e:
        print(f"  FATAL ERROR during S3 client initialization: {e}")
        return None 


def list_s3_objects_versions(client, bucket_name, prefix):
    """Lists latest versions of objects in S3, handling pagination and delete markers."""
    if not client:
         print("  ERROR: S3 client not initialized in list_s3_objects_versions.")
         return {}

    objects_info = {}
    paginator = client.get_paginator('list_object_versions')
    print(f"  Listing objects/versions in s3://{bucket_name}/{prefix}...")
    object_count = 0
    try:
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        for page in page_iterator:
            # Process Versions
            for version in page.get('Versions', []):
                key = version['Key']
                
                if key == prefix and prefix != "": continue
                if key.endswith('/') and version.get('Size', 0) == 0: continue
                if version['IsLatest']:
                    objects_info[key] = {'VersionId': version['VersionId'], 'LastModified': version['LastModified']}
                    object_count += 1

            # Process Delete Markers 
            for marker in page.get('DeleteMarkers', []):
                key = marker['Key']
                if marker['IsLatest'] and key in objects_info:
                    del objects_info[key] # Remove the object if the latest action was a delete
                    object_count -=1 # Decrement count

        print(f"  Found {len(objects_info)} current object keys.")
        return objects_info
    except ClientError as e:
        print(f"  ERROR listing S3 objects: {e}")
        return {} 
    except Exception as e:
        print(f"  Unexpected ERROR listing S3 objects: {e}")
        return {}

def list_s3_objects_for_display(client, bucket_name, prefix):
    """Lists objects using list_objects_v2 for frontend display (simpler)."""
    if not client:
         print("  ERROR: S3 client not initialized in list_s3_objects_for_display.")
         return []

    files_list = []
    paginator = client.get_paginator('list_objects_v2')
    print(f"  Listing objects for display in s3://{bucket_name}/{prefix}...")
    try:
        response_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        for page in response_iterator:
            if "Contents" in page:
                for item in page['Contents']:
                    key = item['Key']
                    # Skip potential "folder" objects if prefix is used and they appear
                    if key.endswith('/') and item.get('Size', 0) == 0:
                        continue
                    # Skip if the key IS the prefix itself (representing the folder)
                    if key == prefix and prefix != "":
                        continue

                    files_list.append({
                        'key': key,
                        'filename': os.path.basename(key) or key, # Handle root objects
                        'size': item.get('Size'),
                        'last_modified': item.get('LastModified').isoformat() if item.get('LastModified') else None,
                        'public_url': construct_public_s3_url(key) 
                    })
        print(f"  Found {len(files_list)} files for display.")
        
        files_list.sort(key=lambda x: x['filename'])
        return files_list

    except ClientError as e:
        print(f"  ERROR listing files for display: {e}")
        return [] 
    except Exception as e:
        print(f"  Unexpected error listing files for display: {e}")
        return []

def construct_public_s3_url(s3_key):
    """Constructs the public HTTP URL for an S3 object."""
    
    s3_key = s3_key.lstrip('/')
    return f"{config.S3_BASE_URL}/{s3_key}"

def download_s3_object(client, bucket_name, s3_key, local_path):
    """Downloads a specific S3 object to a local path."""
    if not client:
         print(f"  ERROR: S3 client not initialized. Cannot download {s3_key}.")
         return False
    try:
        print(f"    Downloading s3://{bucket_name}/{s3_key} to {local_path}...")
        client.download_file(bucket_name, s3_key, local_path)
        print(f"    Download successful.")
        return True
    except ClientError as e:
        print(f"    ERROR downloading S3 object {s3_key}: {e}")
        return False
    except Exception as e:
        print(f"    Unexpected ERROR downloading S3 object {s3_key}: {e}")
        return False

def upload_to_s3(client, file_obj, bucket_name, s3_key):
    """Uploads a file object to S3."""
    if not client:
        print(f"  ERROR: S3 client not initialized. Cannot upload to {s3_key}.")
        return False
    try:
        
        file_obj.seek(0)
        print(f"  Uploading to s3://{bucket_name}/{s3_key}...")
        client.upload_fileobj(file_obj, bucket_name, s3_key)
        print(f"  Upload successful.")
        return True
    except ClientError as e:
        print(f"  ERROR uploading to S3 ({s3_key}): {e}")
        return False
    except Exception as e:
        print(f"  Unexpected ERROR uploading to S3 ({s3_key}): {e}")
        return False

def get_s3_object_metadata(client, bucket_name, s3_key):
    """Retrieves metadata (VersionId, LastModified) for an S3 object."""
    if not client:
        print(f"  ERROR: S3 client not initialized. Cannot get metadata for {s3_key}.")
        return None, None
    try:
        print(f"  Retrieving metadata for s3://{bucket_name}/{s3_key}...")
        metadata = client.head_object(Bucket=bucket_name, Key=s3_key)
        version_id = metadata.get('VersionId')
        last_modified = metadata.get('LastModified')
        print(f"  Metadata retrieved - VersionId: {version_id}, LastModified: {last_modified}")
        return version_id, last_modified
    except ClientError as e:
        print(f"  ERROR getting S3 object metadata for {s3_key}: {e}")
        return None, None
    except Exception as e:
        print(f"  Unexpected ERROR getting S3 object metadata for {s3_key}: {e}")
        return None, None
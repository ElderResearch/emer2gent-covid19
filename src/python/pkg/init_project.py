#!/usr/bin/env python3

import io
import tarfile
from pathlib import Path

import requests


VERSION_ID = "d5R9JQB5KcgJxIlI9CW9BIWn5g5NjC8A"


def download_data():
    """Download data sources archive from S3 and unpack into the data directory"""
    curdir = Path(__file__).resolve()
    data_dir = curdir.parents[3] / "data"
    if not data_dir.exists():
        data_dir.mkdir()

    r = requests.get(
        f"https://emer2gent-covid19.s3.amazonaws.com/data/project_data.tar.gz?versionId={VERSION_ID}"
    )

    with tarfile.open(mode="r:gz", fileobj=io.BytesIO(r.content)) as archive:
        
        import os
        
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(archive, path=data_dir)


if __name__ == "__main__":
    download_data()

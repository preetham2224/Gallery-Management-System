import os
import secrets
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def save_image(file_storage) -> tuple[str, str]:
    """
    Saves original image and creates a thumbnail.
    Returns (saved_filename, original_name).
    """
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    thumb_folder = current_app.config["THUMB_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(thumb_folder, exist_ok=True)

    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    rand = secrets.token_hex(8)
    saved_filename = f"{rand}.{ext}"

    original_path = os.path.join(upload_folder, saved_filename)
    file_storage.save(original_path)

    # Create thumbnail
    thumb_path = os.path.join(thumb_folder, f"{rand}_thumb.{ext}")
    with Image.open(original_path) as im:
        im.thumbnail(current_app.config["THUMB_SIZE"])
        im.save(thumb_path)

    return saved_filename, original_name

# utils.py
def save_video(file_storage) -> tuple[str, str]:
    """
    Saves uploaded video without processing.
    Returns (saved_filename, original_name).
    """
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    original_name = secure_filename(file_storage.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    rand = secrets.token_hex(8)
    saved_filename = f"{rand}.{ext}"

    save_path = os.path.join(upload_folder, saved_filename)
    file_storage.save(save_path)

    return saved_filename, original_name

# Add these functions to your utils.py
def delete_image(filename: str):
    """Delete original image and its thumbnail"""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    thumb_folder = current_app.config["THUMB_FOLDER"]
    
    # Delete original image
    original_path = os.path.join(upload_folder, filename)
    if os.path.exists(original_path):
        os.remove(original_path)
    
    # Delete thumbnail
    base, ext = filename.rsplit(".", 1)
    thumb_filename = f"{base}_thumb.{ext}"
    thumb_path = os.path.join(thumb_folder, thumb_filename)
    if os.path.exists(thumb_path):
        os.remove(thumb_path)

def delete_video(filename: str):
    """Delete video file"""
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    video_path = os.path.join(upload_folder, filename)
    if os.path.exists(video_path):
        os.remove(video_path)
        
def parse_tags(tag_string: str):
    if not tag_string:
        return []
    tags = [t.strip().lower() for t in tag_string.split(",")]
    return [t for t in tags if t]

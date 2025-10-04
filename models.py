from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

# Association table for Photo <-> Tag many-to-many
photo_tags = db.Table(
    "photo_tags",
    db.Column("photo_id", db.Integer, db.ForeignKey("photo.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")  # student | editor | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    albums = db.relationship("Album", backref="owner", lazy=True)
    photos = db.relationship("Photo", backref="uploader", lazy=True)
    videos = db.relationship("Video", backref="uploader", lazy=True)

    # Role helpers
    def is_faculty(self):
        return self.role == "editor"

    def is_admin(self):
        return self.role == "admin"

    def is_editor(self):
        return self.role in ("editor", "admin")

    def __repr__(self):
        return f"<User {self.full_name}>"


class Album(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text)
    visibility = db.Column(db.String(20), default="public")  # public | private
    cover_photo_id = db.Column(db.Integer, db.ForeignKey("photo.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Album {self.title}>"


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)       # saved name
    original_name = db.Column(db.String(255), nullable=False)  # user upload name
    caption = db.Column(db.String(255))
    album_id = db.Column(db.Integer, db.ForeignKey("album.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Tags many-to-many
    tags = db.relationship(
        "Tag",
        secondary=photo_tags,
        backref=db.backref("photos", lazy="dynamic"),
    )

    def thumb_name(self):
        base, ext = self.filename.rsplit(".", 1)
        return f"{base}_thumb.{ext}"

    def __repr__(self):
        return f"<Photo {self.filename}>"


class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    album_id = db.Column(db.Integer, db.ForeignKey("album.id"), nullable=False)

    def __repr__(self):
        return f"<Video {self.filename}>"
    
    # Add this method to get like count
    def like_count(self):
        return len(self.video_likes)

# Add this to your models.py after the Like model
class VideoLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "video_id", name="uniq_video_like"),)

    video = db.relationship("Video", backref=db.backref("video_likes", lazy=True, cascade="all, delete-orphan"), uselist=False)

    def __repr__(self):
        return f"<VideoLike user={self.user_id} video={self.video_id}>"
    
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)

    def __repr__(self):
        return f"<Tag {self.name}>"


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey("photo.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "photo_id", name="uniq_like"),)

    photo = db.relationship("Photo", backref=db.backref("likes", lazy=True, cascade="all, delete-orphan"), uselist=False)

    def __repr__(self):
        return f"<Like user={self.user_id} photo={self.photo_id}>"

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey("photo.id"), nullable=True)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Add relationship to User
    user = db.relationship("User", backref="comments")

    def __repr__(self):
        return f"<Comment {self.body[:20]}>"
    
# Option B: Or create a separate VideoComment model
class VideoComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey("video.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Add relationship to User
    user = db.relationship("User", backref="video_comments")

    def __repr__(self):
        return f"<VideoComment {self.body[:20]}>"

# Then update your Album relationships:
Album.photos = db.relationship(
    "Photo",
    backref="album",
    lazy=True,
    cascade="all, delete-orphan",
    foreign_keys="Photo.album_id",
    passive_deletes=True  # Add this
)
Album.videos = db.relationship(
    "Video",
    backref="album",
    lazy=True,
    cascade="all, delete-orphan",
    foreign_keys="Video.album_id",
    passive_deletes=True  # Add this
)
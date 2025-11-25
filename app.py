import os
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import or_
from config import Config
from models import db, User, Album, Photo, Tag, Like, Comment, Video, VideoLike, VideoComment
from forms import RegisterForm, LoginForm, AlbumForm, PhotoUploadForm, VideoUploadForm, EditProfileForm
from utils import allowed_file, save_image, save_video, parse_tags, delete_image, delete_video
from itertools import chain
from math import ceil
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def get_album_items(album_id):
        photos = Photo.query.filter_by(album_id=album_id).order_by(Photo.created_at.desc()).all()
        videos = Video.query.filter_by(album_id=album_id).order_by(Video.created_at.desc()).all()
        items = sorted(chain(photos, videos), key=lambda x: x.created_at, reverse=True)
        return items


    
    def get_visible_albums_query():
       if current_user.is_authenticated:
         return Album.query.filter(
            or_(Album.visibility == "public", Album.user_id == current_user.id)
        )
       else:
           return Album.query.filter(Album.visibility == "public")
    @app.route("/")
    def landing():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        login_form = LoginForm()
        register_form = RegisterForm()
        return render_template("landing.html", login_form=login_form, register_form=register_form)
    @app.route("/gallery")
    @login_required
    def index():
        q = request.args.get("q", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = 12
        if current_user.is_authenticated:
            photos_q = Photo.query.join(Album, Photo.album_id == Album.id).filter(
                or_(Album.visibility == "public", Album.user_id == current_user.id)
            )
            videos_q = Video.query.join(Album, Video.album_id == Album.id).filter(
                or_(Album.visibility == "public", Album.user_id == current_user.id)
            )
        else:
            photos_q = Photo.query.join(Album, Photo.album_id == Album.id).filter(Album.visibility == "public")
            videos_q = Video.query.join(Album, Video.album_id == Album.id).filter(Album.visibility == "public")
        if q:
            photos_q = photos_q.outerjoin(Photo.tags).filter(
                or_(
                    Photo.caption.ilike(f"%{q}%"),
                    Tag.name.ilike(f"%{q}%"),
                    Album.title.ilike(f"%{q}%")
                )
            )
            videos_q = videos_q.filter(Video.caption.ilike(f"%{q}%"))
            if q.startswith("user:"):
                try:
                    user_id = int(q.split(":")[1])
                    photos_q = photos_q.filter(Photo.user_id == user_id)
                    videos_q = videos_q.filter(Video.user_id == user_id)
                except:
                    flash("Invalid user search format", "warning")
        photos = photos_q.all()
        videos = videos_q.all()
        items = sorted(
            chain(photos, videos),
            key=lambda x: x.created_at,
            reverse=True
        )
        total_items = len(items)
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        items = items[start:end]

        return render_template(
            "index.html",
            items=items,
            q=q,
            page=page,
            total_pages=total_pages,
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = RegisterForm()
        if form.validate_on_submit():
            user = User(
                full_name=form.full_name.data,
                email=form.email.data.lower(),
                password_hash=generate_password_hash(form.password.data),
                role="student",
            )
            db.session.add(user)
            db.session.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        return render_template("auth/register.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        form = LoginForm()
        if form.validate_on_submit():
            login_user(form.user)
            flash("Welcome back!", "success")
            return redirect(url_for("index"))
        return render_template("auth/login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Logged out.", "info")
        return redirect(url_for("landing"))

    @app.route('/profile')
    @login_required
    def profile():
        """User profile page"""
        user = current_user
        albums_count = Album.query.filter_by(user_id=user.id).count()
        photos_count = Photo.query.filter_by(user_id=user.id).count()
        videos_count = Video.query.filter_by(user_id=user.id).count()

        recent_photos = Photo.query.filter_by(user_id=user.id).order_by(Photo.created_at.desc()).limit(5).all()
        recent_videos = Video.query.filter_by(user_id=user.id).order_by(Video.created_at.desc()).limit(5).all()
        recent_activity = sorted(
            chain(recent_photos, recent_videos),
            key=lambda x: x.created_at,
            reverse=True
        )[:10]
        
        return render_template('user/profile.html', 
                            user=user,
                            albums_count=albums_count,
                            photos_count=photos_count,
                            videos_count=videos_count,
                            recent_activity=recent_activity)

    @app.route('/profile/edit', methods=['GET', 'POST'])
    @login_required
    def edit_profile():
        """Edit user profile"""
        form = EditProfileForm()
        
        if form.validate_on_submit():
            current_user.full_name = form.full_name.data
            current_user.email = form.email.data
            if form.password.data:
                current_user.password_hash = generate_password_hash(form.password.data)
            
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            return redirect(url_for('profile'))
        
        elif request.method == 'GET':
            form.full_name.data = current_user.full_name
            form.email.data = current_user.email
        
        return render_template('user/edit_profile.html', form=form)

    @app.route('/albums/shared')
    @login_required
    def shared_albums():
        """Albums shared with the current user"""
        page = request.args.get('page', 1, type=int)
        
        shared_albums = Album.query.filter(
            Album.user_id != current_user.id,
            Album.visibility == 'public'
        ).order_by(Album.created_at.desc()).paginate(page=page, per_page=12, error_out=False)
        
        return render_template('albums/shared.html', albums=shared_albums)

    @app.route('/album/<int:album_id>/share', methods=['GET', 'POST'])
    @login_required
    def share_album(album_id):
        """Share album with specific users"""
        album = Album.query.get_or_404(album_id)
        if album.user_id != current_user.id and not current_user.is_admin():
            abort(403)
        
        if request.method == 'POST':
            flash('Album sharing settings updated', 'success')
            return redirect(url_for('album_detail', album_id=album.id))
        users = User.query.filter(User.id != current_user.id).all()
        
        return render_template('albums/share.html', album=album, users=users)

    @app.route('/favorites')
    @login_required
    def favorites():
        """User's favorite items"""
        page = request.args.get('page', 1, type=int)
        per_page = 12
        liked_photos = Like.query.filter_by(user_id=current_user.id).all()
        liked_videos = VideoLike.query.filter_by(user_id=current_user.id).all()
        favorite_items = []
        for like in liked_photos:
            favorite_items.append({
                'type': 'photo',
                'item': like.photo,
                'liked_at': like.created_at
            })
        
        for like in liked_videos:
            favorite_items.append({
                'type': 'video', 
                'item': like.video,
                'liked_at': like.created_at
            })
        favorite_items.sort(key=lambda x: x['liked_at'], reverse=True)
        total_items = len(favorite_items)
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        items_page = favorite_items[start:end]
        
        return render_template('favorites.html', 
                            items=items_page,
                            page=page,
                            total_pages=total_pages)
    

    @app.route('/my-uploads')
    @login_required
    def my_uploads():
        """User's uploaded content"""
        page = request.args.get('page', 1, type=int)
        per_page = 12
        user_photos = Photo.query.filter_by(user_id=current_user.id).order_by(Photo.created_at.desc()).all()
        user_videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).all()
        upload_items = []
        for photo in user_photos:
            upload_items.append({
                'type': 'photo',
                'item': photo,
                'created_at': photo.created_at
            })
        
        for video in user_videos:
            upload_items.append({
                'type': 'video', 
                'item': video,
                'created_at': video.created_at
            })
        upload_items.sort(key=lambda x: x['created_at'], reverse=True)

        total_items = len(upload_items)
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        items_page = upload_items[start:end]
        
        return render_template('user/uploads.html', 
                            items=items_page,
                            page=page,
                            total_pages=total_pages,
                            photo_count=len(user_photos),
                            video_count=len(user_videos))
    
    @app.route('/my-albums')
    @login_required
    def my_albums():
        """User's albums page"""
        page = request.args.get('page', 1, type=int)
        per_page = 12
        user_albums = Album.query.filter_by(user_id=current_user.id).order_by(Album.created_at.desc()).all()
        total_items = len(user_albums)
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        albums_page = user_albums[start:end]
        
        return render_template('user/my_albums.html', 
                            albums=albums_page,
                            page=page,
                            total_pages=total_pages,
                            total_albums=total_items)
    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.is_admin():
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    @app.route("/dashboard/admin")
    @login_required
    def admin_dashboard():
        if not current_user.is_admin():
            abort(403)
        total_users = User.query.count()
        total_albums = Album.query.count()
        total_photos = Photo.query.count()
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        import os
        from config import Config
        upload_size = 0
        thumb_size = 0
        try:
            for filename in os.listdir(Config.UPLOAD_FOLDER):
                filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
                upload_size += os.path.getsize(filepath)
            
            for filename in os.listdir(Config.THUMB_FOLDER):
                filepath = os.path.join(Config.THUMB_FOLDER, filename)
                thumb_size += os.path.getsize(filepath)
        except:
            upload_size = thumb_size = 0
        
        total_storage = upload_size + thumb_size
        
        return render_template("admin/dashboard.html", 
                            total_users=total_users,
                            total_albums=total_albums,
                            total_photos=total_photos,
                            recent_users=recent_users,
                            upload_size=upload_size,
                            thumb_size=thumb_size,
                            total_storage=total_storage)

    @app.route("/dashboard/user")
    @login_required
    def user_dashboard():
        my_albums = Album.query.filter_by(user_id=current_user.id).order_by(Album.created_at.desc()).all()
        recent_photos = Photo.query.filter_by(user_id=current_user.id).order_by(Photo.created_at.desc()).limit(6).all()
        recent_videos = Video.query.filter_by(user_id=current_user.id).order_by(Video.created_at.desc()).limit(3).all()
        recent_uploads = []
        for photo in recent_photos:
            recent_uploads.append({
                'type': 'photo',
                'id': photo.id,
                'thumb': photo.thumb_name()
                
            })
        for video in recent_videos:
            recent_uploads.append({
                'type': 'video', 
                'id': video.id,
                'thumb': ''        
            })
        album_count = len(my_albums)
        photo_count = Photo.query.filter_by(user_id=current_user.id).count()
        video_count = Video.query.filter_by(user_id=current_user.id).count()
        recent_photo_likes = Like.query.filter_by(user_id=current_user.id).order_by(Like.created_at.desc()).limit(6).all()
        recent_video_likes = VideoLike.query.filter_by(user_id=current_user.id).order_by(VideoLike.created_at.desc()).limit(3).all()
        liked_items = []
        for like in recent_photo_likes:
            liked_items.append({
                'type': 'photo',
                'item': like.photo,
                'created_at': like.created_at
            })
        for like in recent_video_likes:
            liked_items.append({
                'type': 'video',
                'item': like.video,
                'created_at': like.created_at
            })
        
        return render_template("user/dashboard.html", 
                            albums=my_albums,
                            recent_uploads=recent_uploads,
                            album_count=album_count,
                            photo_count=photo_count,
                            video_count=video_count,
                            liked_items=liked_items)
    @app.route("/albums")
    def albums_list():
        page = request.args.get("page", 1, type=int)
        query = Album.query
        if not (current_user.is_authenticated and current_user.is_admin()):
           if current_user.is_authenticated:
              query = query.filter(
                  or_(Album.visibility == "public", Album.user_id == current_user.id)
              )
           else:
                query = query.filter(Album.visibility == "public")

        albums = query.order_by(Album.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
        return render_template("albums/list.html", albums=albums)

    @app.route("/albums/create", methods=["GET", "POST"])
    @login_required
    def album_create():
        form = AlbumForm()
        if form.validate_on_submit():
            album = Album(
                title=form.title.data,
                description=form.description.data,
                visibility=form.visibility.data,
                user_id=current_user.id
            )
            db.session.add(album)
            db.session.commit()
            flash("Album created.", "success")
            return redirect(url_for("albums_list"))
        return render_template("albums/create.html", form=form)

    @app.route("/album/<int:album_id>")
    def album_detail(album_id):
        page = request.args.get("page", 1, type=int)
        per_page = 12

        album = Album.query.get_or_404(album_id)

        photos = Photo.query.filter(Photo.album_id == album.id).all()
        videos = Video.query.filter(Video.album_id == album.id).all()
        items = sorted(
            chain(photos, videos),
            key=lambda x: x.created_at,
            reverse=True
        )
        total_items = len(items)
        total_pages = ceil(total_items / per_page) if total_items > 0 else 1
        start = (page - 1) * per_page
        end = start + per_page
        items = items[start:end]
        return render_template(
            "albums/detail.html",
            album=album,
            items=items,
            page=page,
            total_pages=total_pages,
        )

    @app.post("/albums/<int:album_id>/delete")
    @login_required
    def delete_album(album_id):
        album = Album.query.get_or_404(album_id)
        
        if not (current_user.is_admin() or album.user_id == current_user.id):
            abort(403)
        
        for photo in album.photos:
            photo.tags.clear()
        for photo in album.photos:
            delete_image(photo.filename)
            db.session.delete(photo)
        
        for video in album.videos:
            delete_video(video.filename)
            db.session.delete(video)
        db.session.delete(album)
        db.session.commit()
        
        flash("Album and all its contents deleted successfully.", "success")
        return redirect(url_for('albums_list'))
    @app.route("/photos/upload", methods=["GET", "POST"])
    @login_required
    def photo_upload():
        form = PhotoUploadForm()
        form.album.choices = [(a.id, a.title) for a in Album.query.filter_by(user_id=current_user.id).all()]
        if request.method == "POST" and form.validate_on_submit():
            file = request.files.get("image")
            if not file or file.filename == "":
                flash("Please select an image.", "warning")
                return render_template("photos/upload.html", form=form)
            if not allowed_file(file.filename):
                flash("Unsupported file type.", "danger")
                return render_template("photos/upload.html", form=form)
            saved_filename, original_name = save_image(file)
            photo = Photo(
                filename=saved_filename,
                original_name=original_name,
                caption=form.caption.data,
                album_id=form.album.data,
                user_id=current_user.id,
            )
            db.session.add(photo)
            for tag_text in parse_tags(form.tags.data):
                tag = Tag.query.filter_by(name=tag_text).first()
                if not tag:
                    tag = Tag(name=tag_text)
                    db.session.add(tag)
                photo.tags.append(tag)

            db.session.commit()
            flash("Photo uploaded.", "success")
            return redirect(url_for("album_detail", album_id=form.album.data))
        return render_template("photos/upload.html", form=form)

    @app.route("/photos/<int:photo_id>")
    def photo_detail(photo_id):
        photo = Photo.query.get_or_404(photo_id)
        liked = False
        if current_user.is_authenticated:
            liked = Like.query.filter_by(user_id=current_user.id, photo_id=photo.id).first() is not None
        all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
        all_videos = Video.query.order_by(Video.created_at.desc()).all()
        all_items = sorted(
            chain(all_photos, all_videos),
            key=lambda x: x.created_at,
            reverse=True
        )
        current_index = None
        for i, item in enumerate(all_items):
            if (hasattr(item, 'id') and item.id == photo_id and 
                item.__class__.__name__ == 'Photo'):
                current_index = i
                break
        prev_item = all_items[current_index - 1] if current_index is not None and current_index > 0 else None
        next_item = all_items[current_index + 1] if current_index is not None and current_index < len(all_items) - 1 else None
        comments = Comment.query.filter_by(photo_id=photo.id).order_by(Comment.created_at.desc()).all()

        return render_template(
            "photos/detail.html",
            photo=photo,
            liked=liked,
            comments=comments,
            prev_item=prev_item,
            next_item=next_item,
            all_items=all_items
        )
    
    @app.post("/photos/<int:photo_id>/like")
    @login_required
    def like_photo(photo_id):
        photo = Photo.query.get_or_404(photo_id)
        existing_like = Like.query.filter_by(user_id=current_user.id, photo_id=photo.id).first()
        
        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            flash("Photo unliked.", "info")
        else:
            like = Like(user_id=current_user.id, photo_id=photo.id)
            db.session.add(like)
            db.session.commit()
            flash("Photo liked!", "success")
        
        return redirect(url_for("photo_detail", photo_id=photo.id))

    @app.post("/photos/<int:photo_id>/comment")
    @login_required
    def comment_photo(photo_id):
        photo = Photo.query.get_or_404(photo_id)
        body = request.form.get("body", "").strip()
        if body:
            c = Comment(body=body, user_id=current_user.id, photo_id=photo.id)
            db.session.add(c)
            db.session.commit()
        else:
            flash("Comment cannot be empty.", "warning")
        return redirect(url_for("photo_detail", photo_id=photo.id))
    

    @app.route("/comments/<int:comment_id>/delete", methods=["POST"])
    @login_required
    def delete_comment(comment_id):
        comment = Comment.query.get_or_404(comment_id)

        if comment.user_id != current_user.id and not current_user.is_admin():
            abort(403)

        db.session.delete(comment)
        db.session.commit()
        flash("Comment deleted.", "success")
        return redirect(request.referrer or url_for("index"))

    
    @app.post("/photos/<int:photo_id>/delete")
    @login_required
    def delete_photo(photo_id):
        photo = Photo.query.get_or_404(photo_id)
        
        if not (current_user.is_admin() or photo.user_id == current_user.id):
            abort(403)
        
        album_id = photo.album_id
        delete_image(photo.filename)
        db.session.delete(photo)
        db.session.commit()
        
        flash("Photo deleted successfully.", "success")
        return redirect(url_for('album_detail', album_id=album_id))
    
    @app.route("/videos/upload", methods=["GET", "POST"])
    @login_required
    def video_upload():
        form = VideoUploadForm()
        form.album.choices = [(a.id, a.title) for a in Album.query.filter_by(user_id=current_user.id).all()]
        if request.method == "POST" and form.validate_on_submit():
            file = request.files.get("video")
            if not file or file.filename == "":
                flash("Please select a video.", "warning")
                return render_template("videos/upload.html", form=form)
            if not allowed_file(file.filename):
                flash("Unsupported file type.", "danger")
                return render_template("videos/upload.html", form=form)

            saved_filename, original_name = save_video(file)
            video = Video(
                filename=saved_filename,
                original_name=original_name,
                caption=form.caption.data,
                album_id=form.album.data,
                user_id=current_user.id,
            )
            db.session.add(video)
            for tag_text in parse_tags(form.tags.data):
                tag = Tag.query.filter_by(name=tag_text).first()
                if not tag:
                    tag = Tag(name=tag_text)
                    db.session.add(tag)
            db.session.commit()
            flash("Video uploaded.", "success")
            return redirect(url_for("album_detail", album_id=form.album.data))
        return render_template("videos/upload.html", form=form)
    

    @app.route("/videos/<int:video_id>")
    def video_detail(video_id):
        video = Video.query.get_or_404(video_id)
        liked = False
        if current_user.is_authenticated:
            liked = VideoLike.query.filter_by(user_id=current_user.id, video_id=video.id).first() is not None

        all_photos = Photo.query.order_by(Photo.created_at.desc()).all()
        all_videos = Video.query.order_by(Video.created_at.desc()).all()
        
        all_items = sorted(
            chain(all_photos, all_videos),
            key=lambda x: x.created_at,
            reverse=True
        )
        current_index = None
        for i, item in enumerate(all_items):
            if (hasattr(item, 'id') and item.id == video_id and 
                item.__class__.__name__ == 'Video'):
                current_index = i
                break
        prev_item = all_items[current_index - 1] if current_index is not None and current_index > 0 else None
        next_item = all_items[current_index + 1] if current_index is not None and current_index < len(all_items) - 1 else None
        comments = VideoComment.query.filter_by(video_id=video.id).order_by(VideoComment.created_at.desc()).all()

        return render_template(
            "videos/detail.html",
            video=video,
            liked=liked,
            comments=comments,
            prev_item=prev_item,
            next_item=next_item,
            all_items=all_items
        )
   
    @app.post("/videos/<int:video_id>/like")
    @login_required
    def like_video(video_id):
        video = Video.query.get_or_404(video_id)
        existing_like = VideoLike.query.filter_by(user_id=current_user.id, video_id=video.id).first()
        
        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            flash("Video unliked.", "info")
        else:
            like = VideoLike(user_id=current_user.id, video_id=video.id)
            db.session.add(like)
            db.session.commit()
            flash("Video liked!", "success")
        
        return redirect(url_for('video_detail', video_id=video.id))

    @app.post("/videos/<int:video_id>/unlike")
    @login_required
    def unlike_video(video_id):
        video = Video.query.get_or_404(video_id)
        like = VideoLike.query.filter_by(user_id=current_user.id, video_id=video.id).first()
        if like:
            db.session.delete(like)
            db.session.commit()
            flash("Video unliked.", "info")
        else:
            flash("You haven't liked this video.", "warning")
        return redirect(url_for('video_detail', video_id=video.id))


    @app.post("/videos/<int:video_id>/comment")
    @login_required
    def comment_video(video_id):
        video = Video.query.get_or_404(video_id)
        body = request.form.get("body", "").strip()
        if body:
            c = VideoComment(body=body, user_id=current_user.id, video_id=video.id)
            db.session.add(c)
            db.session.commit()
        else:
            flash("Comment cannot be empty.", "warning")
        return redirect(url_for('video_detail', video_id=video.id))
    
    @app.route("/video_comments/<int:comment_id>/delete", methods=["POST"])
    @login_required
    def delete_video_comment(comment_id):
        comment = VideoComment.query.get_or_404(comment_id)

        if comment.user_id != current_user.id and not current_user.is_admin():
            abort(403)

        db.session.delete(comment)
        db.session.commit()
        flash("Comment deleted.", "success")
        return redirect(request.referrer or url_for("index"))

    
    @app.post("/videos/<int:video_id>/delete")
    @login_required
    def delete_video_route(video_id):
        video = Video.query.get_or_404(video_id)
        
        if not (current_user.is_admin() or video.user_id == current_user.id):
            abort(403)
        
        album_id = video.album_id
        delete_video(video.filename)
        db.session.delete(video)
        db.session.commit()
        flash("Video deleted successfully.", "success")
        return redirect(url_for('album_detail', album_id=album_id))
    def admin_required():
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)

    @app.route("/admin/users")
    @login_required
    def admin_users():
        admin_required()
        users = User.query.order_by(User.created_at.desc()).all()
        return render_template("admin/users.html", users=users)

    @app.post("/admin/users/<int:user_id>/role")
    @login_required
    def admin_set_role(user_id):
        admin_required()
        role = request.form.get("role", "student")
        if role not in ("student", "editor", "admin"):
            abort(400)
        if current_user.id == user_id and role != "admin":
            flash("Admins cannot demote themselves here.", "warning")
            return redirect(url_for("admin_users"))
        user = User.query.get_or_404(user_id)
        user.role = role
        db.session.commit()
        flash("Role updated.", "success")
        return redirect(url_for("admin_users"))

    @app.route("/admin/settings")
    @login_required
    def admin_settings():
        admin_required()
        return render_template("admin/settings.html")
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("base.html", content="403 Forbidden"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("base.html", content="404 Not Found"), 404

    return app


app = create_app()

if __name__ == "__main__":
    with app.app_context():
        from models import db, User
        db.create_all()
        if not User.query.filter_by(email="admin@college.edu").first():
            from werkzeug.security import generate_password_hash
            admin = User(
                full_name="Admin",
                email="admin@college.edu",
                password_hash=generate_password_hash("Admin@123"),
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()
            print("Created default admin: admin@college.edu / Admin@123")
    app.run(debug=True)


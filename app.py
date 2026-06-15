import streamlit as st
import tempfile
import os
import base64
import urllib.request
import subprocess
import ssl
import shutil
from yt_dlp import YoutubeDL
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

st.set_page_config(page_title="Video Downloader PRO", layout="centered")

st.markdown("""
<style>

/* Responsive container */
.stAppHeader, ._profileContainer_gzau3_53, ._container_gzau3_1 _viewerBadge_nim44_23, ._stateContainer_nim44_26 > a, ._stateContainer_nim44_26 > div {
    display: none !important;            
}
.block-container {
    max-width: 800px;
    width: 100%;
    padding-top: 2rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

/* Fix text overflow */
h1, h2, h3 {
    word-wrap: break-word;
}

/* Make input responsive */
.stTextInput input {
    width: 100% !important;
}

/* Mobile adjustments */
@media (max-width: 768px) {

    .block-container {
        max-width: 100%;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }

    h1 {
        font-size: 1.6rem !important;
    }

    h2 {
        font-size: 1.3rem !important;
    }

    h3 {
        font-size: 1.15rem !important;
    }

}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center; margin-bottom:0px; margin-top:20px;">
    <a href="https://sudipdebnath-cloud.github.io/" target="_blank">
        <img src="https://sudipdebnath-cloud.github.io/images/sd_dp.png"
             width="150"
             style="border-radius:50%; border:5px solid #1f77b4;">
    </a>
</div>
""", unsafe_allow_html=True)

st.title("🎬 SD Video Downloader PRO")
st.caption("Download from YouTube, IG, X, FB, TikTok, Pinterest & 1000+ more sites!")

# ---------------- INPUT ----------------
url = st.text_input("Paste Video URL")

# Compact HTML to save space and provide quick step-by-step instructions
st.markdown("""
<p style='font-size: 0.85rem; color: gray; margin-bottom: -5px;'>
    🔒 <b>Restricted Video?</b> 
    1. Install <i>'Get cookies.txt LOCALLY'</i> extension. 
    2. Open video's site. 
    3. Export & upload below.
</p>
""", unsafe_allow_html=True)

uploaded_cookie = st.file_uploader("Upload cookies.txt", type=["txt"])

# ---------------- HELPERS ----------------
def is_youtube(u): return "youtube.com" in u or "youtu.be" in u
def is_instagram(u): return "instagram.com" in u
def is_facebook(u): return "facebook.com" in u or "fb.watch" in u

def normalize_youtube_url(u):
    if "youtu.be" in u:
        return u.split("?")[0]

    parsed = urlparse(u)
    qs = parse_qs(parsed.query)
    vid = qs.get("v", [None])[0]

    if not vid:
        return u

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode({"v": vid}),
        ""
    ))

def get_cookie_path(uploaded_file):
    if uploaded_file:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(uploaded_file.read())
        tmp.close()
        return tmp.name
        
    try:
        if "STATIC_COOKIES" in st.secrets:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
            tmp.write(st.secrets["STATIC_COOKIES"])
            tmp.close()
            return tmp.name
    except Exception:
        pass

    return None

cookie_path = get_cookie_path(uploaded_cookie)

# ---------------- FETCH VIDEO INFO ----------------
if st.button("Fetch Video Info") and url:

    st.session_state.pop("formats", None)
    st.session_state.pop("info", None)

    with st.spinner("Analyzing video..."):
        try:
            clean_url = normalize_youtube_url(url) if is_youtube(url) else url

            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "forceipv4": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios", "android", "mweb"],
                        "player_skip_bundle_url": True,
                    },
                    "instagram": {
                        "check_display_resources": True,
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/",
                }
            }

            if cookie_path:
                ydl_opts["cookiefile"] = cookie_path

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)

            st.session_state["info"] = info

            formats = {}

            for f in info.get("formats", []):
                height = f.get("height")
                if not height:
                    continue

                size = f.get("filesize") or f.get("filesize_approx")
                size_txt = f"{round(size/1024/1024,1)} MB" if size else "Unknown"
                label = f"{height}p • {size_txt}"

                if height not in formats.values():
                    formats[label] = height

            if not formats:
                formats["Best Available"] = 0

            st.session_state["formats"] = dict(
                sorted(formats.items(), key=lambda x: x[1], reverse=True)
            )

            st.success("✅ Video ready to download")

        except Exception as e:
            msg = str(e).lower()
            if "login required" in msg or "cookies" in msg:
                st.error("🔒 Login required. Upload cookies.txt or configure secrets.")
            elif "rate-limit" in msg:
                st.warning("⚠️ Platform rate limit reached. Try again later.")
            else:
                st.error("❌ Failed to fetch video info")
                st.exception(e)

# ---------------- VIDEO PREVIEW ----------------
if "info" in st.session_state:

    info = st.session_state["info"]
    thumbnail = info.get("thumbnail")
    title = info.get("title", "Video")
    duration = info.get("duration")

    if thumbnail:
        try:
            req = urllib.request.Request(
                thumbnail, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response:
                image_bytes = response.read()
            st.image(image_bytes, width="stretch")
        except Exception as e:
            st.image(thumbnail, width="stretch")

    st.subheader(title)

    if duration:
        duration = int(duration)
        mins = (duration % 3600) // 60
        secs = duration % 60
        st.write(f"⏱ Duration: {mins}:{secs:02d}")

# ---------------- DOWNLOAD OPTIONS ----------------
if "formats" in st.session_state:

    st.divider()
    st.subheader("Download Options")

    mode = st.radio(
        "Select Download Type",
        ["Best Quality", "Choose Resolution", "Audio Only (MP3)"]
    )

    selected_height = None

    if mode == "Choose Resolution":
        choice = st.selectbox("Resolution", list(st.session_state["formats"].keys()))
        selected_height = st.session_state["formats"][choice]

    # ---------------- DOWNLOAD ----------------
    if st.button("⬇️ Download"):

        bar = st.progress(0)
        status = st.empty()

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                eta = d.get("eta")
                frag_index = d.get("fragment_index")
                frag_count = d.get("fragment_count")

                try:
                    if total:
                        percent = int(downloaded * 100 / total)
                        bar.progress(percent)
                        dl_mb = downloaded / 1024 / 1024
                        total_mb = total / 1024 / 1024
                        size_txt = f"{dl_mb:.1f}/{total_mb:.1f} MB"
                    elif frag_index and frag_count:
                        percent = int(frag_index * 100 / frag_count)
                        bar.progress(percent)
                        size_txt = f"fragment {frag_index}/{frag_count}"
                    else:
                        percent = 0
                        size_txt = "..."

                    speed_txt = f"{speed / 1024 / 1024:.2f} MB/s" if speed else "--"
                    eta_txt = f"{eta // 60}:{eta % 60:02d}" if eta else "--:--"
                    status.text(f"⬇ {percent}% • {size_txt} • ⚡ {speed_txt} • ⏳ ETA {eta_txt}")
                except:
                    pass

            elif d["status"] == "finished":
                try:
                    bar.progress(100)
                    status.text("🔄 Processing media...")
                except:
                    pass

        with tempfile.TemporaryDirectory() as tmpdir:

            clean_url = normalize_youtube_url(url) if is_youtube(url) else url

            if mode == "Audio Only (MP3)":
                format_string = "bestaudio/best"
            elif mode == "Best Quality":
                format_string = "bestvideo+bestaudio/best"
            else:
                format_string = f"bestvideo[height<={selected_height}]+bestaudio/best"

            ydl_opts = {
                "format": format_string,
                "merge_output_format": "mp4",
                "outtmpl": os.path.join(tmpdir, "%(title).60s_%(id)s.%(ext)s"),
                "restrictfilenames": True,
                "progress_hooks": [hook],
                "retries": 10,
                "fragment_retries": 10,
                "concurrent_fragment_downloads": 5,
                "buffersize": 1024 * 1024 * 16,
                "forceipv4": True,
                "noplaylist": True,
                "continuedl": True,
                "overwrites": True,
                "nocheckcertificate": True,
                "http_chunk_size": 10485760,
                "extractor_args": {
                    "youtube": {
                        "player_client": ["ios", "android", "mweb"],
                        "player_skip_bundle_url": True,
                    },
                    "instagram": {
                        "check_display_resources": True,
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.google.com/",
                }
            }

            if cookie_path:
                ydl_opts["cookiefile"] = cookie_path

            if mode == "Audio Only (MP3)":
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]

            try:
                try:
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(clean_url, download=True)
                except Exception:
                    # Silently fall back to standard format for flat files (Twitter, Pinterest, TikTok)
                    ydl_opts["format"] = "best"
                    with YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(clean_url, download=True)

                base = os.path.splitext(ydl.prepare_filename(info))[0]
                final = None

                for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus"):
                    path = base + ext
                    if os.path.exists(path):
                        final = path
                        break

                if not final:
                    st.error("❌ Downloaded file not found")
                    st.stop()

                # --- FIX FOR IMAGE+AUDIO REELS ---
                has_video_track = True
                
                if info.get('vcodec') == 'none':
                    has_video_track = False
                
                if final.endswith((".mp3", ".m4a", ".opus", ".wav")):
                    has_video_track = False

                if mode != "Audio Only (MP3)" and not has_video_track:
                    thumbnail_url = info.get("thumbnail")
                    
                    if thumbnail_url:
                        status.text("🖼️ Rendering image & audio into video... (Takes a moment)")
                        bar.progress(85)
                        
                        thumb_path = os.path.join(tmpdir, "cover.jpg")
                        rendered_video_path = os.path.join(tmpdir, "rendered_video.mp4")
                        
                        try:
                            # 1. Bypass macOS Python SSL Certificate bug
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode = ssl.CERT_NONE

                            req = urllib.request.Request(
                                thumbnail_url, 
                                headers={'User-Agent': 'Mozilla/5.0'}
                            )
                            with urllib.request.urlopen(req, context=ctx) as response, open(thumb_path, 'wb') as f:
                                f.write(response.read())
                            
                            # 2. Auto-locate FFmpeg on Mac/Linux
                            ffmpeg_cmd = shutil.which("ffmpeg") or "ffmpeg"

                            # 3. Render Video with FFmpeg
                            cmd = [
                                ffmpeg_cmd, "-y",
                                "-loop", "1", "-framerate", "1", 
                                "-i", thumb_path,                
                                "-i", final,                     
                                "-c:v", "libx264", "-tune", "stillimage",
                                "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", 
                                "-c:a", "aac", "-b:a", "192k",
                                "-pix_fmt", "yuv420p",           
                                "-shortest", rendered_video_path 
                            ]
                            
                            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                            
                            final = rendered_video_path
                            
                        except FileNotFoundError:
                            st.error(f"🚨 FFmpeg not found! Path searched: {shutil.which('ffmpeg')}")
                            st.stop()
                        except subprocess.CalledProcessError as e:
                            st.error(f"🚨 FFmpeg crashed during render! Error: {e.stderr[-200:]}")
                            st.stop()
                        except Exception as e:
                            st.error(f"🚨 Python crashed during thumbnail prep! Error: {str(e)}")
                            st.stop()

                bar.progress(100)
                status.text("✅ Download complete")

                with open(final, "rb") as f:
                    st.download_button(
                        "💾 Save Video",
                        f,
                        file_name=os.path.basename(final),
                        mime="application/octet-stream"
                    )

            except Exception as e:
                msg = str(e).lower()
                if "403" in msg or "forbidden" in msg:
                    if not cookie_path:
                        st.error("🚫 Platform blocked this download. Upload cookies.txt.")
                    else:
                        st.error("⚠️ Cookies expired. Export fresh cookies.")
                elif "login required" in msg or "cookies" in msg:
                    st.error("🔒 Login required. Upload cookies.txt.")
                elif "rate-limit" in msg:
                    st.warning("⏳ Rate limit reached. Try later.")
                else:
                    st.error("❌ Download failed")
                    st.exception(e)
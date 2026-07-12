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

/* Thumbnail Download Button Hover Effect */
.thumb-dl-btn {
    transition: all 0.2s ease-in-out;
}
.thumb-dl-btn:hover {
    background: rgba(0, 0, 0, 0.8) !important;
    transform: scale(1.1);
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

st.markdown("""
<p style='font-size: 0.85rem; color: gray; margin-bottom: -5px;'>
    🔒 <b>Restricted Video?</b> Pick a cookie source below — using your browser's
    existing login is usually the most reliable, since exported cookie files
    expire and need re-exporting.
</p>
""", unsafe_allow_html=True)

def _chrome_installed():
    return os.path.exists("/Applications/Google Chrome.app")

def _safari_installed():
    return os.path.exists("/Applications/Safari.app")

def _detect_viewing_browser():
    """Look at the User-Agent of the browser currently loading this page
    to guess which browser to pull cookies from. Falls back to checking
    which browsers are installed if headers aren't available (older
    Streamlit versions)."""
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        ua = ""

    if ua:
        # Chrome (and Chromium/Edge) UAs always include "Chrome"/"Chromium"/"Edg",
        # even though they also contain a legacy "Safari/xxx" token — so check
        # for those first. Only treat it as Safari if none of those are present.
        if any(tag in ua for tag in ("Chrome", "Chromium", "Edg")):
            return "Use browser (Chrome)"
        if "Safari" in ua and "Version" in ua:
            return "Use browser (Safari)"

    if _chrome_installed():
        return "Use browser (Chrome)"
    if _safari_installed():
        return "Use browser (Safari)"
    return "None"

_cookie_options = ["None", "Use browser (Chrome)", "Use browser (Safari)", "Upload cookies.txt"]
_default_cookie_index = _cookie_options.index(_detect_viewing_browser())

cookie_source = st.radio(
    "Cookie source (for login-required Instagram/YouTube videos)",
    _cookie_options,
    index=_default_cookie_index,
    horizontal=True,
)

uploaded_cookie = None
browser_for_cookies = None

if cookie_source == "Upload cookies.txt":
    st.caption("Install the 'Get cookies.txt LOCALLY' extension, open the video's site while logged in, export, then upload here.")
    uploaded_cookie = st.file_uploader("Upload cookies.txt", type=["txt"])
elif cookie_source == "Use browser (Chrome)":
    st.caption("Make sure you're logged into Instagram/YouTube in Chrome on this Mac. APP will read the session directly — nothing to export.")
    browser_for_cookies = "chrome"
elif cookie_source == "Use browser (Safari)":
    st.caption("Safari's cookie store is protected by macOS — if this fails, grant your terminal 'Full Disk Access' in System Settings > Privacy & Security, or use Chrome instead.")
    browser_for_cookies = "safari"

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
    cookie_text = None

    if uploaded_file:
        cookie_text = uploaded_file.read().decode("utf-8", errors="ignore")
    else:
        try:
            if "STATIC_COOKIES" in st.secrets:
                cookie_text = st.secrets["STATIC_COOKIES"]
        except Exception:
            pass

    if cookie_text:
        cookie_text = cookie_text.replace(".x.com", ".twitter.com").replace("x.com\t", "twitter.com\t")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
        tmp.write(cookie_text)
        tmp.close()
        return tmp.name

    return None


def get_cookie_ydl_opts(uploaded_file, browser_name):
    """Returns a dict to merge into ydl_opts for whichever cookie source is
    active. cookiefile and cookiesfrombrowser are mutually exclusive in
    APP, so only one key is ever set."""
    if browser_name:
        # Reads the session straight from the browser's own cookie store —
        # no export/upload, and it can't go stale the way a saved file can.
        return {"cookiesfrombrowser": (browser_name,)}

    cookie_path = get_cookie_path(uploaded_file)
    if cookie_path:
        return {"cookiefile": cookie_path}

    return {}


def get_stream_codec(path, stream_type):
    """Return the codec name of the first stream of the given type
    ('v' for video, 'a' for audio), or None if there isn't one / ffprobe fails."""
    ffprobe_cmd = shutil.which("ffprobe") or "ffprobe"
    try:
        result = subprocess.run(
            [
                ffprobe_cmd, "-v", "error",
                "-select_streams", f"{stream_type}:0",
                "-show_entries", "stream=codec_name",
                "-of", "csv=p=0",
                path,
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15,
        )
        codec = result.stdout.strip()
        return codec or None
    except Exception:
        return None


def ensure_player_compatible(path, tmpdir, status=None, bar=None):
    """Re-encode to H.264/AAC only if the downloaded file isn't already in
    a widely-compatible codec (QuickTime, Windows, mobile players). This
    keeps normal H.264 downloads fast and only pays the re-encode cost
    when the platform served something like VP9/AV1 + Opus."""
    video_codec = get_stream_codec(path, "v")
    audio_codec = get_stream_codec(path, "a")

    video_ok = video_codec in ("h264",)
    audio_ok = audio_codec is None or audio_codec in ("aac",)

    if video_ok and audio_ok:
        return path  # already compatible, nothing to do

    if status:
        status.text("🔄 Converting for player compatibility...")
    if bar:
        bar.progress(90)

    ffmpeg_cmd = shutil.which("ffmpeg") or "ffmpeg"
    fixed_path = os.path.join(tmpdir, "compat_" + os.path.basename(path))

    cmd = [
        ffmpeg_cmd, "-y",
        "-i", path,
        "-c:v", "libx264", "-c:a", "aac",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        fixed_path,
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=600)
        return fixed_path
    except Exception:
        # If re-encoding fails for any reason, fall back to the original
        # file rather than blocking the download entirely.
        return path


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
                    # FIX: Removed the restrictive mobile player_client override
                    # Now yt-dlp will fetch desktop streams, unlocking 1080p+ DASH formats!
                    "youtube": {},
                    "instagram": {
                        "check_display_resources": True,
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": clean_url, 
                }
            }

            ydl_opts.update(get_cookie_ydl_opts(uploaded_cookie, browser_for_cookies))

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=False)

            st.session_state["info"] = info

            # === CLEANER UI FORMAT LOGIC ===
            formats_dict = {}

            for f in info.get("formats", []):
                height = f.get("height")
                vcodec = f.get("vcodec", "none")
                ext = f.get("ext", "")

                # Skip audio-only streams
                if not height or vcodec == "none":
                    continue
                
                # For YouTube, strictly only list MP4 formats in the dropdown 
                # This prevents the UI from falsely promising 4K (which is WebM-only)
                if is_youtube(clean_url) and ext != "mp4":
                    continue

                size = f.get("filesize") or f.get("filesize_approx")
                size_txt = f" • {round(size/1024/1024,1)} MB" if size else ""
                
                # Dictionary keyed by height naturally overwrites lower-bitrate duplicates
                # Because yt-dlp sorts worst-to-best, the last one stored is the best MP4 version.
                formats_dict[height] = f"{height}p{size_txt}"

            if not formats_dict:
                st.session_state["formats"] = {"Best Available": 0}
            else:
                # Flip the dictionary for the UI and sort largest to smallest
                st.session_state["formats"] = dict(
                    sorted({label: h for h, label in formats_dict.items()}.items(), key=lambda x: x[1], reverse=True)
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
            
            b64_image = base64.b64encode(image_bytes).decode()
            img_src = f"data:image/jpeg;base64,{b64_image}"
        except Exception:
            img_src = thumbnail

        html_code = f"""
        <div style="position: relative; border-radius: 8px; overflow: hidden; margin-bottom: 1rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <img src="{img_src}" style="width: 100%; display: block; object-fit: inherit;">
            <a href="{img_src}" download="thumbnail.jpg" title="Download Thumbnail" class="thumb-dl-btn"
               style="position: absolute; top: 10px; right: 10px; background: rgba(0, 0, 0, 0.5); 
                      color: white; border-radius: 50%; width: 40px; height: 40px; 
                      display: flex; align-items: center; justify-content: center; 
                      text-decoration: none; backdrop-filter: blur(4px);">
               <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                   <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                   <polyline points="7 10 12 15 17 10"></polyline>
                   <line x1="12" y1="15" x2="12" y2="3"></line>
               </svg>
            </a>
        </div>
        """
        st.markdown(html_code, unsafe_allow_html=True)

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

            is_social_media = is_instagram(clean_url) or is_facebook(clean_url) or "tiktok.com" in clean_url

            if mode == "Audio Only (MP3)":
                format_string = "bestaudio/best"
            elif mode == "Best Quality":
                if is_social_media:
                    format_string = "best[ext=mp4]/best"
                else:
                    format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best"
            else:
                if is_social_media:
                    format_string = f"best[ext=mp4][height<={selected_height}]/best[height<={selected_height}]/best"
                else:
                    format_string = f"bestvideo[ext=mp4][height<={selected_height}]+bestaudio[ext=m4a]/bestvideo[height<={selected_height}]+bestaudio/best[ext=mp4]/best"

            ydl_opts = {
                "format": format_string,
                "merge_output_format": "mp4",
                "format_sort": ["vcodec:h264", "acodec:aac", "ext:mp4:m4a", "res"],
                "outtmpl": os.path.join(tmpdir, "%(title).60s_%(id)s.%(ext)s"),
                "restrictfilenames": True,
                "progress_hooks": [hook],
                "retries": 15,            
                "fragment_retries": 15,
                "buffersize": 1024 * 1024 * 16,
                "forceipv4": True,
                "noplaylist": True,
                "continuedl": True,
                "overwrites": True,
                "nocheckcertificate": True,
                "extractor_args": {
                    # FIX: Removed the restrictive mobile player_client override here too
                    "youtube": {},
                    "instagram": {
                        "check_display_resources": True,
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": clean_url, 
                }
            }

            ydl_opts.update(get_cookie_ydl_opts(uploaded_cookie, browser_for_cookies))

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
                    ydl_opts["format"] = "best[ext=mp4]/best"
                    try:
                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(clean_url, download=True)
                    except Exception:
                        if "format" in ydl_opts:
                            del ydl_opts["format"]
                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(clean_url, download=True)

                base = os.path.splitext(ydl.prepare_filename(info))[0]
                final = None

                for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus", ".jpg", ".png"):
                    path = base + ext
                    if os.path.exists(path):
                        final = path
                        break

                if not final:
                    st.error("❌ Downloaded file not found")
                    st.stop()

                has_video_track = True
                
                if info.get('vcodec') == 'none':
                    has_video_track = False
                
                if final.endswith((".mp3", ".m4a", ".opus", ".wav")):
                    has_video_track = False

                if mode != "Audio Only (MP3)" and not has_video_track and not final.endswith((".jpg", ".png")):
                    thumbnail_url = info.get("thumbnail")
                    
                    if thumbnail_url:
                        status.text("🖼️ Rendering image & audio into video... (Takes a moment)")
                        bar.progress(85)
                        
                        thumb_path = os.path.join(tmpdir, "cover.jpg")
                        rendered_video_path = os.path.join(tmpdir, "rendered_video.mp4")
                        
                        try:
                            ctx = ssl.create_default_context()
                            ctx.check_hostname = False
                            ctx.verify_mode = ssl.CERT_NONE

                            req = urllib.request.Request(
                                thumbnail_url, 
                                headers={'User-Agent': 'Mozilla/5.0'}
                            )
                            with urllib.request.urlopen(req, context=ctx) as response, open(thumb_path, 'wb') as f:
                                f.write(response.read())
                            
                            ffmpeg_cmd = shutil.which("ffmpeg") or "ffmpeg"

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

                elif mode != "Audio Only (MP3)" and has_video_track and not final.endswith((".jpg", ".png")):
                    # A real video stream came through, but the platform may have
                    # served it in VP9/AV1 + Opus (common on slideshow-style reels),
                    # which QuickTime and some other players won't open cleanly.
                    # Only re-encode if it's actually needed.
                    final = ensure_player_compatible(final, tmpdir, status=status, bar=bar)

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
                    if cookie_source == "None":
                        st.error("🚫 Platform blocked this download. Try 'Use browser (Chrome)' above.")
                    elif browser_for_cookies:
                        st.error("⚠️ Blocked even with browser cookies. Make sure you're actually logged into that site in the selected browser, then try again.")
                    else:
                        st.error("⚠️ Cookies expired. Export a fresh cookies.txt, or switch to 'Use browser (Chrome)' instead.")
                elif "login required" in msg or "cookies" in msg:
                    if cookie_source == "None":
                        st.error("🔒 Login required. Select 'Use browser (Chrome)' above, or upload cookies.txt.")
                    else:
                        st.error("🔒 Login required — your session doesn't have access to this content (private account, age-restricted, etc.).")
                elif "rate-limit" in msg:
                    st.warning("⏳ Rate limit reached. Try later.")
                elif "requested format is not available" in msg:
                    st.error("❌ No downloadable video found. (This might be a static Image Pin or Text post).")
                elif "downloaded file is empty" in msg:
                    st.error("❌ The platform blocked the video stream chunks. Try updating your cookies or using a different link.")
                else:
                    st.error("❌ Download failed")
                    st.exception(e)

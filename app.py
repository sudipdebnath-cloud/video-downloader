import streamlit as st
import tempfile
import os
import base64
from yt_dlp import YoutubeDL
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

st.set_page_config(page_title="Video Downloader PRO", layout="centered")

st.markdown("""
<style>

/* Responsive container */
.stAppHeader {
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
st.caption("YouTube • Facebook • Instagram • X • Shorts • Reels")

# ---------------- INPUT ----------------
url = st.text_input("Paste Video URL")

uploaded_cookie = st.file_uploader(
    "Upload cookies.txt (needed for private / restricted videos)",
    type=["txt"]
)

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

    if not uploaded_file:
        return None

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp.write(uploaded_file.read())
    tmp.close()

    return tmp.name


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
                        "player_client": ["android", "web"]
                    }
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9"
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
                st.error("🔒 Login required. Upload cookies.txt.")

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
        st.image(thumbnail, use_container_width=True)

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

        choice = st.selectbox(
            "Resolution",
            list(st.session_state["formats"].keys())
        )

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

                    if speed:
                        speed_mb = speed / 1024 / 1024
                        speed_txt = f"{speed_mb:.2f} MB/s"
                    else:
                        speed_txt = "--"

                    if eta:
                        mins = eta // 60
                        secs = eta % 60
                        eta_txt = f"{mins}:{secs:02d}"
                    else:
                        eta_txt = "--:--"

                    status.text(
                        f"⬇ {percent}% • {size_txt} • ⚡ {speed_txt} • ⏳ ETA {eta_txt}"
                    )

                except:
                    pass

            elif d["status"] == "finished":

                try:
                    bar.progress(100)
                    status.text("🔄 Processing video...")
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
                        "player_client": ["android", "web"]
                    }
                },

                "http_headers": {
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9"
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

                    if mode == "Choose Resolution":

                        st.warning("⚠️ Resolution failed. Retrying Best Quality...")

                        ydl_opts["format"] = "bestvideo+bestaudio/best"

                        with YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(clean_url, download=True)

                    else:
                        raise

                base = os.path.splitext(
                    ydl.prepare_filename(info)
                )[0]

                final = None

                for ext in (".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus"):

                    path = base + ext

                    if os.path.exists(path):
                        final = path
                        break

                if not final:
                    st.error("❌ Downloaded file not found")
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
                        st.error("🚫 YouTube blocked this download. Upload cookies.txt.")
                    else:
                        st.error("⚠️ Cookies expired. Export fresh cookies.")

                elif "login required" in msg or "cookies" in msg:

                    st.error("🔒 Login required. Upload cookies.txt.")

                elif "rate-limit" in msg:

                    st.warning("⏳ Rate limit reached. Try later.")

                else:

                    st.error("❌ Download failed")
                    st.exception(e)
import os
import posixpath
import urllib.parse
import sublime
import sublime_plugin


def _norm_fs_path(p: str) -> str:
    """
    Normalize a filesystem path for reliable prefix matching across platforms.
    - Expands ~
    - Normalizes separators/case
    - Removes trailing separators
    """
    if not p:
        return ""
    p = os.path.expanduser(p)
    p = os.path.normpath(p)
    # normcase lowercases on Windows, leaves as-is on macOS/Linux
    p = os.path.normcase(p)
    return p.rstrip("\\/")


def _fs_relpath(file_path: str, base_path: str) -> str:
    """
    ST3/Python 3.3-safe relative path resolver.
    Raises ValueError if file_path is not under base_path.
    """
    file_n = _norm_fs_path(file_path)
    base_n = _norm_fs_path(base_path)

    # Boundary-safe prefix check:
    # base=C:\work\app should not match C:\work\application
    if file_n == base_n:
        return ""

    if not file_n.startswith(base_n + os.sep):
        raise ValueError("File not under base path")

    return os.path.relpath(file_n, base_n)



def _to_url_path(rel_fs_path: str) -> str:
    """
    Convert a filesystem relative path into a URL path (always forward slashes).
    """
    parts = rel_fs_path.split(os.sep)
    return "/".join(parts)


class ViewInBrowserPlusCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        if not view:
            return

        file_path = view.file_name()
        if not file_path:
            sublime.error_message("ViewInBrowserPlus: File is not saved to disk.")
            return

        settings = sublime.load_settings("ViewInBrowserPlus.sublime-settings")
        print("ViewInBrowserPlus settings:", settings.get("mappings"))
        mappings = settings.get("mappings", [])
        prefer_longest = bool(settings.get("prefer_longest_match", True))
        url_encode_path = bool(settings.get("url_encode_path", True))
        browser = (settings.get("browser") or "").strip()

        if not mappings:
            sublime.error_message("ViewInBrowserPlus: No mappings configured.")
            return

        candidates = []
        for m in mappings:
            base_path = (m.get("base_path") or "").strip()
            base_url = (m.get("base_url") or "").strip()
            if not base_path or not base_url:
                continue
            try:
                rel = _fs_relpath(file_path, base_path)
                candidates.append((base_path, base_url, rel))
            except Exception:
                pass

        if not candidates:
            sublime.error_message(
                "ViewInBrowserPlus: No mapping matched this file.\n\nFile:\n{}".format(file_path)
            )
            return

        # Choose best candidate
        if prefer_longest:
            # longest base_path wins
            candidates.sort(key=lambda t: len(_norm_fs_path(t[0])), reverse=True)

        base_path, base_url, rel = candidates[0]
        url_path = _to_url_path(rel)

        # Join base_url + url_path carefully
        # Ensure base_url has no trailing slash for consistent join
        base_url = base_url.rstrip("/")

        if url_encode_path:
            # Encode each segment so slashes remain slashes
            segments = [urllib.parse.quote(seg) for seg in url_path.split("/")]
            url_path = "/".join(segments)

        final_url = "{}/{}".format(base_url, url_path)

        # Open it
        if browser:
            self.window.run_command("open_url", {"url": final_url})
            # Note: Sublime's open_url uses OS default handler.
            # If you *must* force a browser executable, we can add an OS-specific subprocess launcher.
        else:
            self.window.run_command("open_url", {"url": final_url})

        sublime.status_message("ViewInBrowserPlus: {}".format(final_url))

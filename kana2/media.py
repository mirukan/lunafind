import logging
import os

import pybooru.resources as booruRes

import requests

from . import CLIENT, tools, utils


def media(post, chunk_size=16 * 1024 ** 2):
    check_keys = ["id", "file_url", "large_file_url", "md5"]
    if tools.has_vital_keys(post, "download media", check_keys) is False:
        return False

    post_id          = post["id"]
    media_url        = post["file_url"]
    # verify_dl_method = "md5", post["md5"]

    # If the post is an ugoira, get the associated video instead of the zip.
    # The file_ext key turns out to not be reliable for older posts.
    if post["file_ext"] == "zip":
        media_url        = post["large_file_url"]
        # verify_dl_method = "filesize", post["large_file_url"]

    # media_ext = tools.get_file_to_dl_ext(post)

    # Only media hosted on raikou(2).donmai.us will have the full URL.
    if not media_url.startswith("http"):
        media_url = "%s%s" % (CLIENT.site_url, media_url)

    logging.info("Downloading media for post %d", post_id)

    req = requests.get(media_url, stream=True, timeout=60)

    if req.status_code not in range(200, 204 + 1):
        logging.error("Failed media download for post %d: %s",
                      post_id, booruRes.HTTP_STATUS_CODE[req.status_code][0])
        # tools.move_failed_dl(post_id, media_ext, "error-%s" % req.status_code
        return False

    yield from req.iter_content(chunk_size)


def verify(file_, method):
    if not (method[0] == "md5" and
            method[1] == utils.get_file_md5(file_) or

            method[0] == "filesize" and
            method[1] == os.path.getsize(file_) or

            method[0] == "filesize" and
            requests.head(CLIENT.site_url +
                          method[1]).headers["content-length"] !=
            os.path.getsize(file_)):

        logging.error("Corrupted download, %s check failed.", method[0])

        # TODO: Have download handle this.
        # tools.move_failed_dl(post_id, file_ext, method[0] + "-mismatch")

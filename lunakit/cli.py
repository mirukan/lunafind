# Copyright 2018 miruka
# This file is part of lunakit, licensed under LGPLv3.

r"""Usage: lunakit [QUERY]... [options]

Search, filter and download posts from Danbooru-based sites.

Arguments:
  QUERY
    Tags to search for, search results URL, or post URL.
    If no queries are used, latest posts from the home page will be returned.

    As multiple queries can be used in one command,
    tag searches with multiple tags must be wrapped in quotes.

    If a query starts with a `-`, prefix it with a `%` or `\` to prevent it
    from being seen as an option, e.g. `lunakit %-rating:e`.
    For `\`, quoting will always be required to prevent the shell from
    interpreting it.

Options:
  -p PAGES, --pages PAGES
    Pages to fetch for tag searches, can be:
    - `all`
    - Direct number, e.g. `1` (the default)
    - A range with an optional step: `3-6`, `10-end`, `1-20-2` (skip 1/2 pages)
    - A comma-separated list: `1,3,5,12,99`

  -l NUM, --limit NUM
    Number of posts per page. On Danbooru, default is 20 and max is 200.

  -r, --random
    Randomize results order.

  -w, --raw
    Do not parse the query for aliased tags, metatags or multiple tags,
    send it as a single literal tag.

  -b NAME, --booru NAME
    Booru to search on (is auto-detected for URLs), must be defined in your
    configuration file. The default one uses Danbooru.


  -f TAGS, --filter TAGS
    Filter posts returned by searches,
    can be used to work around the two tags limit on Danbooru.
    Same syntax as tag searches, most metatags are supported with some
    additions and restriction lifts (to document).

    For a faster filtering, use tags that have less posts for the booru
    search and others for the filter, for example:
      `lunakit "snow wallpaper" -f "touhou 1girl" -d`
    Instead of:
      `lunakit "touhou 1girl" -f "wallpaper snow" -d`

  -o BY, --order BY
    Order posts returned by searches.
    Has to force all results to be fetched at the start and loaded in RAM.
    See `--help-order-values` to get a list of the possible `BY` values.

    Also remember this works with actually fetched results.
    The equivalent to searching "tag1 tag2 order:score" on Danbooru would be:
    `lunakit "tag1 tag2" --pages all --order score` (notice `--pages all`).


  -R RES, --resource RES
    Comma-separated list of resources for posts to print on stdout,
    e.g. `info` or `info,media,artcom,notes`.

    If no `--resource`, `--info-key` or `--download` option is specified,
    the default behavior is to print info on stdout.

  -k KEY, --info-key KEY
    Comma-separated list of info JSON keys to print for posts,
    e.g. `dl_url` or `id,tag_string`

  -d, --download
    Save posts and their resources (media, info, artcom, notes...) to disk.
    Cannot be used with `--resource` or `--info-key`.

  -q, --quiet-skip
    Do not warn when skipping download of already existing files.

  -O, --overwrite
    Do not skip downloads and overwrite files that already exist.


  -h, --help
    Show this help.

  --help-order-values
    Show possible values for `--order`.

  -V, --version
    Show the program version.

Notes:
  Pixiv ugoiras
    The converted webm seen in the browser will be downloaded,
    instead of the heavy and unplayable zip files normally provided by the API.

  Additional info keys
    The info returned for posts contains keys generated by lunakit and not
    present in the standard Danbooru API post JSONs.
    Examples include `dl_url`, `dl_ext` and `dl_size`, which are about the
    image or ugoira webm that should be downloaded.

Examples:
  lunakit "blonde 2girls" --download
    Download the first page of posts containing tags `blonde` and `2girls`.

  lunakit --random --limit 200 --key dl_url
    Print raw image/webm URL for 200 random posts.

  lunakit "wallpaper order:score" --filter "%-no_human ratio:16:9 width:>=1920"
    Search for posts with the `wallpaper` tags sorted by score,
    filter posts to only leave those without the `no_human` tag, with a ratio
    of 16:9 and a width equal or superior to 1920, print info.

    Since the filter value starts with a `-`, it is escaped with a `%` to not
    be mistaken for an option. `\` can also be used, but will most likely
    always require quoting due to your shell.

  lunakit "~scenery ~landscape" "~outdoor ~nature" --pages all --download
    Do two separate searches (Danbooru 2 tag limit) for "scenery or landscape"
    and "outdoor or nature", all pages, combine the results and
    download everything."""

import re
import sys
from typing import List, Optional

import blessed
import docopt

from . import Album, Stream, __about__, clients, order, utils

TERM    = blessed.Terminal()
OPTIONS = [string for match in re.findall(r"(-.)(?:\s|,)|(--.+?)\s", __doc__)
           for string in match if string]


def print_help(doc: str = __doc__, exit_code: int = 0) -> None:
    doc = doc.splitlines()

    # Usage:
    doc[0] = re.sub(r"(Usage: +)",
                    f"%s{TERM.blue}" % TERM.magenta_bold(r"\1"), doc[0])
    # [things]
    doc[0] = re.sub(r"\[(\S+)\]",
                    f"[%s{TERM.blue}]" % TERM.bold(rf"\1"), doc[0])

    doc[0] = f"{doc[0]}{TERM.normal}"
    doc    = "\n".join(doc)

    styles = {
        r"`(.+?)`":      "green",         # `things`
        r"^(\S.+:)$":    "magenta_bold",  #  Sections:
        r"^(  [A-Z]+)$": "blue_bold",     #  ARGUMENT
        r"^(  \S.+)$":   "blue",          #  Two-space indented lines
        r"^(\s*-)":      "magenta",       #  - Dash lists
    }

    for reg, style in styles.items():
        doc = re.sub(reg, getattr(TERM, style)(r"\1"), doc, flags=re.MULTILINE)

    doc = re.sub(r"(-{1,2}[a-zA-Z\d]+ +)([A-Z]+)",
                 r"\1%s%s%s" % (TERM.blue_bold(r"\2"), TERM.normal, TERM.blue),
                 doc)

    print(doc)
    sys.exit(exit_code)


def print_order_values() -> None:
    dicts     = {**order.ORDER_NUM, **order.ORDER_DATE, **order.ORDER_FUNCS}
    by_maxlen = len(max(dicts.keys(), key=len))

    for di in (order.ORDER_NUM, order.ORDER_DATE):
        print(f"{'Value':{by_maxlen}}   Default sort")

        for by, (asc_or_desc, _) in di.items():
            print(f"{by:{by_maxlen}}  {asc_or_desc}ending")

        print()

    print("For values above, the sort order can be manually specified by "
          "prefixing the value with 'asc_' or 'desc_', e.g. 'asc_score'.\n")

    for by in order.ORDER_FUNCS:
        print(by)

    sys.exit(0)


def main(argv: Optional[List[str]] = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]

    try:
        args = docopt.docopt(
            __doc__, help=False, argv=argv, version=__about__.__version__
        )
    except docopt.DocoptExit:
        if len(sys.argv) > 1:
            print("Invalid command syntax, check help:\n")

        print_help(exit_code=10)

    if args["--help-order-values"]:
        print_order_values()

    if args["--help"]:
        print_help()

    params = {
        "pages":  args["--pages"],
        "random": args["--random"],
        "raw":    args["--raw"],
    }

    params = {k: v for k, v in params.items() if v is not None}

    if args["--limit"]:
        params["limit"] = int(args["--limit"])

    if args["--booru"]:
        params["prefer"] = clients.ALIVE[args["--booru"]]

    unesc = lambda s: s[1:] if s.startswith(r"\-") or s.startswith("%-") else s

    stores = [Stream(unesc(q), **params).filter(unesc(args["--filter"] or ""))
              for q in args["QUERY"] or [""]]

    if args["--order"]:
        stores = [Album(stores[0]).put(*stores[1:]).order(args["--order"])]


    for obj in stores:
        posts = obj.list if isinstance(obj, Album) else obj

        if not(args["--resource"] or args["--info-key"] or args["--download"]):
            args["--resource"] = "info"

        if args["--download"]:
            posts.write(overwrite = args["--overwrite"],
                        warn      = not args["--quiet-skip"])
            return

        for post in posts:
            if args["--info-key"]:
                for key in args["--info-key"].split(","):
                    print(post["info"][key])

            if args["--resource"]:
                for res in args["--resource"].split(","):
                    json = utils.prettify_json(post[res].get_serialized())
                    if json:
                        print(json)

            if args["--info-key"] or args["--resource"]:
                print()
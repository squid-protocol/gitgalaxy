# Blog posts

One Markdown file per post. The file name (without `.md`) becomes the URL: `my-post.md` is `https://gitgalaxy.io/blog/my-post/`.

```
---
title: A short, specific title
date: 2026-11-21
description: One or two sentences. Shown in the blog list, search results and link previews.
---

Body in Markdown. Fenced code, tables and images work.
```

Optional front matter: `slug` (override the URL), `draft: true` (built nowhere until removed), `canonical` (set this
if the post also lives somewhere else, so search engines credit one copy).

After adding or editing a post, run `python site/tools/build_blog.py` and commit the generated files
(`site/blog/`, `site/sitemap.xml`). Files starting with `_` and this README are ignored.

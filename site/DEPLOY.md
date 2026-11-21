# Deploying gitgalaxy.io

**Read this before pulling.** The server serves `/var/www/gitgalaxy/site`, a git checkout of this repo. It is hand-deployed
(no CI) and was left on an old commit for months, so a plain `git pull` ships *every* `site/` change since then,
including viewer code nobody has tested on the live box. Always diff first.

Facts about the server (verified 2026-11-20): nginx only, no Flask process (`app.py` is not live), Ubuntu 24.04,
root `/var/www/gitgalaxy/site`, galaxy data in `/var/www/gitgalaxy_data` served at `/data/` and `/museum/`.
Access: `ssh gitgalaxy-io` (key only).

## 1. Back up and look before changing

    ssh gitgalaxy-io 'cd /var/www/gitgalaxy && git fetch origin main && git diff --stat HEAD origin/main -- site | tail -20'
    ssh gitgalaxy-io 'tar czf /root/backups/site-$(date +%F).tgz -C /var/www/gitgalaxy site /etc/nginx/sites-available/gitgalaxy'

## 2. Site files

Either pull (after reading the diff above) or copy only what you reviewed:

    ssh gitgalaxy-io 'cd /var/www/gitgalaxy && git pull --ff-only origin main'

Rollback: `git checkout <old-commit> -- site` in that directory.

## 3. nginx: compression, headers, caching

    scp site/deploy/nginx/conf.d/gitgalaxy-gzip.conf gitgalaxy-io:/etc/nginx/conf.d/
    scp site/deploy/nginx/snippets/gitgalaxy-security-headers.conf gitgalaxy-io:/etc/nginx/snippets/

Then edit `/etc/nginx/sites-available/gitgalaxy` (keep every line Certbot manages):

1. In the `server { ... }` block that has `listen 443 ssl;` add, next to `index index.html;`:

       include snippets/gitgalaxy-security-headers.conf;
       location = /index.html { include snippets/gitgalaxy-security-headers.conf; add_header Cache-Control "no-cache" always; }
       location ~* \.(?:js|css)$ { include snippets/gitgalaxy-security-headers.conf; add_header Cache-Control "public, max-age=600, must-revalidate" always; }

2. In `location /data/` and `location /museum/` add `include snippets/gitgalaxy-security-headers.conf;`, and in `/data/` also:

       gzip_static on;
       add_header Cache-Control "public, max-age=86400" always;

3. Remove `location = /api/list_galaxies` and `location /backend/`: both point at the broken `site/data` link and nothing uses them.

Check, then reload (a reload never drops connections; a failed `-t` leaves the running config alone):

    ssh gitgalaxy-io 'nginx -t && systemctl reload nginx'
    curl -sI https://gitgalaxy.io/ | grep -iE 'strict-transport|x-content|x-frame|referrer|permissions|content-security'

Rollback: restore `/etc/nginx/sites-available/gitgalaxy` from the tarball and reload.

## 4. Refreshed galaxy data

Built on a workstation with the engine at a recorded commit, not on the server. A bundle contains, per galaxy,
`<id>_galaxy.json`, `<id>_galaxy_llm.md`, an audit file when it is 100 MB or smaller, and a pre-compressed `.gz` twin of
each (served by `gzip_static`). It also has `manifest.json`, `PROVENANCE.json` (source repo and commit, scan date and
engine commit for every galaxy) and `SHA256SUMS`. Audits over 100 MB are left out on purpose and their manifest entry
has an empty `auditUrl`, so the viewer shows the button as unavailable instead of linking to a 404.

**Ship the viewer first (or together).** Data from the current engine needs the constellation fix in this PR; the old
April viewer throws when you click a star in constellation mode on it.

    rsync -a --info=progress2 <bundle>/ gitgalaxy-io:/var/www/gitgalaxy_data.new/
    ssh gitgalaxy-io 'cd /var/www/gitgalaxy_data.new && sha256sum -c SHA256SUMS --quiet && echo checksums ok'
    ssh gitgalaxy-io 'cd /var/www && mv gitgalaxy_data gitgalaxy_data.bak-$(date +%F) && mv gitgalaxy_data.new gitgalaxy_data'

Rollback: swap the two directory names back. Delete the `.bak-*` directory only after the new data has been live a few days.
Check afterwards: `curl -s https://gitgalaxy.io/data/manifest.json | head`, then open a galaxy and click a star in
constellation mode.

## 5. Blog

`python site/tools/build_blog.py` regenerates `site/blog/`, `site/sitemap.xml` and `site/robots.txt` from
`site/blog/posts/*.md`. Commit the output; the server needs no build step. See `site/blog/posts/README.md`.

After the first deploy: submit `https://gitgalaxy.io/sitemap.xml` in Search Console (a Domain or URL-prefix property for
`https://gitgalaxy.io/`, verified by a DNS TXT record).

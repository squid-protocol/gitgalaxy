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

## 3. nginx: compression, headers, caching, blocked paths

The server config as deployed on 2026-11-21 is in `site/deploy/nginx/sites-available/gitgalaxy.conf` (a reference copy;
the Certbot lines are managed on the server). To reproduce it on a new box:

    scp site/deploy/nginx/conf.d/gitgalaxy-gzip.conf gitgalaxy-io:/etc/nginx/conf.d/
    scp site/deploy/nginx/snippets/gitgalaxy-security-headers.conf gitgalaxy-io:/etc/nginx/snippets/

Then edit `/etc/nginx/sites-available/gitgalaxy`, keeping every Certbot line, so that it matches the reference copy:

- the headers snippet is included at server level and again inside every location that sets its own `add_header`
  (nginx does not inherit `add_header` into a location that has one);
- `/data/` and `/museum/` get `gzip_static on;` and a one-day `Cache-Control`;
- these are blocked with 404 because nginx serves everything under the web root: dotfiles (except `/.well-known/`),
  `*.py`, `/deploy/`, `/blog/posts/` (blog drafts) and `/DEPLOY.md`;
- the old `/api/list_galaxies` and `/backend/` blocks are gone (they pointed at a broken link).

Test and reload with an automatic way back (a failed `-t` leaves the running config alone, so always test first):

    ssh gitgalaxy-io 'N=/etc/nginx/sites-available/gitgalaxy; cp -p $N $N.bak && cp $N.new $N && nginx -t && systemctl reload nginx || { cp -p $N.bak $N; echo reverted; }'
    curl -sI https://gitgalaxy.io/ | grep -iE 'strict-transport|x-content|x-frame|referrer|permissions|content-security'

The content-security-policy is **report-only**. After a week of clean visits, rename the header to
`Content-Security-Policy` in the snippet to enforce it.

Rollback: restore `/etc/nginx/sites-available/gitgalaxy.bak` (or the tarball from step 1) and reload.

## 4. Refreshed galaxy data

Built on a workstation with the engine at a recorded commit, not on the server. A bundle contains, per galaxy,
`<id>_galaxy.json`, `<id>_galaxy_llm.md`, an audit file when it is 100 MB or smaller, and a pre-compressed `.gz` twin of
each (served by `gzip_static`). It also has `manifest.json`, `PROVENANCE.json` (source repo and commit, scan date and
engine commit for every galaxy) and `SHA256SUMS`. Audits over 100 MB are left out on purpose and their manifest entry
has an empty `auditUrl`, so the viewer shows the button as unavailable instead of linking to a 404.

**Ship the viewer first (or together).** Data from the current engine needs the constellation fix (PR 8803); the old
April viewer throws when you click a star in constellation mode on it.

**Merge into the data directory, do not swap it.** `/var/www/gitgalaxy_data` also holds galaxies that are not in the
manifest (bun, cpython, AppFlowy, ...) which other pages may link to; replacing the directory would remove them.
Upload everything except the manifest first, check the checksums, then upload the manifest last, so visitors never see a
manifest that points at files that have not arrived. Replaced files go to a backup directory. Use `-z`: the JSON
compresses about 16x and an uncompressed upload crawls on a home connection.

    B=/path/to/bundle; D=/var/www/gitgalaxy_data
    rsync -az --partial --chown=www-data:www-data --backup --backup-dir=$D.bak-$(date +%F) --exclude manifest.json -e ssh $B/ gitgalaxy-io:$D/
    ssh gitgalaxy-io "cd $D && grep -v '  manifest.json\$' SHA256SUMS | sha256sum -c --quiet && echo checksums ok"
    rsync -a --chown=www-data:www-data --backup --backup-dir=$D.bak-$(date +%F) -e ssh $B/manifest.json gitgalaxy-io:$D/

Rollback: `cp -a $D.bak-<date>/. $D/` puts the replaced files back (the old manifest included); delete the backup only after
the new data has been live a few days. Check afterwards: `curl -s https://gitgalaxy.io/data/manifest.json | head`, then open
a galaxy and click a star in constellation mode.

The server limits new SSH connections (ufw `limit`): do not poll it with many short `ssh` calls, or it will refuse you
for a while. One connection that does several things is better.

## 5. Blog

`python site/tools/build_blog.py` regenerates `site/blog/`, `site/sitemap.xml` and `site/robots.txt` from
`site/blog/posts/*.md`. Commit the output; the server needs no build step. See `site/blog/posts/README.md`.

After the first deploy: submit `https://gitgalaxy.io/sitemap.xml` in Search Console (a Domain or URL-prefix property for
`https://gitgalaxy.io/`, verified by a DNS TXT record).

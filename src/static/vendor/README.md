# Vendored browser libraries

These files are served locally; pages do not request JavaScript from a CDN.

| Library | Version | File | Upstream |
| --- | --- | --- | --- |
| Marked | 18.1.1 | `marked-18.1.1.umd.js` | https://github.com/markedjs/marked |
| DOMPurify | 3.4.17 | `purify-3.4.17.min.js` | https://github.com/cure53/DOMPurify |

The files were copied unmodified from the corresponding npm release archives after
verifying each archive's SHA-512 integrity against its npm metadata. License files
are included alongside the scripts.

To update, download a specific release from the official npm registry, verify its
integrity, replace its browser bundle and license, and update the filenames in
`index.html`, `blog.html`, `projects.html`, `post.html`, and the browser test. Run the
Markdown browser tests after updating either library.

# JMBlog v0.1:

This was made for my own personal use but for whatever reason you'd like to reuse the codebase, you can go right ahead.

This locally hosted web application allows for a showcase of your talents, thought process and skills through a blogging medium.

- You are able to execute CRUD (Create, Read, Update, Delete) operations on blog / project posts through parsed CLI options.
- Uses SQLite3 to store *.md files to later fetch and serve to visiting users. 
- Uses a FASTAPI backend to respond and recieve requests, with Uvicorn to broadcast to the local network.
- Expects markdown syntax to render.

This includes a basic full vanilla frontend and Python backend, including fully functional pages such as:
Home, Blog, Projects, Contact

The pages are available at `/home`, `/blog`, `/projects`, and `/contact`; the original `.html` URLs still work. The home page shows the three newest posts and projects. Entries whose topic name is `project` (ignoring case and surrounding spaces) appear in Projects; all other topics appear in Blog.

To change a post's timestamp, pass its topic ID, post ID, and a date in `MM/DD/YYYY` (Month/Day/Year) order:

```powershell
python -m public.app.main post-timestamp 1 42 11/03/2026
```

Both IDs must be positive integers, and the post must belong to the specified topic. Dates require two-digit months and days, a four-digit year, and a valid calendar date (including leap-year checks). The date is interpreted as midnight in `America/New_York`, matching the website's date display, and converted to UTC for storage in SQLite's existing `YYYY-MM-DD HH:MM:SS` format. For example, `11/03/2026` is stored as `2026-11-03 05:00:00`. This preserves datetime parsing, API serialization, and chronological sorting. Install `requirements.txt` to include the timezone data needed on Windows.

Each entry uses its description, or a plain-text Markdown summary when no description is set. The first image in the Markdown content becomes its thumbnail. An empty image slot stays in place for entries without an image. The light/dark toggle shares the article template's saved theme preference across pages.









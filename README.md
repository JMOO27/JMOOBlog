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

Each entry uses its description, or a plain-text Markdown summary when no description is set. The first image in the Markdown content becomes its thumbnail. An empty image slot stays in place for entries without an image. The light/dark toggle shares the article template's saved theme preference across pages.









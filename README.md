# JMBlog v0.1:

This was made for my own personal use but for whatever reason you'd like to reuse the codebase, you can go right ahead.

This locally hosted web application allows for a showcase of your talents, thought process and skills through a blogging medium.

- You are able to execute CRUD (Create, Read, Update, Delete) operations on blog / project posts through parsed CLI options.
- Uses SQLite3 to store *.md files to later fetch and serve to visiting users. 
- Uses a FASTAPI backend to respond and recieve requests, with Uvicorn to broadcast to the local network.
- Expects markdown syntax to render.

This includes a basic full vanilla frontend and Python backend, including fully functional pages such as:
Home, Blog, Projects, Contact

# Usage
Note: If using a container, augment your path with /app/posts/{actual_file_path}

## Creating a topic:
This accepts text. Do note, this will be used to render tags on your page.

When the topic is created, it will automatically be assigned to a value in the DB, which can be referenced to refer to your specific topic. 

```python -m public.app.main create {topic_title}```

## Modifying a topic title: 
```python -m public.app.main topic-modify {topic_id) {title}```

## Deleting a topic: 
Note: This will delete all posts that relate with a topic. \
```python -m public.app.main delete {topic_id)```

## Creating a blog post: 
To create a blog post, make sure to have created a topic first, as each post is related to a topic. \
Any file submitted in the file path must end with .md! \
```python -m public.app.main create "{file_path}" --topic ID```

## Modifying/Updating a Blog Post: 
Essentially this replaces the entire file within the database. Make sure when committing this operation you are overwriting something you don't intend on getting back. \
```python -m public.app.main create {post_id} {file_path}```

## Deleting a Post:
```python -m public.app.main create {post_id}```

## Modify/Update a Timestamp:
```python -m public.app.main create {topic_id} {post_id} MM/DD/YYYY```

## View All Posts:
```python -m public.app.main create posts```

## View All Topics:
```python -m public.app.main create topics```









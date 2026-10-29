// API entries use BlogEntry directly: blog_id, blog_type, title, content, timestamp.
// Titles and summaries use textContent. Markdown bodies are sanitized before insertion.
const entryTemplate = document.createElement('template');
entryTemplate.innerHTML = `
    <article class="entry">
        <p class="entry-meta">
            <span data-entry-label></span><span aria-hidden="true">&middot;</span>
            <time></time>
        </p>
        <div class="entry-heading">
            <h3><a></a></h3>
            <a class="entry-view" data-entry-view-link>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/>
                    <circle cx="12" cy="12" r="3"/>
                </svg>
            </a>
        </div>
    </article>`;

const entryDate = new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York'
});
const entryTimestamp = new Intl.DateTimeFormat('en-US', {
    dateStyle: 'long', timeStyle: 'long', timeZone: 'America/New_York'
});

function renderMarkdown(content) {
    return DOMPurify.sanitize(marked.parse(content, { gfm: true, async: false }), {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ['style'],
        FORBID_ATTR: ['style'],
        RETURN_DOM_FRAGMENT: true
    });
}

function preview(content) {
    const fragment = renderMarkdown(content);
    // Detached fragments avoid loading images while deriving plain-text summaries.
    fragment.querySelectorAll('img').forEach(image => image.replaceWith(
        document.createTextNode(image.alt)
    ));
    fragment.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, pre, blockquote, td, th, br')
        .forEach(element => element.append(document.createTextNode(' ')));
    const text = fragment.textContent.replace(/\s+/g, ' ').trim();
    return text.length > 200 ? `${text.slice(0, 200).trimEnd()}…` : text;
}

function fillTime(time, timestamp) {
    const date = new Date(timestamp);
    time.dateTime = timestamp;
    time.textContent = entryDate.format(date);
    time.title = entryTimestamp.format(date);
}

function appendContent(container, content) {
    const body = document.createElement('div');
    body.className = 'markdown-body';
    body.append(renderMarkdown(content));
    // Keyboard readers can scroll long code blocks and tables independently.
    body.querySelectorAll('pre').forEach(block => {
        block.tabIndex = 0;
        block.setAttribute('aria-label', 'Code block');
    });
    body.querySelectorAll('table').forEach(table => {
        const wrapper = document.createElement('div');
        wrapper.className = 'markdown-table';
        wrapper.tabIndex = 0;
        wrapper.setAttribute('role', 'region');
        wrapper.setAttribute('aria-label', 'Table');
        table.replaceWith(wrapper);
        wrapper.append(table);
    });
    container.append(body);
}

function renderEntry(entry, full = false) {
    const article = entryTemplate.content.firstElementChild.cloneNode(true);
    const isProject = entry.blog_type === 'project';
    const link = article.querySelector('h3 a');
    link.href = isProject ? `/projects.html#project-${entry.blog_id}` : `/post.html?id=${entry.blog_id}`;
    link.textContent = entry.title;
    const viewLink = article.querySelector('[data-entry-view-link]');
    if (isProject) {
        viewLink.remove();
    } else {
        viewLink.href = link.href;
        viewLink.setAttribute('aria-label', `Read ${entry.title}`);
        viewLink.title = `Read ${entry.title}`;
    }
    if (isProject) {
        article.querySelector('[data-entry-label]').textContent = 'Project';
    } else {
        article.querySelector('.entry-meta').replaceChildren(article.querySelector('time'));
    }
    fillTime(article.querySelector('time'), entry.timestamp);

    if (full) {
        article.id = `project-${entry.blog_id}`;
        article.querySelector('h3').textContent = entry.title;
        appendContent(article, entry.content);
    } else {
        const paragraph = document.createElement('p');
        paragraph.textContent = preview(entry.content);
        article.append(paragraph);
    }
    return article;
}

function showMessage(container, message, error = false) {
    const paragraph = document.createElement('p');
    paragraph.className = 'entry-status';
    paragraph.setAttribute('role', error ? 'alert' : 'status');
    paragraph.textContent = message;
    container.replaceChildren(paragraph);
}

async function fetchJSON(url) {
    const response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
        const error = new Error(`Request failed: ${response.status}`);
        error.status = response.status;
        throw error;
    }
    return response.json();
}

// Reuse each list request when a column and the latest panel need the same data.
const entryRequests = new Map();
function fetchEntries(type) {
    if (!entryRequests.has(type)) {
        entryRequests.set(type, fetchJSON(`/api/entries?type=${encodeURIComponent(type)}`));
    }
    return entryRequests.get(type);
}

async function loadList(list) {
    const type = list.dataset.entryList;
    showMessage(list, `Loading ${type === 'project' ? 'projects' : 'posts'}…`);
    try {
        const entries = await fetchEntries(type);
        if (!entries.length) {
            showMessage(list, type === 'project' ? 'No projects yet.' : 'No blog posts yet.');
            return;
        }
        list.replaceChildren(...entries.map(entry => renderEntry(entry, list.dataset.entryView === 'full')));
        // Project bodies arrive after the browser's initial fragment lookup.
        const target = document.getElementById(window.location.hash.slice(1));
        if (target && list.contains(target)) requestAnimationFrame(() => target.scrollIntoView());
    } catch {
        showMessage(list, 'Could not load entries. Please refresh to try again.', true);
    }
}

async function loadLatest(panel) {
    showMessage(panel, 'Loading latest entry…');
    try {
        const groups = await Promise.all([fetchEntries('blog'), fetchEntries('project')]);
        const latest = groups.flat().sort((a, b) =>
            Date.parse(b.timestamp) - Date.parse(a.timestamp) || b.blog_id - a.blog_id
        )[0];
        if (latest) panel.replaceChildren(renderEntry(latest));
        else showMessage(panel, 'No entries yet.');
    } catch {
        showMessage(panel, 'Could not load the latest entry. Please refresh to try again.', true);
    }
}

async function loadArticle(article) {
    const status = document.querySelector('[data-article-status]');
    const title = document.querySelector('#post-title');
    const id = new URLSearchParams(window.location.search).get('id');
    if (!id || !/^[1-9]\d*$/.test(id)) {
        title.textContent = 'Entry not found';
        showMessage(status, 'Choose an entry from the blog or projects page.');
        return;
    }
    showMessage(status, 'Loading entry…');
    try {
        const entry = await fetchJSON(`/api/entries/${id}`);
        const isProject = entry.blog_type === 'project';
        title.textContent = entry.title;
        document.title = `${entry.title} | jmoo.dev`;
        document.querySelector('meta[name="description"]').content = preview(entry.content);
        article.querySelector('[data-entry-label]').textContent = isProject ? 'Project' : 'Blog post';
        fillTime(article.querySelector('time'), entry.timestamp);
        appendContent(article.querySelector('.post-body'), entry.content);
        const back = document.querySelector('[data-article-back]');
        back.href = isProject ? '/projects.html' : '/blog.html';
        back.textContent = isProject ? '← All projects' : '← All posts';
        document.querySelectorAll('.nav-link[aria-current]').forEach(link => link.removeAttribute('aria-current'));
        document.querySelector(`.nav-link[data-page="${isProject ? 'projects' : 'blog'}"]`).setAttribute('aria-current', 'page');
        article.hidden = false;
        status.replaceChildren();
    } catch (error) {
        title.textContent = error.status === 404 ? 'Entry not found' : 'Could not load entry';
        showMessage(status, error.status === 404
            ? 'This entry may have been removed. Browse the blog or projects for more.'
            : 'Please refresh to try again.', true);
    }
}

document.querySelectorAll('[data-entry-list]').forEach(loadList);
document.querySelectorAll('[data-latest-entry]').forEach(loadLatest);
document.querySelectorAll('[data-entry-article]').forEach(loadArticle);

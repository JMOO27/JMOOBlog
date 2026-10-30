// Post details include the related topic, description, and UTC timestamp.
// Titles and summaries use textContent. Markdown bodies are sanitized before insertion.
const entryTemplate = document.createElement('template');
entryTemplate.innerHTML = `
    <article class="entry">
        <div class="entry-copy">
            <p class="entry-meta"><time></time></p>
            <h3><a></a></h3>
            <p class="entry-summary"></p>
            <div class="entry-tags"><span class="topic-tag"></span></div>
        </div>
        <a class="entry-media"></a>
    </article>`;

const entryDate = new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', timeZone: 'America/New_York'
});
const entryTimestamp = new Intl.DateTimeFormat('en-US', {
    dateStyle: 'long', timeStyle: 'long', timeZone: 'America/New_York'
});
const articleDate = new Intl.DateTimeFormat('en-US', {
    month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/New_York'
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

function previewImageURL(content) {
    const source = renderMarkdown(content).querySelector('img')?.getAttribute('src');
    if (!source) return null;
    try {
        const url = new URL(source, window.location.href);
        if (['http:', 'https:'].includes(url.protocol) || /^data:image\/(png|jpeg|gif|webp|avif);/i.test(source)) {
            return url.href;
        }
    } catch {
        // Malformed image URLs leave the reserved space intact.
    }
    return null;
}

function renderEntry(entry) {
    const article = entryTemplate.content.firstElementChild.cloneNode(true);
    const link = article.querySelector('h3 a');
    link.href = `/post.html?id=${entry.id}`;
    link.textContent = entry.title;
    fillTime(article.querySelector('time'), entry.timestamp);
    article.querySelector('.entry-summary').textContent = entry.description?.trim() || preview(entry.content);
    article.querySelector('.topic-tag').textContent = entry.topic.title;

    // Use the first sanitized Markdown image; every entry keeps its media slot.
    const media = article.querySelector('.entry-media');
    media.href = link.href;
    media.setAttribute('aria-label', `Read ${entry.title}`);
    const source = previewImageURL(entry.content);
    if (source) {
        const image = document.createElement('img');
        image.alt = '';
        image.loading = 'lazy';
        image.decoding = 'async';
        image.addEventListener('error', () => image.remove(), { once: true });
        image.src = source;
        media.append(image);
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

// Reuse requests when multiple lists need the same topic group.
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
        const visible = list.dataset.entryLimit ? entries.slice(0, Number(list.dataset.entryLimit)) : entries;
        list.replaceChildren(...visible.map(entry => renderEntry(entry)));
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
        document.title = 'Post not found | jmoo.dev';
        showMessage(status, 'Post not found. Choose a post from the blog page.', true);
        return;
    }
    showMessage(status, 'Loading post…');
    try {
        const entry = await fetchJSON(`/api/entries/${id}`);
        title.textContent = entry.title;
        document.title = `${entry.title} | jmoo.dev`;
        const description = article.querySelector('[data-post-description]');
        const hasDescription = Boolean(entry.description?.trim());
        description.textContent = hasDescription ? entry.description : '';
        description.hidden = !hasDescription;
        document.querySelector('meta[name="description"]').content = hasDescription
            ? entry.description : preview(entry.content);
        article.querySelector('[data-post-topic]').textContent = entry.topic.title;
        const isProject = entry.topic.title.trim().toLowerCase() === 'project';
        const backLabel = isProject ? 'All projects' : 'All posts';
        const backPath = isProject ? '/projects' : '/blog';
        const back = document.querySelector('[data-article-back]');
        back.href = backPath;
        back.lastChild.textContent = ` ${backLabel}`;
        const endLink = article.querySelector('.post-end a');
        endLink.href = backPath;
        endLink.textContent = `\u2190 ${backLabel}`;
        const date = article.querySelector('[data-post-date]');
        fillTime(date, entry.timestamp);
        date.textContent = articleDate.format(new Date(entry.timestamp));
        appendContent(article.querySelector('.post-body'), entry.content);
        // Share the canonical post URL, without unrelated query parameters or fragments.
        const postURL = new URL('/post.html', window.location.origin);
        postURL.searchParams.set('id', String(entry.id));
        article.querySelector('[data-post-email]').href =
            `mailto:?subject=${encodeURIComponent(entry.title)}&body=${encodeURIComponent(postURL.href)}`;
        const copyLink = article.querySelector('[data-copy-post-link]');
        const feedback = article.querySelector('[data-copy-feedback]');
        copyLink.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(postURL.href);
                feedback.textContent = 'Link copied';
            } catch {
                // A selectable URL still makes sharing usable without clipboard access.
                feedback.replaceChildren();
                const link = document.createElement('a');
                link.href = postURL.href;
                link.textContent = postURL.href;
                link.className = 'copy-fallback';
                feedback.append('Copy this link: ', link);
            }
        });
        article.hidden = false;
        status.replaceChildren();
    } catch (error) {
        document.title = error.status === 404 ? 'Post not found | jmoo.dev' : 'Could not load post | jmoo.dev';
        showMessage(status, error.status === 404
            ? 'This entry may have been removed. Browse the blog or projects for more.'
            : 'Please refresh to try again.', true);
    }
}

document.querySelectorAll('[data-entry-list]').forEach(loadList);
document.querySelectorAll('[data-latest-entry]').forEach(loadLatest);
document.querySelectorAll('[data-entry-article]').forEach(loadArticle);

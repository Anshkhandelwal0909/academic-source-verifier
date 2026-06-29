// Tab Switching
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active-view'));
        
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active-view');
    });
});

// DIRECT SEARCH LOGIC
const queryInput = document.getElementById('query-input');
const searchBtn = document.getElementById('search-btn');
const loading = document.getElementById('loading');
const errorDiv = document.getElementById('error');
const resultsContainer = document.getElementById('results-container');
const resultsList = document.getElementById('results-list');
const resultsCount = document.getElementById('results-count');
const template = document.getElementById('result-template');

async function performSearch(query) {
    if (!query.trim()) return;

    // Reset UI
    errorDiv.classList.add('hidden');
    resultsContainer.classList.add('hidden');
    resultsList.innerHTML = '';
    loading.classList.remove('hidden');

    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || 'Failed to fetch results');
        }

        renderResults(data.results, data.warnings);
    } catch (err) {
        errorDiv.textContent = err.message;
        errorDiv.classList.remove('hidden');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderResults(results, warnings) {
    resultsCount.textContent = `${results.length} found`;
    resultsContainer.classList.remove('hidden');

    if (warnings && warnings.length > 0) {
        const warningBox = document.createElement('div');
        warningBox.style.background = 'rgba(245, 158, 11, 0.1)';
        warningBox.style.color = '#fbbf24';
        warningBox.style.padding = '12px';
        warningBox.style.borderRadius = '8px';
        warningBox.style.marginBottom = '16px';
        warningBox.style.fontSize = '0.9rem';
        warningBox.innerHTML = '<strong>Notices:</strong><br>' + warnings.join('<br>');
        resultsList.appendChild(warningBox);
    }

    if (results.length === 0) {
        resultsList.innerHTML += '<p style="color: #94a3b8; text-align: center; padding: 20px;">No academic sources found.</p>';
        return;
    }

    results.forEach(res => {
        const clone = template.content.cloneNode(true);
        
        clone.querySelector('.title').textContent = res.title;
        clone.querySelector('.authors').textContent = res.authors || 'Unknown Authors';
        clone.querySelector('.year').textContent = res.year || 'n.d.';
        clone.querySelector('.venue').textContent = res.venue || 'Unknown Venue';
        clone.querySelector('.citation-count').textContent = res.citation_count;
        
        if (res.abstract) {
            clone.querySelector('.abstract').textContent = res.abstract;
        } else {
            clone.querySelector('.abstract').style.display = 'none';
        }

        const citationEl = clone.querySelector('.citation-text');
        citationEl.textContent = res.citation_string;

        const urlEl = clone.querySelector('.url-link');
        if (res.url) {
            urlEl.href = res.url;
        } else {
            urlEl.style.display = 'none';
        }

        const tierBadge = clone.querySelector('.tier-badge');
        tierBadge.textContent = `Tier ${res.tier}`;
        tierBadge.classList.add(`tier-${res.tier}`);

        clone.querySelector('.source-api-badge').textContent = res.source_api;

        resultsList.appendChild(clone);
    });
}

searchBtn.addEventListener('click', () => performSearch(queryInput.value));
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performSearch(queryInput.value);
});

// DOCUMENT UPLOAD LOGIC
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const docLoading = document.getElementById('doc-loading');
const docProgressContainer = document.getElementById('doc-progress-container');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const annotatedDocument = document.getElementById('annotated-document');
const docLineTemplate = document.getElementById('doc-line-template');

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = 'var(--primary)';
});

uploadZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = 'var(--card-border)';
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.style.borderColor = 'var(--card-border)';
    if (e.dataTransfer.files.length) {
        handleFileUpload(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleFileUpload(e.target.files[0]);
    }
});

async function handleFileUpload(file) {
    if (!file.name.endsWith('.txt') && !file.name.endsWith('.pdf')) {
        alert("Only .txt and .pdf files are supported.");
        return;
    }

    uploadZone.classList.add('hidden');
    docLoading.classList.remove('hidden');
    annotatedDocument.innerHTML = '';
    annotatedDocument.classList.add('hidden');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/document/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) throw new Error(data.detail || 'Upload failed');
        
        docLoading.classList.add('hidden');
        docProgressContainer.classList.remove('hidden');
        annotatedDocument.classList.remove('hidden');
        
        startSSEStream(data.job_id);

    } catch (err) {
        alert(err.message);
        uploadZone.classList.remove('hidden');
        docLoading.classList.add('hidden');
    }
}

function startSSEStream(jobId) {
    const eventSource = new EventSource(`/api/document/stream/${jobId}`);
    
    // Map to keep track of rendered lines
    const renderedLines = new Map();

    eventSource.onmessage = function(event) {
        const payload = JSON.parse(event.data);
        
        if (payload.error) {
            console.error("SSE Error:", payload.error);
            eventSource.close();
            return;
        }
        
        if (payload.type === 'job_complete') {
            eventSource.close();
            progressText.textContent = "Processing Complete";
            return;
        }

        if (payload.type === 'parsing') {
            progressText.textContent = "Parsing document...";
            return;
        }

        const data = payload.data;
        const progress = payload.progress;
        const total = payload.total;

        // Update progress bar
        const pct = Math.round((progress / total) * 100);
        progressFill.style.width = `${pct}%`;
        progressText.textContent = `Processing: ${progress} / ${total} lines (${pct}%)`;

        // Render line
        const lineIdx = data.line_index;
        let lineEl = renderedLines.get(lineIdx);
        
        if (!lineEl) {
            const clone = docLineTemplate.content.cloneNode(true);
            lineEl = clone.querySelector('.doc-line-container');
            lineEl.dataset.index = lineIdx;
            lineEl.querySelector('.doc-line-text').textContent = data.text;
            
            // Insert in correct order
            let inserted = false;
            for (let child of annotatedDocument.children) {
                if (parseInt(child.dataset.index) > lineIdx) {
                    annotatedDocument.insertBefore(clone, child);
                    inserted = true;
                    break;
                }
            }
            if (!inserted) {
                annotatedDocument.appendChild(clone);
            }
            
            renderedLines.set(lineIdx, lineEl);
        }

        const statusEl = lineEl.querySelector('.doc-line-status');
        const citationEl = lineEl.querySelector('.doc-line-citation');
        
        // Update status badge
        statusEl.className = 'doc-line-status'; // reset
        if (payload.type === 'line_searching') {
            statusEl.textContent = 'Searching...';
            statusEl.classList.add('status-searching');
        } else if (payload.type === 'line_complete') {
            if (data.status === 'SUPPORTED_TIER1' || data.status === 'SUPPORTED_TIER2') {
                statusEl.textContent = data.status === 'SUPPORTED_TIER1' ? 'Supported (Tier 1)' : 'Supported (Tier 2)';
                statusEl.classList.add('status-supported');
                
                // Show highest tier source
                if (data.sources && data.sources.length > 0) {
                    const topSource = data.sources[0];
                    citationEl.innerHTML = `<strong>Tier ${topSource.tier} Source Found:</strong><br>${topSource.citation_string}<br><br><span style="font-size: 0.85em; opacity: 0.8;">Reason: ${data.reason}</span>`;
                    citationEl.classList.remove('hidden');
                }
            } else if (data.status === 'NO_SUPPORT_FOUND') {
                statusEl.textContent = 'No Support Found';
                statusEl.classList.add('status-no_support');
                citationEl.innerHTML = `<span style="font-size: 0.85em; opacity: 0.8;">Reason: ${data.reason}</span>`;
                citationEl.classList.remove('hidden');
            } else if (data.status === 'SEARCH_SKIPPED') {
                statusEl.textContent = 'Skipped';
                statusEl.classList.add('status-skipped');
                citationEl.innerHTML = `<span style="font-size: 0.85em; opacity: 0.8;">Reason: ${data.reason}</span>`;
                citationEl.classList.remove('hidden');
            } else {
                statusEl.textContent = data.status || 'Failed';
                statusEl.classList.add('status-skipped');
                if (data.reason) {
                    citationEl.innerHTML = `<span style="font-size: 0.85em; opacity: 0.8;">Reason: ${data.reason}</span>`;
                    citationEl.classList.remove('hidden');
                }
            }
        }
        
        // Auto scroll to bottom
        annotatedDocument.scrollTop = annotatedDocument.scrollHeight;
    };
    
    eventSource.onerror = function(err) {
        console.error("SSE connection error", err);
        eventSource.close();
    };
}

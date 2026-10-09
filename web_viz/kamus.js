let allComponents = [];
let bantenDict = {};
let currentFiltered = [];
let renderedIndex = 0;
const PAGE_SIZE = 40;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data.json');
        const data = await response.json();
        
        processData(data.banten || []);
        initDashboard();
        initControls();
        initModal();
        applyFilters();
    } catch (error) {
        console.error("Error loading component dictionary:", error);
    }
});

function processData(bantenList) {
    const compMap = {};
    bantenDict = {};

    bantenList.forEach((banten, bIdx) => {
        const bantenName = banten.nama ? banten.nama.trim() : `Banten #${bIdx + 1}`;
        bantenDict[bantenName] = banten;

        const komponenArr = Array.isArray(banten.komponen) ? banten.komponen : [];

        komponenArr.forEach(comp => {
            let compName = '';
            let peran = '';
            let deskripsi = '';

            if (typeof comp === 'string') {
                compName = comp.trim();
            } else if (comp && typeof comp === 'object') {
                compName = comp.nama ? comp.nama.trim() : '';
                peran = comp.peran ? comp.peran.trim() : '';
                deskripsi = comp.deskripsi ? comp.deskripsi.trim() : '';
            }

            if (!compName) return;

            const key = compName.toLowerCase();

            if (!compMap[key]) {
                compMap[key] = {
                    id: key,
                    name: compName,
                    usages: [],
                    roles: new Set(),
                    descriptions: new Set()
                };
            }

            // Record this banten usage if not already recorded
            const exists = compMap[key].usages.some(u => u.bantenName.toLowerCase() === bantenName.toLowerCase());
            if (!exists) {
                compMap[key].usages.push({
                    bantenName: bantenName,
                    peran: peran,
                    deskripsi: deskripsi
                });
            }

            if (peran) compMap[key].roles.add(peran);
            if (deskripsi) compMap[key].descriptions.add(deskripsi);
        });
    });

    // Convert map to array and pre-index search keywords
    allComponents = Object.values(compMap).map(item => {
        const roleStr = Array.from(item.roles).join(' ');
        const descStr = Array.from(item.descriptions).join(' ');
        const bantenStr = item.usages.map(u => u.bantenName).join(' ');
        
        return {
            ...item,
            usageCount: item.usages.length,
            _searchIndex: `${item.name} ${roleStr} ${descStr} ${bantenStr}`.toLowerCase()
        };
    });
}

function initDashboard() {
    const totalComponentsEl = document.getElementById('total-components');
    const topComponentEl = document.getElementById('top-component');
    const totalRelationsEl = document.getElementById('total-relations');

    const totalComp = allComponents.length;
    let totalRelations = 0;
    let topComp = null;

    allComponents.forEach(comp => {
        totalRelations += comp.usageCount;
        if (!topComp || comp.usageCount > topComp.usageCount) {
            topComp = comp;
        }
    });

    totalComponentsEl.innerText = totalComp.toLocaleString('id-ID');
    totalRelationsEl.innerText = totalRelations.toLocaleString('id-ID');
    
    if (topComp) {
        topComponentEl.innerHTML = `${escapeHtml(topComp.name)} <span style="font-size: 1rem; color: var(--text-muted); font-weight: 500;">(${topComp.usageCount} Banten)</span>`;
    }
}

function initControls() {
    const searchInput = document.getElementById('searchInput');
    const sortFilter = document.getElementById('sortFilter');
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    const listContainer = document.getElementById('dictionaryList');

    // Debounced search
    let debounceTimer = null;
    searchInput.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(applyFilters, 100);
    });

    sortFilter.addEventListener('change', applyFilters);

    loadMoreBtn.addEventListener('click', () => {
        renderChunk(false);
    });

    // Event delegation on dictionary list
    listContainer.addEventListener('click', (e) => {
        // If clicking banten subcard -> open banten modal
        const bantenCard = e.target.closest('.banten-subcard');
        if (bantenCard) {
            e.stopPropagation();
            const bantenName = bantenCard.dataset.banten;
            const bantenItem = bantenDict[bantenName];
            if (bantenItem) {
                openModal(bantenItem);
            }
            return;
        }

        // If clicking header -> toggle dropdown accordion
        const header = e.target.closest('.component-header');
        if (header) {
            const card = header.closest('.component-card');
            if (card) {
                toggleDropdown(card);
            }
        }
    });
}

function toggleDropdown(card) {
    const isExpanded = card.classList.contains('expanded');
    
    if (isExpanded) {
        card.classList.remove('expanded');
    } else {
        // Lazy render dropdown content if empty
        const dropdown = card.querySelector('.component-dropdown');
        if (dropdown && dropdown.dataset.rendered !== 'true') {
            const compId = card.dataset.id;
            const comp = allComponents.find(c => c.id === compId);
            if (comp) {
                renderDropdownContent(dropdown, comp);
                dropdown.dataset.rendered = 'true';
            }
        }
        card.classList.add('expanded');
    }
}

function renderDropdownContent(container, comp) {
    let html = '';

    // If there are general roles/descriptions
    const rolesList = Array.from(comp.roles);
    if (rolesList.length > 0) {
        html += `<div class="dropdown-desc"><strong>Peran umum:</strong> ${escapeHtml(rolesList.slice(0, 3).join(', '))}</div>`;
    }

    html += `<div style="font-size: 0.9rem; font-weight: 600; margin-bottom: 0.6rem; color: var(--text-main);">Daftar Banten yang Menggunakan (${comp.usages.length}):</div>`;
    html += `<div class="banten-grid">`;

    comp.usages.forEach(u => {
        const roleBadge = u.peran ? `<span class="badge-peran">${escapeHtml(u.peran)}</span>` : '';
        const descText = u.deskripsi ? `<p style="margin-top: 0.35rem;">${escapeHtml(u.deskripsi)}</p>` : '';

        html += `
            <div class="banten-subcard" data-banten="${escapeHtml(u.bantenName)}">
                <h5>${escapeHtml(u.bantenName)}</h5>
                ${roleBadge}
                ${descText}
            </div>
        `;
    });

    html += `</div>`;
    container.innerHTML = html;
}

function applyFilters() {
    const searchInput = document.getElementById('searchInput');
    const sortFilter = document.getElementById('sortFilter');
    const term = searchInput.value.trim().toLowerCase();
    const sortMode = sortFilter.value;

    let filtered = [];
    const len = allComponents.length;

    for (let i = 0; i < len; i++) {
        const item = allComponents[i];
        if (!term || item._searchIndex.includes(term)) {
            filtered.push(item);
        }
    }

    // Sort
    if (sortMode === 'usage_desc') {
        filtered.sort((a, b) => b.usageCount - a.usageCount);
    } else if (sortMode === 'usage_asc') {
        filtered.sort((a, b) => a.usageCount - b.usageCount);
    } else if (sortMode === 'name_asc') {
        filtered.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortMode === 'name_desc') {
        filtered.sort((a, b) => b.name.localeCompare(a.name));
    }

    currentFiltered = filtered;
    
    const countEl = document.getElementById('resultsCount');
    countEl.innerText = `Menampilkan ${filtered.length.toLocaleString('id-ID')} komponen`;

    renderChunk(true);
}

function renderChunk(reset = false) {
    const listContainer = document.getElementById('dictionaryList');
    const loadMoreBtn = document.getElementById('loadMoreBtn');

    if (reset) {
        listContainer.innerHTML = '';
        renderedIndex = 0;
    }

    if (currentFiltered.length === 0) {
        listContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 3rem;">Tidak ada komponen yang cocok dengan kata kunci.</div>';
        loadMoreBtn.style.display = 'none';
        return;
    }

    const nextBatch = currentFiltered.slice(renderedIndex, renderedIndex + PAGE_SIZE);
    let html = '';

    nextBatch.forEach(comp => {
        html += `
            <div class="component-card" data-id="${comp.id}">
                <div class="component-header">
                    <div class="component-title-group">
                        <span class="component-name">${escapeHtml(comp.name)}</span>
                        <span class="component-badge">${comp.usageCount} Banten</span>
                    </div>
                    <span class="component-arrow">▼</span>
                </div>
                <div class="component-dropdown" data-rendered="false">
                    <!-- Lazy rendered on expand -->
                </div>
            </div>
        `;
    });

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    while (tempDiv.firstChild) {
        listContainer.appendChild(tempDiv.firstChild);
    }

    renderedIndex += nextBatch.length;

    if (renderedIndex < currentFiltered.length) {
        loadMoreBtn.style.display = 'block';
        loadMoreBtn.innerText = `Tampilkan Lebih Banyak (${(currentFiltered.length - renderedIndex).toLocaleString('id-ID')} lagi)`;
    } else {
        loadMoreBtn.style.display = 'none';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function initModal() {
    const modal = document.getElementById('detailModal');
    const closeBtn = document.querySelector('.close-btn');
    
    closeBtn.onclick = function() {
        modal.style.display = "none";
    };
    
    window.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = "none";
        }
    };

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
        }
    });
}

function openModal(item) {
    const modal = document.getElementById('detailModal');
    const modalBody = document.getElementById('modalBody');
    
    let html = `<h2>${escapeHtml(item.nama)}</h2>`;
    
    if (item.deskripsi) {
        html += `<div class="modal-section">
            <h3>Deskripsi</h3>
            <p>${escapeHtml(item.deskripsi)}</p>
        </div>`;
    }
    
    if (item.makna) {
        html += `<div class="modal-section">
            <h3>Makna</h3>
            <p>${escapeHtml(item.makna)}</p>
        </div>`;
    }
    
    if (item.fungsi) {
        html += `<div class="modal-section">
            <h3>Fungsi</h3>
            <p>${escapeHtml(item.fungsi)}</p>
        </div>`;
    }
    
    if (item.komponen && item.komponen.length > 0) {
        html += `<div class="modal-section">
            <h3>Seluruh Komponen Banten Ini (${item.komponen.length})</h3>
            <div class="komponen-list">`;
        
        item.komponen.forEach(comp => {
            const compName = typeof comp === 'string' ? comp : (comp.nama || 'Tanpa Nama');
            const compPeran = (typeof comp === 'object' && comp.peran) ? `<strong>Peran:</strong> ${escapeHtml(comp.peran)}<br>` : '';
            const compDesc = (typeof comp === 'object' && comp.deskripsi) ? `<strong>Info:</strong> ${escapeHtml(comp.deskripsi)}` : '';
            
            html += `<div class="komponen-item">
                <h4>${escapeHtml(compName)}</h4>
                <p>${compPeran}${compDesc}</p>
            </div>`;
        });
        
        html += `</div></div>`;
    }
    
    modalBody.innerHTML = html;
    modal.style.display = "block";
}

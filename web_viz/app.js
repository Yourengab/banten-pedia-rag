let categoryChartInstance = null;
let topBantenChartInstance = null;
let allData = [];
let categoriesMap = {};

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data.json');
        const data = await response.json();
        
        // Pre-process all items for instant searching, counting, and categorization
        allData = (data.banten || []).map((item, index) => {
            const name = item.nama ? item.nama.trim() : "Tanpa Nama";
            const firstWord = name.split(' ')[0];
            const category = firstWord && firstWord.length > 3 ? firstWord : "Lainnya";
            const compCount = item.komponen ? item.komponen.length : 0;
            
            // Build searchable text once
            const compNames = item.komponen ? item.komponen.map(c => c.nama || '').join(' ') : '';
            const searchIndex = `${name} ${item.deskripsi || ''} ${item.fungsi || ''} ${item.makna || ''} ${compNames}`.toLowerCase();

            return {
                ...item,
                id: index,
                nama: name,
                category: category,
                _compCount: compCount,
                _searchIndex: searchIndex
            };
        });

        initCategories(allData);
        initDashboard(allData);
        createCharts();
        updateCharts(allData);
        initList(allData);
        initModal();
        initScrollAnimations();
        
    } catch (error) {
        console.error("Error loading data:", error);
    }
});

// Smooth scroll for anchor links
function initScrollAnimations() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

function initCategories(data) {
    categoriesMap = {};
    data.forEach(item => {
        categoriesMap[item.category] = (categoriesMap[item.category] || 0) + 1;
    });

    const categoryFilter = document.getElementById('categoryFilter');
    const sortedCategories = Object.keys(categoriesMap).sort((a, b) => categoriesMap[b] - categoriesMap[a]);
    
    sortedCategories.forEach(cat => {
        const option = document.createElement('option');
        option.value = cat;
        option.textContent = `${cat} (${categoriesMap[cat]})`;
        categoryFilter.appendChild(option);
    });
}

function initDashboard(data) {
    const total = data.length;
    let maxComponents = 0;
    let localCatMap = {};
    
    for (let i = 0; i < data.length; i++) {
        const item = data[i];
        if (item._compCount > maxComponents) {
            maxComponents = item._compCount;
        }
        localCatMap[item.category] = (localCatMap[item.category] || 0) + 1;
    }
    
    let topCategory = "-";
    let topCatCount = 0;
    for (let cat in localCatMap) {
        if (localCatMap[cat] > topCatCount) {
            topCatCount = localCatMap[cat];
            topCategory = cat;
        }
    }
    
    document.getElementById('total-banten').innerText = total;
    document.getElementById('top-category').innerText = topCategory;
    document.getElementById('max-components').innerText = maxComponents;
}

function createCharts() {
    Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';
    Chart.defaults.color = '#1d1d1f';

    // 1. Doughnut Chart: Kelompok Penamaan Sama
    const categoryCtx = document.getElementById('categoryChart').getContext('2d');
    categoryChartInstance = new Chart(categoryCtx, {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    '#0071e3', '#34c759', '#ff9500', '#ff3b30', '#af52de', '#5856d6', '#8e8e93'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false, // Matikan animasi agar tidak lag
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        usePointStyle: true,
                        boxWidth: 8,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` ${context.label}: ${context.raw} banten`;
                        }
                    }
                }
            },
            cutout: '60%'
        }
    });

    // 2. Bar Chart: 5 Banten dengan Komponen Terbanyak
    const topBantenCtx = document.getElementById('topBantenChart').getContext('2d');
    topBantenChartInstance = new Chart(topBantenCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Jumlah Komponen',
                data: [],
                backgroundColor: 'rgba(52, 199, 89, 0.85)',
                borderColor: '#34c759',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false, // Matikan animasi agar tidak lag
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return ` ${context.raw} Komponen`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: '#e5e5ea' }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        maxRotation: 30,
                        minRotation: 0,
                        autoSkip: false
                    }
                }
            }
        }
    });
}

function updateCharts(data) {
    if (!categoryChartInstance || !topBantenChartInstance) return;

    // 1. Update Doughnut Chart (Proporsi Kelompok Penamaan Sama)
    let localCatMap = {};
    for (let i = 0; i < data.length; i++) {
        const cat = data[i].category;
        localCatMap[cat] = (localCatMap[cat] || 0) + 1;
    }

    const sortedCats = Object.keys(localCatMap)
        .map(key => ({ category: key, count: localCatMap[key] }))
        .sort((a, b) => b.count - a.count);

    let labels = [];
    let counts = [];
    let othersCount = 0;

    for (let i = 0; i < sortedCats.length; i++) {
        if (i < 6) {
            labels.push(sortedCats[i].category);
            counts.push(sortedCats[i].count);
        } else {
            othersCount += sortedCats[i].count;
        }
    }

    if (othersCount > 0) {
        labels.push('Lain-lain');
        counts.push(othersCount);
    }

    if (labels.length === 0) {
        labels = ['Tidak ada data'];
        counts = [0];
    }

    categoryChartInstance.data.labels = labels;
    categoryChartInstance.data.datasets[0].data = counts;
    categoryChartInstance.update('none'); // Update instan tanpa re-render animasi

    // 2. Update Bar Chart (Top 5 Banten Komponen Terbanyak)
    // Quick copy and sort
    const top5 = [...data]
        .sort((a, b) => b._compCount - a._compCount)
        .slice(0, 5);

    const top5Labels = top5.map(item => item.nama.length > 16 ? item.nama.substring(0, 16) + '...' : item.nama);
    const top5Data = top5.map(item => item._compCount);

    topBantenChartInstance.data.labels = top5Labels.length > 0 ? top5Labels : ['Tidak ada data'];
    topBantenChartInstance.data.datasets[0].data = top5Data.length > 0 ? top5Data : [0];
    topBantenChartInstance.update('none'); // Update instan tanpa re-render animasi
}

function initList(data) {
    const listContainer = document.getElementById('bantenList');
    const searchInput = document.getElementById('searchInput');
    const categoryFilter = document.getElementById('categoryFilter');
    const sortFilter = document.getElementById('sortFilter');
    
    // Fast string-based rendering
    const renderList = (items) => {
        if (items.length === 0) {
            listContainer.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">Tidak ada banten yang cocok dengan filter.</div>';
            return;
        }

        let html = '';
        const len = items.length;
        for (let i = 0; i < len; i++) {
            const item = items[i];
            const desc = item.deskripsi || item.fungsi || 'Tidak ada keterangan singkat.';
            html += `
                <div class="banten-item" data-id="${item.id}">
                    <div class="card-badge">${item._compCount} Komponen</div>
                    <h4>${escapeHtml(item.nama)}</h4>
                    <p>${escapeHtml(desc)}</p>
                    <button class="detail-btn">Selengkapnya</button>
                </div>
            `;
        }
        listContainer.innerHTML = html;
    };

    // Single delegated event listener for click on items
    listContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('.detail-btn');
        if (!btn) return;
        
        const itemCard = btn.closest('.banten-item');
        const id = parseInt(itemCard.dataset.id, 10);
        const selected = allData.find(item => item.id === id);
        if (selected) openModal(selected);
    });

    const applyFilters = () => {
        const term = searchInput.value.trim().toLowerCase();
        const cat = categoryFilter.value;
        const sortMode = sortFilter.value;

        let filtered = [];
        for (let i = 0; i < allData.length; i++) {
            const item = allData[i];
            const matchTerm = !term || item._searchIndex.includes(term);
            const matchCat = !cat || item.category === cat;
            if (matchTerm && matchCat) {
                filtered.push(item);
            }
        }

        // Sorting
        if (sortMode === 'name_asc') {
            filtered.sort((a, b) => a.nama.localeCompare(b.nama));
        } else if (sortMode === 'name_desc') {
            filtered.sort((a, b) => b.nama.localeCompare(a.nama));
        } else if (sortMode === 'comp_desc') {
            filtered.sort((a, b) => b._compCount - a._compCount);
        } else if (sortMode === 'comp_asc') {
            filtered.sort((a, b) => a._compCount - b._compCount);
        }

        renderList(filtered);
        initDashboard(filtered);
        updateCharts(filtered);
    };

    renderList(data);

    // Debounced search to guarantee butter-smooth typing
    let debounceTimeout = null;
    searchInput.addEventListener('input', () => {
        if (debounceTimeout) clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(applyFilters, 100);
    });

    categoryFilter.addEventListener('change', applyFilters);
    sortFilter.addEventListener('change', applyFilters);
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
        document.body.style.overflow = '';
    };
    
    window.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = "none";
            document.body.style.overflow = '';
        }
    };

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && modal.style.display === 'block') {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    });
}

function openModal(item) {
    const modal = document.getElementById('detailModal');
    const modalHeader = document.getElementById('modalHeader');
    const modalTitle = document.getElementById('modalTitle');
    const modalMeta = document.getElementById('modalMeta');
    const modalBody = document.getElementById('modalBody');
    
    modalTitle.textContent = item.nama;
    modalMeta.innerHTML = `
        <span><i class="fas fa-cubes"></i> ${item._compCount || (item.komponen ? item.komponen.length : 0)} Komponen</span>
        <span><i class="fas fa-tag"></i> ${item.kategori || 'Umum'}</span>
    `;
    
    let html = '<div class="modal-grid">';
    
    // Main Content
    html += '<div class="main-column">';
    
    const sections = [
        { id: 'deskripsi', title: 'Deskripsi', icon: 'fa-info-circle', content: item.deskripsi },
        { id: 'makna', title: 'Makna', icon: 'fa-book-open', content: item.makna },
        { id: 'fungsi', title: 'Fungsi', icon: 'fa-cog', content: item.fungsi }
    ];

    sections.forEach((section, index) => {
        if (section.content) {
            const isOpen = index === 0 ? 'active' : '';
            html += `
                <div class="modal-accordion ${isOpen}" data-section="${section.id}">
                    <div class="accordion-header" onclick="toggleAccordion('${section.id}')">
                        <h3><i class="fas ${section.icon}"></i> ${section.title}</h3>
                        <i class="fas fa-chevron-down arrow"></i>
                    </div>
                    <div class="accordion-content">
                        <p>${escapeHtml(section.content)}</p>
                    </div>
                </div>`;
        }
    });
    
    html += '</div>';

    // Components
    html += '<div class="side-column">';
    if (item.komponen && item.komponen.length > 0) {
        html += `<div class="modal-section no-border">
            <h3><i class="fas fa-list-ul"></i> Daftar Komponen</h3>
            <div class="komponen-list">`;
        
        item.komponen.forEach(comp => {
            const compName = comp.nama || 'Tanpa Nama';
            const hasDetail = comp.peran || comp.deskripsi;
            const compDetail = hasDetail ? `<p>${comp.peran ? `<strong>Peran:</strong> ${escapeHtml(comp.peran)}<br>` : ''}${comp.deskripsi ? `<strong>Info:</strong> ${escapeHtml(comp.deskripsi)}` : ''}</p>` : '';
            
            html += `<div class="komponen-item">
                <h4>${escapeHtml(compName)}</h4>
                ${compDetail}
            </div>`;
        });
        
        html += `</div></div>`;
    }
    html += '</div></div>';
    
    modalBody.innerHTML = html;
    modal.style.display = "block";
    document.body.style.overflow = 'hidden';
}

function toggleAccordion(sectionId) {
    const parent = document.querySelector(`.modal-accordion[data-section="${sectionId}"]`);
    const all = document.querySelectorAll('.modal-accordion');
    
    if (parent.classList.contains('active')) {
        parent.classList.remove('active');
    } else {
        all.forEach(a => a.classList.remove('active'));
        parent.classList.add('active');
    }
}

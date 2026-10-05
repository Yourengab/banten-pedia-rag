document.addEventListener('DOMContentLoaded', async () => {
    try {
        const response = await fetch('data.json');
        const data = await response.json();
        const bantenList = data.banten;
        
        initDashboard(bantenList);
        initChart(bantenList);
        initList(bantenList);
        initModal();
        
    } catch (error) {
        console.error("Error loading data:", error);
    }
});

function initDashboard(data) {
    const total = data.length;
    let totalComponents = 0;
    let maxComponents = 0;
    
    data.forEach(item => {
        const compCount = item.komponen ? item.komponen.length : 0;
        totalComponents += compCount;
        if (compCount > maxComponents) {
            maxComponents = compCount;
        }
    });
    
    const avg = total > 0 ? (totalComponents / total).toFixed(1) : 0;
    
    document.getElementById('total-banten').innerText = total;
    document.getElementById('avg-components').innerText = avg;
    document.getElementById('max-components').innerText = maxComponents;
}

function initChart(data) {
    const sortedData = [...data].sort((a, b) => {
        const aCount = a.komponen ? a.komponen.length : 0;
        const bCount = b.komponen ? b.komponen.length : 0;
        return bCount - aCount;
    });
    
    const top10 = sortedData.slice(0, 10);
    const labels = top10.map(item => item.nama.length > 20 ? item.nama.substring(0, 20) + '...' : item.nama);
    const chartData = top10.map(item => item.komponen ? item.komponen.length : 0);
    
    const ctx = document.getElementById('bantenChart').getContext('2d');
    
    Chart.defaults.color = '#e0aaff';
    Chart.defaults.font.family = 'Inter';
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Jumlah Komponen',
                data: chartData,
                backgroundColor: 'rgba(157, 78, 221, 0.7)',
                borderColor: 'rgba(199, 125, 255, 1)',
                borderWidth: 1,
                borderRadius: 6,
                hoverBackgroundColor: 'rgba(199, 125, 255, 0.9)'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255,255,255,0.05)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Ensure items with same name have a unique identifier in the list if needed.
// To handle multiple identical names, we just show them and let them click.
function initList(data) {
    const listContainer = document.getElementById('bantenList');
    const searchInput = document.getElementById('searchInput');
    
    const renderList = (items) => {
        listContainer.innerHTML = '';
        items.forEach((item, index) => {
            const compCount = item.komponen ? item.komponen.length : 0;
            const desc = item.deskripsi || item.fungsi || 'Tidak ada deskripsi';
            
            const div = document.createElement('div');
            div.className = 'banten-item';
            div.innerHTML = `
                <h4>${item.nama}</h4>
                <p>${desc}</p>
                <div class="meta">${compCount} Komponen</div>
            `;
            
            // Add click listener to open modal with details
            div.addEventListener('click', () => openModal(item));
            
            listContainer.appendChild(div);
        });
    };
    
    renderList(data);
    
    searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const filtered = data.filter(item => 
            item.nama.toLowerCase().includes(term) || 
            (item.deskripsi && item.deskripsi.toLowerCase().includes(term))
        );
        renderList(filtered);
    });
}

function initModal() {
    const modal = document.getElementById('detailModal');
    const closeBtn = document.querySelector('.close-btn');
    
    closeBtn.onclick = function() {
        modal.style.display = "none";
    }
    
    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = "none";
        }
    }
}

function openModal(item) {
    const modal = document.getElementById('detailModal');
    const modalBody = document.getElementById('modalBody');
    
    let html = `<h2>${item.nama}</h2>`;
    
    if (item.deskripsi) {
        html += `<div class="modal-section">
            <h3>Deskripsi</h3>
            <p>${item.deskripsi}</p>
        </div>`;
    }
    
    if (item.makna) {
        html += `<div class="modal-section">
            <h3>Makna</h3>
            <p>${item.makna}</p>
        </div>`;
    }
    
    if (item.fungsi) {
        html += `<div class="modal-section">
            <h3>Fungsi</h3>
            <p>${item.fungsi}</p>
        </div>`;
    }
    
    if (item.komponen && item.komponen.length > 0) {
        html += `<div class="modal-section">
            <h3>Komponen (${item.komponen.length})</h3>
            <div class="komponen-list">`;
        
        item.komponen.forEach(comp => {
            const compName = comp.nama || 'Tanpa Nama';
            const compPeran = comp.peran ? `<strong>Peran:</strong> ${comp.peran}<br>` : '';
            const compDesc = comp.deskripsi ? `<strong>Info:</strong> ${comp.deskripsi}` : '';
            
            html += `<div class="komponen-item">
                <h4>${compName}</h4>
                <p>${compPeran}${compDesc}</p>
            </div>`;
        });
        
        html += `</div></div>`;
    }
    
    modalBody.innerHTML = html;
    modal.style.display = "block";
}

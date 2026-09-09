let currentChatId = null;
let currentPage = 1;
let genderChart = null;

document.addEventListener('DOMContentLoaded', () => {
    const chatSelector = document.getElementById('chat-selector');
    
    if (chatSelector.options.length > 0) {
        currentChatId = chatSelector.value;
        loadDashboard();
    }

    chatSelector.addEventListener('change', (e) => {
        currentChatId = e.target.value;
        currentPage = 1;
        loadDashboard();
    });

    document.getElementById('search-input').addEventListener('input', () => {
        currentPage = 1;
        loadMembers();
    });

    document.getElementById('gender-filter').addEventListener('change', () => {
        currentPage = 1;
        loadMembers();
    });

    document.getElementById('prev-page').addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadMembers();
        }
    });

    document.getElementById('next-page').addEventListener('click', () => {
        currentPage++;
        loadMembers();
    });
});

async function loadDashboard() {
    if (!currentChatId) return;
    await loadStats();
    await loadMembers();
}

async function loadStats() {
    const response = await fetch(`/api/stats/${currentChatId}`);
    const stats = await response.json();

    document.getElementById('total-count').textContent = Object.values(stats).reduce((a, b) => a + b, 0);
    document.getElementById('male-count').textContent = stats.Male || 0;
    document.getElementById('female-count').textContent = stats.Female || 0;
    document.getElementById('deleted-count').textContent = stats.Deleted || 0;

    updateChart(stats);
}

function updateChart(stats) {
    const ctx = document.getElementById('genderChart').getContext('2d');
    
    const data = {
        labels: ['Erkaklar', 'Ayollar', 'O\'chirilganlar', 'Aniqlanmagan'],
        datasets: [{
            data: [
                stats.Male || 0, 
                stats.Female || 0, 
                stats.Deleted || 0, 
                stats.Unknown || 0
            ],
            backgroundColor: ['#3b82f6', '#f472b6', '#34495e', '#94a3b8'],
            borderWidth: 0
        }]
    };

    if (genderChart) {
        genderChart.destroy();
    }

    genderChart = new Chart(ctx, {
        type: 'doughnut',
        data: data,
        options: {
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8' }
                }
            },
            cutout: '70%'
        }
    });
}

async function loadMembers() {
    const search = document.getElementById('search-input').value;
    const gender = document.getElementById('gender-filter').value;
    
    const response = await fetch(`/api/members/${currentChatId}?search=${search}&gender=${gender}&page=${currentPage}`);
    const data = await response.json();

    const tbody = document.getElementById('table-body');
    tbody.innerHTML = '';

    data.members.forEach(member => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${member.user_id}</td>
            <td>${member.first_name || '-'}</td>
            <td>${member.last_name || '-'}</td>
            <td>${member.username ? '@' + member.username : '-'}</td>
            <td><span class="gender-badge gender-${member.gender.toLowerCase()}">${translateGender(member.gender)}</span></td>
            <td><span class="status-badge status-${member.is_deleted ? 'deleted' : 'active'}">${member.is_deleted ? 'O\'chirilgan' : 'Faol'}</span></td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('page-info').textContent = `Sahifa ${data.page} / ${data.pages || 1}`;
    document.getElementById('prev-page').disabled = (currentPage <= 1);
    document.getElementById('next-page').disabled = (currentPage >= data.pages);
}

function translateGender(gender) {
    const map = {
        'Male': 'Erkak',
        'Female': 'Ayol',
        'Unknown': 'Aniqlanmagan',
        'Deleted': 'O\'chirilgan'
    };
    return map[gender] || gender;
}

// Data for the application
const courts = [
    {
        id: 1,
        name: "Quadra 1",
        type: "Futebol Society",
        availableTimes: [18, 19, 21, 22], // Hours available
        allTimes: [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    },
    {
        id: 2,
        name: "Quadra 2",
        type: "Vôlei de Areia",
        availableTimes: [13, 14, 15, 16, 20, 21],
        allTimes: [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    },
    {
        id: 3,
        name: "Quadra 3",
        type: "Beach Tennis",
        availableTimes: [17, 18, 19, 20],
        allTimes: [13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    }
];

const menuItems = [
    { id: 1, name: "Água Mineral", price: "R$ 3.00", icon: "💧" },
    { id: 2, name: "Suco Natural", price: "R$ 8.00", icon: "🍊" },
    { id: 3, name: "Isotônico", price: "R$ 10.00", icon: "⚡" },
    { id: 4, name: "Açaí na Tigela", price: "R$ 18.00", icon: "🥣" },
    { id: 5, name: "Sanduíche Natural", price: "R$ 12.00", icon: "🥪" },
    { id: 6, name: "Refrigerante", price: "R$ 6.00", icon: "🥤" }
];

// Utility: Format Date
function getFormattedDate() {
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    return new Date().toLocaleDateString('pt-BR', options);
}

// Utility: Show Toast
function showToast(message) {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    } else {
        alert(message);
    }
}

// Page Specific Logic
document.addEventListener('DOMContentLoaded', () => {

    // Booking Page Logic
    const courtsContainer = document.getElementById('courtsContainer');
    if (courtsContainer) {
        // Set date
        const dateDisplay = document.getElementById('currentDateDisplay');
        if (dateDisplay) {
            // Capitalize first letter
            const dateStr = getFormattedDate();
            dateDisplay.textContent = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);
        }

        // Render Courts
        courts.forEach(court => {
            const card = document.createElement('div');
            card.className = 'card court-card';

            // Court Header (Name + Icon/Link)
            const header = document.createElement('div');
            header.className = 'court-header';
            header.innerHTML = `
                <div>
                    <div class="court-name">${court.name}</div>
                    <div class="text-secondary">${court.type}</div>
                </div>
                <a href="court-details.html?id=${court.id}" style="color: var(--color-warm-orange);">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                </a>
            `;

            // Time Grid
            const grid = document.createElement('div');
            grid.className = 'time-grid';

            court.allTimes.forEach(time => {
                const isAvailable = court.availableTimes.includes(time);
                const slot = document.createElement('div');
                slot.className = `time-slot ${isAvailable ? 'available' : 'unavailable'}`;
                slot.textContent = `${time}h`;

                if (isAvailable) {
                    slot.onclick = () => {
                        // Deselect others in this grid if we wanted single selection per court
                        // grid.querySelectorAll('.time-slot').forEach(s => s.classList.remove('selected'));

                        slot.classList.toggle('selected');
                        if (slot.classList.contains('selected')) {
                            showToast(`${court.name} reservada para ${time}:00`);
                        }
                    };
                }

                grid.appendChild(slot);
            });

            card.appendChild(header);
            card.appendChild(grid);
            courtsContainer.appendChild(card);
        });
    }

    // Menu Page Logic
    const menuContainer = document.getElementById('menuContainer');
    if (menuContainer) {
        menuItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'card menu-item';

            card.innerHTML = `
                <div class="menu-img-placeholder">${item.icon}</div>
                <div class="menu-item-details">
                    <h3>${item.name}</h3>
                    <div class="menu-item-price">${item.price}</div>
                </div>
                <button class="btn-icon" style="width: 32px; height: 32px; background: rgba(255,140,0,0.1);" onclick="showToast('${item.name} adicionado!')">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="12" y1="5" x2="12" y2="19"></line>
                        <line x1="5" y1="12" x2="19" y2="12"></line>
                    </svg>
                </button>
            `;

            menuContainer.appendChild(card);
        });
    }

    // Court Details Page Logic
    const detailTitle = document.getElementById('detailTitle');
    if (detailTitle) {
        const urlParams = new URLSearchParams(window.location.search);
        const courtId = parseInt(urlParams.get('id'));
        const court = courts.find(c => c.id === courtId) || courts[0]; // Default to first if not found

        if (court) {
            document.getElementById('heroCourtName').textContent = court.name;
            // Populate time grid for details page
            const grid = document.getElementById('detailTimeGrid');
            if (grid) {
                court.allTimes.forEach(time => {
                    const isAvailable = court.availableTimes.includes(time);
                    const slot = document.createElement('div');
                    slot.className = `time-slot ${isAvailable ? 'available' : 'unavailable'}`;
                    slot.textContent = `${time}h`;
                    grid.appendChild(slot);
                });
            }
        }
    }
});

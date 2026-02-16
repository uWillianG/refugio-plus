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

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const eyeIconId = inputId === 'password' ? 'eye-icon-password' : 'eye-icon-confirm';
    const eyeIcon = document.getElementById(eyeIconId);

    if (input.type === 'password') {
        input.type = 'text';
        eyeIcon.innerHTML = `
            <path d="m15.5 4.14 2.04 2.04M9.9 4.24 7.86 2.2M3 3l18 18m-8.31-8.31a4.67 4.67 0 0 1 6.31 6.31"/>
            <path d="M10.35 5.57a9.49 9.49 0 0 1 1.65-.14c7 0 10 7 10 7a13.16 13.16 0 0 1-1.7 2.55"/>
            <path d="M5.8 11.9 2 12s3-7 10-7a9.49 9.49 0 0 1 5.05 1.43"/>
        `;
    } else {
        input.type = 'password';
        eyeIcon.innerHTML = `
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
            <circle cx="12" cy="12" r="3"/>
        `;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const successToast = document.getElementById('toast-notification-success');
    if (successToast) {
        setTimeout(() => {
            successToast.classList.add('show');
        }, 100);

        setTimeout(() => {
            const redirectUrl = successToast.getAttribute('data-redirect-url');
            if (redirectUrl) {
                window.location = redirectUrl;
            }
        }, 2500);
    }
});

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const eyeIcon = document.getElementById('eye-icon');

    if (input.type === 'password') {
        input.type = 'text';
        eyeIcon.innerHTML = `
            <path d="m15.5 4.14 2.04 2.04M9.9 4.24 7.86 2.2M3 3l18 18m-8.31-8.31a4.67 4.67 0 0 1 6.31 6.31"/>
            <path d="M10.35 5.57a9.49 9.49 0 0 1 1.65-.14c7 0 10 7 10 7a13.16 13.16 0 0 1-1.7 2.55"/>
            <path d="M5.8 11.9 2 12s3-7 10-7a9.49 9.49 0 0 1 5.05 1.43"/>
        `;
    } else {
        input.type = 'password';
        eyeIcon.innerHTML = `
            <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/>
            <circle cx="12" cy="12" r="3"/>
        `;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const toast = document.getElementById('toast-notification');
    if (toast) {
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);

        setTimeout(() => {
            toast.classList.remove('show');
        }, 5000);
    }
    /*const successToast = document.getElementById('toast-notification-success');
    if (successToast) {
        setTimeout(() => {
            successToast.classList.add('show');
        }, 100);

        setTimeout(() => {
            // NOTE: If uncommenting, use a data attribute for the URL in HTML
            // window.location = successToast.dataset.redirectUrl;
        }, 2500);
    }*/
});

document.addEventListener('DOMContentLoaded', function () {
    const phoneInput = document.getElementById('phone');
    const cpfInput = document.getElementById('cpf');

    function formatPhone(value) {
        const digits = value.replace(/\D/g, '').slice(0, 11);
        if (digits.length <= 10) {
            return digits
                .replace(/^(\d{2})(\d)/, '($1) $2')
                .replace(/(\d{4})(\d)/, '$1-$2');
        }

        return digits
            .replace(/^(\d{2})(\d)/, '($1) $2')
            .replace(/(\d{5})(\d)/, '$1-$2');
    }

    function formatCpf(value) {
        const digits = value.replace(/\D/g, '').slice(0, 11);
        return digits
            .replace(/(\d{3})(\d)/, '$1.$2')
            .replace(/(\d{3})(\d)/, '$1.$2')
            .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
    }

    if (phoneInput) {
        phoneInput.value = formatPhone(phoneInput.value);
        phoneInput.addEventListener('input', function (event) {
            event.target.value = formatPhone(event.target.value);
        });
    }

    if (cpfInput) {
        cpfInput.value = formatCpf(cpfInput.value);
        cpfInput.addEventListener('input', function (event) {
            event.target.value = formatCpf(event.target.value);
        });
    }
});

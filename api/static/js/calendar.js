let currentDate = new Date();
let bookings = [];
let availableCars = [];
let searchQuery = '';
let selectedStatus = 'all';

const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const months = [
    'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];


function formatForDateTimeLocal(date) {
    const pad = num => String(num).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getFilteredBookings() {
    const normalized = searchQuery.trim().toLowerCase();
    return bookings.filter((booking) => {
        const statusMatch = selectedStatus === 'all' || booking.status === selectedStatus;
        if (!statusMatch) {
            return false;
        }

        if (!normalized) {
            return true;
        }

        const searchable = [booking.model, booking.number_plate, booking.full_name]
            .map((item) => String(item || '').toLowerCase())
            .join(' ');

        return searchable.includes(normalized);
    });
}



function requireAuthToken() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/';
        return null;
    }
    return token;
}

function notify(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => toast.classList.add('show'));

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 250);
    }, 2600);
}

async function loadBookings() {
    try {
        const response = await fetch('/api/bookings/calendar', {
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/';
                return;
            }
            throw new Error('Ошибка загрузки бронирований');
        }
        
        bookings = await response.json();
        renderCalendar();
    } catch (error) {
        console.error('Ошибка:', error);
    }
}


async function loadAvailableCars() {
    try {
        const response = await fetch('/api/cars/available', {
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки списка автомобилей');
        }
        
        availableCars = await response.json();
        updateCarSelect();
    } catch (error) {
        console.error('Ошибка:', error);
    }
}


function updateCarSelect() {
    const select = document.getElementById('carSelect');
    select.innerHTML = '<option value="">Выберите автомобиль</option>';
    
    availableCars.forEach(car => {
        const option = document.createElement('option');
        option.value = car.id;
        option.textContent = `${car.model} (${car.number_plate})`;
        select.appendChild(option);
    });
}


function showCreateBookingModal(date) {
    const modal = document.getElementById('createBookingModal');
    const startDateTime = document.getElementById('startDateTime');
    const endDateTime = document.getElementById('endDateTime');
    

    const startDate = new Date(date);
    startDate.setHours(9, 0, 0);
    startDateTime.value = formatForDateTimeLocal(startDate);
    

    const endDate = new Date(date);
    endDate.setDate(endDate.getDate() + 1);
    endDate.setHours(9, 0, 0);
    endDateTime.value = formatForDateTimeLocal(endDate);
    

    loadAvailableCars();
    
    modal.style.display = 'block';
}


function closeCreateBookingModal() {
    document.getElementById('createBookingModal').style.display = 'none';
}


async function createBooking(event) {
    event.preventDefault();
    
    const carId = document.getElementById('carSelect').value;
    const startTime = document.getElementById('startDateTime').value;
    const endTime = document.getElementById('endDateTime').value;
    
    if (!carId || !startTime || !endTime) {
        notify('Пожалуйста, заполните все поля', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/bookings/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${requireAuthToken()}`
            },
            body: JSON.stringify({
                car_id: parseInt(carId),
                start_time: startTime,
                end_time: endTime
            })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Ошибка при создании бронирования');
        }
        
        notify('Бронирование успешно создано', 'success');
        closeCreateBookingModal();
        loadBookings(); 
        
    } catch (error) {
        notify(error.message, 'error');
    }
}


function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    document.getElementById('currentMonth').textContent = `${months[month]} ${year}`;
    
    const calendar = document.getElementById('calendar');
    calendar.innerHTML = '';
    

    weekdays.forEach(day => {
        const weekday = document.createElement('div');
        weekday.className = 'weekday';
        weekday.textContent = day;
        calendar.appendChild(weekday);
    });
    
  
    const firstDay = new Date(year, month, 1);
    let startingDay = firstDay.getDay() || 7; 
    startingDay--; 
    
   
    for (let i = 0; i < startingDay; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day';
        calendar.appendChild(emptyDay);
    }
    
   
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
   
    for (let day = 1; day <= daysInMonth; day++) {
        const calendarDay = document.createElement('div');
        calendarDay.className = 'calendar-day';
        
        const dateDiv = document.createElement('div');
        dateDiv.className = 'date';
        dateDiv.textContent = day;
        calendarDay.appendChild(dateDiv);
        
       
        calendarDay.onclick = () => {
            const selectedDate = new Date(year, month, day);
            showCreateBookingModal(selectedDate);
        };
        
        const bookingsContainer = document.createElement('div');
        bookingsContainer.className = 'bookings-container';
        
    
        const dayBookings = getFilteredBookings().filter(booking => {
            const bookingDate = new Date(booking.start_time);
            return bookingDate.getDate() === day && 
                   bookingDate.getMonth() === month && 
                   bookingDate.getFullYear() === year;
        });
        
        
        dayBookings.forEach(booking => {
            const bookingDiv = document.createElement('div');
            bookingDiv.className = `booking ${booking.status}`;
            bookingDiv.textContent = `${booking.model} - ${booking.full_name}`;
            bookingDiv.onclick = (e) => {
                e.stopPropagation(); 
                showBookingDetails(booking);
            };
            bookingsContainer.appendChild(bookingDiv);
        });
        
        calendarDay.appendChild(bookingsContainer);
        calendar.appendChild(calendarDay);
    }
}


function showBookingDetails(booking) {
    const modal = document.getElementById('bookingModal');
    const bookingInfo = document.getElementById('bookingInfo');
    const beforePhotos = document.getElementById('beforePhotos');
    const afterPhotos = document.getElementById('afterPhotos');
    const bookingActions = document.getElementById('bookingActions');
    
  
    const startDate = new Date(booking.start_time).toLocaleString('ru-RU');
    const endDate = new Date(booking.end_time).toLocaleString('ru-RU');
    
   
    let statusText = '';
    let statusClass = '';
    
    switch(booking.status) {
        case 'active':
            statusText = 'Активно';
            statusClass = 'status-active';
            break;
        case 'completed':
            statusText = 'Завершено';
            statusClass = 'status-completed';
            break;
        case 'canceled':
            statusText = 'Отменено';
            statusClass = 'status-canceled';
            break;
        default:
            statusText = booking.status;
            statusClass = '';
    }
    
   
    bookingInfo.innerHTML = `
        <h2>Информация о бронировании</h2>
        <p><strong>Автомобиль:</strong> ${escapeHtml(booking.model)} (${escapeHtml(booking.number_plate)})</p>
        <p><strong>Клиент:</strong> ${escapeHtml(booking.full_name)}</p>
        <p><strong>ФИО:</strong> ${escapeHtml(booking.description || 'Не указано')}</p>
        <p><strong>Телефон:</strong> ${escapeHtml(booking.phone_number || 'Не указан')}</p>
        <p><strong>Телеграм:</strong> ${escapeHtml(booking.telegram_id)}</p>
        <p><strong>Начало:</strong> ${escapeHtml(startDate)}</p>
        <p><strong>Окончание:</strong> ${escapeHtml(endDate)}</p>
        <p><strong>Статус:</strong> <span class="status-badge ${statusClass}">${escapeHtml(statusText)}</span></p>
    `;
    
   
    beforePhotos.innerHTML = '';
    afterPhotos.innerHTML = '';
    
    
    const before = booking.photos?.before || [];
    const after = booking.photos?.after || [];

    before.forEach(photo => {
        const img = document.createElement('img');
        img.src = photo;
        img.className = 'photo-thumbnail';
        img.onclick = () => openLightbox(photo);
        beforePhotos.appendChild(img);
    });
    
    
    after.forEach(photo => {
        const img = document.createElement('img');
        img.src = photo;
        img.className = 'photo-thumbnail';
        img.onclick = () => openLightbox(photo);
        afterPhotos.appendChild(img);
    });
    
  
    bookingActions.innerHTML = '';
    
   
    if (booking.status === 'active') {
      
        const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
        

        const cancelButton = document.createElement('button');
        cancelButton.className = 'btn-cancel';
        cancelButton.textContent = 'Отменить бронирование';
        cancelButton.onclick = () => cancelUserBooking(booking.id);
        bookingActions.appendChild(cancelButton);
    }
    
    modal.style.display = 'block';
}


function openLightbox(photoUrl) {
    const lightbox = document.createElement('div');
    lightbox.className = 'modal';
    lightbox.style.display = 'block';
    
    const img = document.createElement('img');
    img.src = photoUrl;
    img.style.maxWidth = '90%';
    img.style.maxHeight = '90vh';
    img.style.margin = 'auto';
    img.style.position = 'absolute';
    img.style.top = '50%';
    img.style.left = '50%';
    img.style.transform = 'translate(-50%, -50%)';
    
    lightbox.onclick = () => document.body.removeChild(lightbox);
    lightbox.appendChild(img);
    document.body.appendChild(lightbox);
}


document.getElementById('prevMonth').onclick = () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
};

document.getElementById('nextMonth').onclick = () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
};

document.getElementById('goToTodayBtn').onclick = () => {
    currentDate = new Date();
    renderCalendar();
};


document.querySelector('.close').onclick = () => {
    document.getElementById('bookingModal').style.display = 'none';
};


async function logout() {
    try {
        const response = await fetch('/logout', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка при выходе из системы');
        }

        localStorage.removeItem('token');
        window.location.href = '/';
        
    } catch (error) {
        console.error('Ошибка:', error);
        notify(error.message, 'error');
    }
}

async function checkAdminRights() {
    try {
        const response = await fetch('/auth/me', {
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/';
                return;
            }
            throw new Error('Ошибка получения данных пользователя');
        }
        
        const userData = await response.json();
        if (userData.admin) {
            document.querySelector('.admin-controls').style.display = 'flex';
        }
    } catch (error) {
        console.error('Ошибка:', error);
    }
}

function showAddCarModal() {
    document.getElementById('addCarModal').style.display = 'block';
}

function closeAddCarModal() {
    document.getElementById('addCarModal').style.display = 'none';
}

async function addCar(event) {
    event.preventDefault();
    
    const model = document.getElementById('carModel').value;
    const number_plate = document.getElementById('carNumber').value;
    
    try {
        const response = await fetch('/api/cars/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${requireAuthToken()}`
            },
            body: JSON.stringify({ model, number_plate })
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.detail || 'Ошибка при добавлении автомобиля');
        }
        
        notify('Автомобиль успешно добавлен', 'success');
        closeAddCarModal();
        loadBookings(); 
        
    } catch (error) {
        console.error('Ошибка:', error);
        notify(error.message, 'error');
    }
}


function showManageBookingsModal() {

    document.getElementById('manageBookingsModal').style.display = 'block';
}


function closeManageBookingsModal() {
    document.getElementById('manageBookingsModal').style.display = 'none';
}


async function loadActiveBookings() {
    try {
        const response = await fetch('/api/bookings/calendar', {
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Ошибка загрузки бронирований');
        }
        
        const bookings = await response.json();
        
        const bookingsList = document.getElementById('activeBookingsList');
        bookingsList.innerHTML = '';
        
        if (bookings.length === 0) {
            bookingsList.innerHTML = `
                <div style="text-align: center; padding: 30px;">
                    <p>Нет бронирований</p>
                </div>
            `;
            return;
        }
        
   
        const groupedBookings = {
            active: bookings.filter(b => b.status === 'active'),
            completed: bookings.filter(b => b.status === 'completed'),
            canceled: bookings.filter(b => b.status === 'canceled')
        };
        
        
        if (groupedBookings.active.length > 0) {
            const activeHeader = document.createElement('h3');
            activeHeader.textContent = 'Активные бронирования';
            activeHeader.style.marginTop = '20px';
            bookingsList.appendChild(activeHeader);
            
            groupedBookings.active.forEach(booking => {
                addBookingItem(booking, bookingsList);
            });
        }
        
 
        if (groupedBookings.completed.length > 0) {
            const completedHeader = document.createElement('h3');
            completedHeader.textContent = 'Завершенные бронирования';
            completedHeader.style.marginTop = '20px';
            bookingsList.appendChild(completedHeader);
            
            groupedBookings.completed.forEach(booking => {
                addBookingItem(booking, bookingsList);
            });
        }
        
  
        if (groupedBookings.canceled.length > 0) {
            const canceledHeader = document.createElement('h3');
            canceledHeader.textContent = 'Отмененные бронирования';
            canceledHeader.style.marginTop = '20px';
            bookingsList.appendChild(canceledHeader);
            
            groupedBookings.canceled.forEach(booking => {
                addBookingItem(booking, bookingsList);
            });
        }
        
    } catch (error) {
        console.error('Ошибка:', error);
        notify(error.message, 'error');
    }
}


function addBookingItem(booking, container) {
    const startDate = new Date(booking.start_time).toLocaleString('ru-RU');
    const endDate = new Date(booking.end_time).toLocaleString('ru-RU');
    
  
    let statusText = '';
    let statusClass = '';
    
    switch(booking.status) {
        case 'active':
            statusText = 'Активно';
            statusClass = 'status-active';
            break;
        case 'completed':
            statusText = 'Завершено';
            statusClass = 'status-completed';
            break;
        case 'canceled':
            statusText = 'Отменено';
            statusClass = 'status-canceled';
            break;
        default:
            statusText = booking.status;
            statusClass = '';
    }
    
    const bookingItem = document.createElement('div');
    bookingItem.className = 'booking-item';
    bookingItem.innerHTML = `
        <div class="booking-info">
            <p><strong>Клиент:</strong> ${escapeHtml(booking.full_name)}</p>
            <p><strong>Автомобиль:</strong> ${escapeHtml(booking.model)} (${escapeHtml(booking.number_plate)})</p>
            <p><strong>Период:</strong> ${startDate} - ${endDate}</p>
            <p><strong>Статус:</strong> <span class="status-badge ${statusClass}">${statusText}</span></p>
        </div>
        <div class="booking-actions">
            ${booking.status === 'active' ? `
                <button onclick="updateBookingStatus(${booking.id}, 'completed')" class="btn-complete">Завершить</button>
                <button onclick="updateBookingStatus(${booking.id}, 'canceled')" class="btn-cancel">Отменить</button>
            ` : ''}
        </div>
    `;
    container.appendChild(bookingItem);
}


async function updateBookingStatus(bookingId, newStatus) {
    try {
        const response = await fetch(`/api/bookings/${bookingId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${requireAuthToken()}`
            },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Ошибка обновления статуса');
        }
        
        
        loadActiveBookings();
        loadBookings();
        
        const statusText = newStatus === 'completed' ? 'завершено' : 'отменено';
        notify(`Бронирование успешно ${statusText}`, 'success');
        
    } catch (error) {
        console.error('Ошибка:', error);
        notify(error.message, 'error');
    }
}


function refreshCalendar() {
    loadBookings();
}


async function getCurrentUser() {
    if (localStorage.getItem('user')) {
        return JSON.parse(localStorage.getItem('user'));
    }
    
    try {
        const response = await fetch('/auth/me', {
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                window.location.href = '/';
                return null;
            }
            throw new Error('Ошибка получения данных пользователя');
        }
        
        const userData = await response.json();
        localStorage.setItem('user', JSON.stringify(userData));
        return userData;
    } catch (error) {
        console.error('Ошибка получения пользователя:', error);
        return null;
    }
}


async function cancelUserBooking(bookingId) {
    if (!confirm('Вы уверены, что хотите отменить бронирование?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/bookings/${bookingId}/cancel`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${requireAuthToken()}`
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Ошибка ${response.status}`);
        }
        
        const data = await response.json();
        notify('Бронирование успешно отменено', 'success');
        document.getElementById('bookingModal').style.display = 'none';
        refreshCalendar();
    } catch (error) {
        notify(`Ошибка: ${error.message}`, 'error');
    }
}


document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuthToken()) {
        return;
    }

    loadBookings();
    checkAdminRights();

    const searchInput = document.getElementById('bookingSearch');
    const statusFilter = document.getElementById('statusFilter');

    searchInput.addEventListener('input', (event) => {
        searchQuery = event.target.value;
        renderCalendar();
    });

    statusFilter.addEventListener('change', (event) => {
        selectedStatus = event.target.value;
        renderCalendar();
    });

    document.getElementById('createBookingForm').addEventListener('submit', createBooking);
    document.getElementById('logoutBtn').addEventListener('click', logout);
    document.getElementById('addCarBtn').addEventListener('click', showAddCarModal);
    document.getElementById('addCarForm').addEventListener('submit', addCar);
}); 
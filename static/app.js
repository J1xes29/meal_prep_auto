const daySelect = document.getElementById('day_select');
const dateSelect = document.getElementById('date_select');
const foodSearchInput = document.getElementById('food_search');
const foodCategoryFilter = document.getElementById('food_category_filter');
const addOptionBtn = document.getElementById('add_option_btn');
const optionFilter = document.getElementById('option_filter');
const optionFilterBtn = document.getElementById('option_filter_btn');
const foodSearchBtn = document.getElementById('food_search_btn');
const editPlanBtn = document.getElementById('edit_plan_btn');
const planModal = document.getElementById('plan_modal');
const closePlanModalBtn = document.getElementById('close_plan_modal');
const closePlanModalSecondaryBtn = document.getElementById('close_plan_modal_btn');
const savePlanModalBtn = document.getElementById('save_plan_modal_btn');

function showToast(message, type = 'success') {
    const container = document.getElementById('toast_container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 2600);
}

function showPrompt(message, type = 'success') {
    showToast(message, type);
}

function setTodayDate() {
    if (!dateSelect) return;
    const today = new Date();
    const isoDate = today.toISOString().split('T')[0];
    dateSelect.value = isoDate;
    syncDayFromDate();
}

function syncDayFromDate() {
    if (!dateSelect.value || !daySelect) return;

    const date = new Date(`${dateSelect.value}T00:00:00`);
    const weekdayNames = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
    daySelect.value = weekdayNames[date.getDay()];
}

function loadOptions(filterCategory = '') {
    const url = filterCategory ? `/api/options?category=${encodeURIComponent(filterCategory)}` : '/api/options';

    fetch(url)
        .then(response => response.json())
        .then(data => {
            const list = document.getElementById('option_list');
            list.innerHTML = '';

            if (!data.length) {
                list.innerHTML = '<div class="empty-state">Belum ada menu tersimpan.</div>';
                return;
            }

            data.forEach(option => {
                const item = document.createElement('div');
                item.className = 'option-item';
                item.innerHTML = `
                    <div>
                        <strong>${option.name}</strong>
                        <div class="meta">${option.category} • ${option.calories} kcal</div>
                    </div>
                    <div class="option-actions">
                        <button class="mini-btn" type="button" title="Hapus menu" data-delete-id="${option.id}">×</button>
                    </div>
                `;
                list.appendChild(item);
            });

            attachDeleteHandlers();
            loadDailyPlan();
        })
        .catch(() => {
            document.getElementById('option_list').innerHTML = '<div class="empty-state">Gagal memuat menu.</div>';
        });
}

function attachDeleteHandlers() {
    document.querySelectorAll('[data-delete-id]').forEach(button => {
        button.addEventListener('click', () => deleteOption(Number(button.dataset.deleteId)));
    });
}

function loadDailyPlan() {
    const day = daySelect.value;
    const date = dateSelect.value;
    const url = date ? `/api/daily-plan?date=${encodeURIComponent(date)}` : `/api/daily-plan?day=${encodeURIComponent(day)}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            renderMenuChecklist(data);
            renderSelectedPlan(data);
        })
        .catch(() => {
            renderMenuChecklist([]);
            renderSelectedPlan([]);
        });
}

function renderMenuChecklist(selectedItems = []) {
    const selectedIds = new Set(selectedItems.map(item => item.option_id));
    fetch('/api/options')
        .then(response => response.json())
        .then(options => {
            const list = document.getElementById('menu_checklist');
            list.innerHTML = '';

            if (!options.length) {
                list.innerHTML = '<div class="empty-state">Tambahkan menu dulu di database.</div>';
                return;
            }

            options.forEach(option => {
                const wrapper = document.createElement('label');
                wrapper.className = 'option-item';
                wrapper.innerHTML = `
                    <div>
                        <strong>${option.name}</strong>
                        <div class="meta">${option.category} • ${option.calories} kcal • ${option.protein ?? 0} g protein</div>
                    </div>
                    <input type="checkbox" value="${option.id}" ${selectedIds.has(option.id) ? 'checked' : ''} />
                `;
                list.appendChild(wrapper);
            });
        });
}

function renderSelectedPlan(items) {
    const container = document.getElementById('selected_plan');
    container.innerHTML = '';

    if (!items.length) {
        container.innerHTML = '<div class="empty-state">Belum ada menu yang dipilih untuk hari ini.</div>';
        document.getElementById('total_box').textContent = 'Total Kalori: 0 kcal • Protein: 0 g';
        return;
    }

    let totalCalories = 0;
    let totalProtein = 0;
    items.forEach(item => {
        totalCalories += Number(item.calories || 0);
        totalProtein += Number(item.protein || 0);
        const node = document.createElement('div');
        node.className = 'selected-item';
        node.innerHTML = `
            <span>${item.name}</span>
            <strong>${item.calories} kcal • ${item.protein ?? 0} g protein</strong>
        `;
        container.appendChild(node);
    });

    document.getElementById('total_box').textContent = `Total Kalori: ${totalCalories} kcal • Protein: ${totalProtein} g`;
}

function addOption() {
    const name = document.getElementById('option_name').value.trim();
    const category = document.getElementById('option_category').value.trim();
    const calories = document.getElementById('option_calories').value;
    const protein = document.getElementById('option_protein').value;

    if (!name || !calories) {
        showPrompt('Nama menu dan kalori wajib diisi!', 'error');
        return;
    }

    fetch('/api/options', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, category, calories: Number(calories), protein: Number(protein || 0) })
    })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Gagal menambahkan menu');
            }
            document.getElementById('option_name').value = '';
            document.getElementById('option_calories').value = '';
            document.getElementById('option_protein').value = '';
            showPrompt(data.message || 'Menu berhasil ditambahkan');
            loadOptions(optionFilter.value || '');
            loadSummary();
        })
        .catch(error => showPrompt(error.message || 'Gagal menambahkan menu.', 'error'));
}

function deleteOption(optionId) {
    if (!window.confirm('Yakin ingin menghapus menu ini?')) return;

    fetch(`/api/options/${optionId}`, {
        method: 'DELETE'
    })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Gagal menghapus menu');
            }
            showPrompt(data.message || 'Menu dihapus');
            loadOptions(optionFilter.value || '');
            loadDailyPlan();
            loadSummary();
        })
        .catch(error => showPrompt(error.message || 'Gagal menghapus menu.', 'error'));
}

function saveDailyPlan() {
    const day = daySelect.value;
    const date = dateSelect.value;
    const checked = [...document.querySelectorAll('#menu_checklist input:checked')];
    const optionIds = checked.map(item => Number(item.value));

    if (!date) {
        showPrompt('Tanggal wajib dipilih sebelum menyimpan.', 'error');
        return;
    }

    fetch('/api/daily-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, date, option_ids: optionIds })
    })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Gagal menyimpan jadwal harian');
            }
            showPrompt(data.message || 'Jadwal harian berhasil disimpan');
            loadDailyPlan();
            loadSummary();
            loadHistory();
        })
        .catch(error => showPrompt(error.message || 'Gagal menyimpan jadwal harian.', 'error'));
}

function openPlanModal() {
    const summary = document.getElementById('modal_plan_summary');
    const list = document.getElementById('modal_plan_list');
    const selectedDate = dateSelect.value || new Date().toISOString().split('T')[0];
    const selectedDay = daySelect.value;

    summary.textContent = `${selectedDay} • ${selectedDate}`;
    list.innerHTML = '<div class="empty-state">Memuat menu...</div>';
    if (planModal) {
        planModal.classList.remove('hidden');
        planModal.setAttribute('aria-hidden', 'false');
    }

    Promise.all([
        fetch('/api/options').then(response => response.json()),
        fetch(`/api/daily-plan?date=${encodeURIComponent(selectedDate)}`).then(response => response.json())
    ])
        .then(([options, selectedItems]) => {
            const selectedIds = new Set((selectedItems || []).map(item => Number(item.option_id)));
            list.innerHTML = '';

            if (!options.length) {
                list.innerHTML = '<div class="empty-state">Belum ada menu tersimpan.</div>';
                return;
            }

            options.forEach(option => {
                const item = document.createElement('label');
                item.className = 'modal-plan-item';
                item.innerHTML = `
                    <div>
                        <strong>${option.name}</strong>
                        <div class="meta">${option.category} • ${option.calories} kcal</div>
                    </div>
                    <input type="checkbox" value="${option.id}" ${selectedIds.has(option.id) ? 'checked' : ''} />
                `;
                list.appendChild(item);
            });
        })
        .catch(() => {
            list.innerHTML = '<div class="empty-state">Gagal memuat menu untuk diedit.</div>';
        });
}

function closePlanModal() {
    if (planModal) {
        planModal.classList.add('hidden');
        planModal.setAttribute('aria-hidden', 'true');
    }
}

function savePlanFromModal() {
    const checked = [...document.querySelectorAll('#modal_plan_list input:checked')];
    const optionIds = checked.map(item => Number(item.value));
    const payload = {
        day: daySelect.value,
        date: dateSelect.value,
        option_ids: optionIds
    };

    if (!payload.date) {
        showPrompt('Tanggal wajib dipilih sebelum menyimpan.', 'error');
        return;
    }

    fetch('/api/daily-plan', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Gagal memperbarui menu');
            }
            showPrompt(data.message || 'Menu harian berhasil diperbarui');
            closePlanModal();
            loadDailyPlan();
            loadSummary();
            loadHistory();
        })
        .catch(error => showPrompt(error.message || 'Gagal memperbarui menu.', 'error'));
}

function clearDailyPlan() {
    const day = daySelect.value;
    const date = dateSelect.value;
    fetch('/api/daily-plan', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, date })
    })
        .then(async response => {
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || 'Gagal menghapus jadwal harian');
            }
            showPrompt(data.message || 'Jadwal dihapus');
            loadDailyPlan();
            loadSummary();
            loadHistory();
        })
        .catch(error => showPrompt(error.message || 'Gagal menghapus jadwal harian.', 'error'));
}

function loadSummary() {
    fetch('/api/summary')
        .then(response => response.json())
        .then(data => {
            renderTopbar(data);
            renderWeeklySummary(data.daily_totals);
        })
        .catch(() => {
            document.getElementById('topbar').innerHTML = '';
            document.getElementById('weekly_summary').innerHTML = '<div class="empty-state">Gagal memuat ringkasan mingguan.</div>';
        });
}

function renderTopbar(data) {
    const topbar = document.getElementById('topbar');
    topbar.innerHTML = `
        <div class="stat-card">
            <div class="label">Menu</div>
            <div class="value">${data.menu_count}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Kalori</div>
            <div class="value">${data.weekly_total} kcal</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Protein</div>
            <div class="value">${data.weekly_protein ?? 0} g</div>
        </div>
        <div class="stat-card">
            <div class="label">Kategori</div>
            <div class="value">${data.categories.length}</div>
        </div>
    `;
}

function renderWeeklySummary(dailyTotals) {
    const summary = document.getElementById('weekly_summary');
    summary.innerHTML = '';

    dailyTotals.forEach(item => {
        const card = document.createElement('div');
        card.className = 'day-summary';
        card.innerHTML = `
            <strong>${item.day}</strong>
            <div>${item.count} menu</div>
            <div>${item.total_calories} kcal</div>
            <div>${item.total_protein ?? 0} g protein</div>
        `;
        summary.appendChild(card);
    });
}

function loadHistory() {
    fetch('/api/history?limit=7')
        .then(response => response.json())
        .then(data => {
            const list = document.getElementById('history_list');
            list.innerHTML = '';

            if (!data.length) {
                list.innerHTML = '<div class="empty-state">Belum ada riwayat jadwal tersimpan.</div>';
                return;
            }

            data.forEach(item => {
                const itemEl = document.createElement('div');
                itemEl.className = 'history-item';
                itemEl.innerHTML = `
                    <div class="history-head">
                        <strong>${item.date}</strong>
                        <span>${item.day}</span>
                    </div>
                    <div class="history-menu">${item.menu_names || 'Belum ada menu'}</div>
                    <div class="history-meta">${item.item_count} menu • ${item.total_calories} kcal • ${item.total_protein ?? 0} g protein</div>
                `;
                list.appendChild(itemEl);
            });
        })
        .catch(() => {
            document.getElementById('history_list').innerHTML = '<div class="empty-state">Gagal memuat riwayat jadwal.</div>';
        });
}

function searchFoodReference() {
    const query = foodSearchInput.value.trim();
    const category = foodCategoryFilter.value.trim();
    const params = new URLSearchParams();

    if (query) params.append('query', query);
    if (category) params.append('category', category);

    fetch(`/api/food-reference${params.toString() ? `?${params.toString()}` : ''}`)
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('food_reference_results');
            container.innerHTML = '';

            if (!data.length) {
                container.innerHTML = '<div class="empty-state">Tidak ada data kalori untuk pencarian ini.</div>';
                return;
            }

            data.forEach(item => {
                const row = document.createElement('div');
                row.className = 'reference-item';
                row.innerHTML = `
                    <div>
                        <strong>${item.name}</strong>
                        <div class="meta">${item.category} • ${item.portion}</div>
                    </div>
                    <div class="reference-actions">
                        <div class="reference-calories">${item.calories} kcal • ${item.protein ?? 0} g</div>
                        <button class="mini-primary" type="button" data-use-food="${item.name}|${item.calories}|${item.protein ?? 0}">Pakai</button>
                    </div>
                `;
                container.appendChild(row);
            });

            document.querySelectorAll('[data-use-food]').forEach(button => {
                button.addEventListener('click', () => {
                    const [name, calories, protein] = button.dataset.useFood.split('|');
                    document.getElementById('option_name').value = name;
                    document.getElementById('option_calories').value = calories;
                    document.getElementById('option_protein').value = protein;
                    document.getElementById('option_category').value = foodCategoryFilter.value || 'Protein';
                    document.getElementById('option_name').focus();
                });
            });
        })
        .catch(() => {
            document.getElementById('food_reference_results').innerHTML = '<div class="empty-state">Gagal memuat referensi kalori.</div>';
        });
}

function bindEvents() {
    if (dateSelect) {
        dateSelect.addEventListener('change', () => {
            syncDayFromDate();
            loadDailyPlan();
            loadHistory();
        });
    }

    if (daySelect) {
        daySelect.addEventListener('change', () => {
            if (!dateSelect.value) return;
            loadDailyPlan();
        });
    }

    if (optionFilterBtn) {
        optionFilterBtn.addEventListener('click', () => {
            loadOptions(optionFilter.value || '');
        });
    }

    if (optionFilter) {
        optionFilter.addEventListener('change', () => {
            loadOptions(optionFilter.value || '');
        });
    }

    if (foodSearchBtn) {
        foodSearchBtn.addEventListener('click', searchFoodReference);
    }

    if (foodSearchInput) {
        foodSearchInput.addEventListener('input', function () {
            if (this.value.trim().length >= 2 || this.value.trim().length === 0) {
                searchFoodReference();
            }
        });
    }

    if (foodCategoryFilter) {
        foodCategoryFilter.addEventListener('change', searchFoodReference);
    }

    if (addOptionBtn) {
        addOptionBtn.addEventListener('click', addOption);
    }

    if (editPlanBtn) {
        editPlanBtn.addEventListener('click', openPlanModal);
    }

    if (closePlanModalBtn) {
        closePlanModalBtn.addEventListener('click', closePlanModal);
    }

    if (closePlanModalSecondaryBtn) {
        closePlanModalSecondaryBtn.addEventListener('click', closePlanModal);
    }

    if (savePlanModalBtn) {
        savePlanModalBtn.addEventListener('click', savePlanFromModal);
    }

    if (planModal) {
        planModal.addEventListener('click', event => {
            if (event.target === planModal) {
                closePlanModal();
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    setTodayDate();
    bindEvents();
    loadOptions();
    loadDailyPlan();
    loadSummary();
    loadHistory();
    searchFoodReference();
});

window.addEventListener('pageshow', () => {
    setTodayDate();
});
